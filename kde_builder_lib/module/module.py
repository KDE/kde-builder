# SPDX-FileCopyrightText: 2012, 2013, 2016, 2019, 2020, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2020 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import copy
import glob
import os
import re
import shutil
import textwrap
import traceback
from typing import TYPE_CHECKING

from kde_builder_lib.build_exception import BuildException
from kde_builder_lib.build_exception import BuildExceptionConfig
from ..build_system.autotools import BuildSystemAutotools
from ..build_system.build_system import BuildSystem
from ..build_system.cmake_bootstrap import BuildSystemCMakeBootstrap
from ..build_system.kde_cmake import BuildSystemKDECMake
from ..build_system.meson import BuildSystemMeson
from ..build_system.qmake5 import BuildSystemQMake5
from ..build_system.qmake6 import BuildSystemQMake6
from ..build_system.qt4 import BuildSystemQt4
from ..build_system.qt5 import BuildSystemQt5
from ..build_system.qt6 import BuildSystemQt6
from ..debug import Debug
from ..debug import KBLogger
from ..ipc.ipc import IPC
from ..options_base import OptionsBase
from ..updater.kde_project import UpdaterKDEProject
from ..updater.kde_project_metadata import UpdaterKDEProjectMetadata
from ..updater.qt5 import UpdaterQt5
from ..updater.updater import Updater
from ..util.util import Util

if TYPE_CHECKING:
    from ..build_context import BuildContext
    from ..module_set.module_set import ModuleSet
    from ..phase_list import PhaseList

logger_module = KBLogger.getLogger("module")


class Module(OptionsBase):
    """
    A subclass of :class:`OptionsBase`, which represents a source code module of some
    sort that can be updated, built, tested and installed.

    This uses abstract interfaces to represent the build_system and the source code
    version control system (:class:`BuildSystem` and :class:`Updater` respectively).

    Includes a stringifying and can be sorted amongst other Modules.

    Examples:
    ::

        module = Module(ctx, "module-name")
        module.update() or raise "no update!"
        module.build() or raise "no build/install!"

        modulesFromSet = module_set.convert_to_modules(ctx)
        for module in modulesFromSet:
            print(f"module name: {module}")
    """

    def __init__(self, ctx: BuildContext, name: str):
        self.ctx = ctx
        self.name = name

        if not self.name:
            BuildException.croak_internal("Empty Module constructed")

        OptionsBase.__init__(self)

        # If building a BuildContext instead of a `Module`, then the context
        # can't have been set up yet...
        if self.__class__.__name__ != "BuildContext" and ctx.__class__.__name__ != "BuildContext":
            BuildException.croak_internal(f"Invalid context {ctx}")

        phases = None
        if ctx:
            # Clone the passed-in phases so we can be different. They may be modified later in set_option.
            phases = copy.copy(ctx.phases)

        # newOptions:
        self.name = name
        self.scm_obj = None
        self.build_obj = None
        self.phases: PhaseList = phases
        self.context = ctx
        self.module_set = None  # in perl it was called module-set (i.e. via "-")
        self.post_build_msgs = []

        # Record current values of what would be last source/build dir, if present,
        # before they are potentially reset during the module build.
        self.set_option({"#last-source-dir": self.get_persistent_option("source-dir") or ""})
        self.set_option({"#last-build-dir": self.get_persistent_option("build-dir") or ""})
        self.scm_obj = None

    def __str__(self) -> str:  # Add stringify operator.
        return self.name

    def get_module_set(self):
        from ..module_set.null import ModuleSetNull
        if not self.module_set:
            self.module_set = ModuleSetNull()
        return self.module_set

    def set_module_set(self, module_set: ModuleSet) -> None:
        from ..module_set.module_set import ModuleSet
        Util.assert_isa(module_set, ModuleSet)
        self.module_set = module_set

    def get_subdir_path(self, subdir_option: str) -> str:
        """
        Function to retrieve a subdirectory path with tilde-expansion and relative path handling.
        The parameter is the option key (e.g. build-dir or log-dir) to read and interpret.
        """
        directory = self.get_option(subdir_option)

        # If build-dir starts with a slash, it is an absolute path.
        if directory.startswith("/"):
            return directory

        # Make sure we got a valid option result.
        if not directory:
            raise ValueError(f"Reading option for {subdir_option} gave empty directory!")

        # If it starts with a tilde, expand it out.
        if directory.startswith("~"):
            directory = re.sub(r"^~", os.getenv("HOME"), directory)
        else:
            # Relative directory, tack it on to the end of kdesrcdir.
            kdesrcdir = self.get_option("source-dir")
            directory = f"{kdesrcdir}/{directory}"

        return directory

    def get_install_path_components(self, dirtype: str) -> dict:
        """
        Returns the directory that a module should be installed in.

        NOTE: The return value is a dict.
        The key "module" will return the final module name.
        The key "path" will return the full path to the module.
        The key "fullpath" will return their concatenation.

        For example, with module == "KDE/kdelibs", and no change in the dest-dir option, you'd get something like:
        ::
            {
              "path": "/home/user/kde/src/KDE",
              "module": "kdelibs",
              "fullpath": "/home/user/kde/src/KDE/kdelibs"
            }

        If dest-dir were changed to e.g. extragear-multimedia, you'd get:
        ::
            {
              "path": "/home/user/kde/src",
              "module": "extragear-multimedia",
              "fullpath": "/home/user/kde/src/extragear-multimedia"
            }

        Parameters:
            dirtype - Either "source" or "build".

        Returns:
            dict
        """
        module = self

        destdir = module.dest_dir()
        srcbase = module.get_source_dir()
        if dirtype == "build":
            srcbase = module.get_subdir_path("build-dir")

        combined = f"{srcbase}/{destdir}"

        # Remove dup //
        combined = re.sub("/+", "/", combined)

        parts = combined.split("/")
        result = {"module": parts.pop(), "path": "/".join(parts)}
        result["fullpath"] = f"""{result["path"]}/{result["module"]}"""

        # We used to have code here to migrate very old directory layouts. It was
        # removed as of about 2013-09-29.

        return result

    def get_source_dir(self) -> str:
        """
        Do note that this returns the *base* path to the source directory,
        without the module name or kde_projects stuff appended. If you want that
        use function fullpath().
        """
        return self.get_subdir_path("source-dir")

    def scm(self):

        if self.scm_obj:
            return self.scm_obj

        if not self.scm_obj:
            self.scm_obj = Updater(self)
        return self.scm_obj

    def set_scm_type(self, scm_type: str) -> None:
        new_type = None
        if scm_type == "git":
            new_type = Updater(self)
        elif scm_type == "proj":
            new_type = UpdaterKDEProject(self)
        elif scm_type == "metadata":
            new_type = UpdaterKDEProjectMetadata(self)
        elif scm_type == "qt5":
            new_type = UpdaterQt5(self)
        else:
            new_type = None

        self.scm_obj = new_type

    def scm_type(self) -> str:
        """
        Returns a string describing the scm platform of the given module.
        Return value: "git" at this point, as appropriate.
        """
        return self.scm().name()

    def current_scm_revision(self) -> str:
        return self.scm().current_revision_internal()

    def build_system_from_name(self, name: str) -> BuildSystem:
        """
        Returns a new build system object, given the appropriate name.
        This is a suboptimal way to fix the problem of allowing users to override
        the detected build system (we could instead use introspection to figure out
        available build systems at runtime). However, KISS...
        """
        build_system_classes = {
            "generic": BuildSystem,
            "qmake": BuildSystemQMake5,
            "qmake6": BuildSystemQMake6,
            "cmake-bootstrap": BuildSystemCMakeBootstrap,
            "kde": BuildSystemKDECMake,
            "qt": BuildSystemQt4,
            "qt5": BuildSystemQt5,
            "qt6": BuildSystemQt6,
            "autotools": BuildSystemAutotools,
            "meson": BuildSystemMeson,
        }

        class_name = build_system_classes[name.lower()] or None
        if not class_name:
            BuildException.croak_runtime(f"Invalid build system {name} requested")
        return class_name(self)

    def build_system(self) -> BuildSystem:
        if self.build_obj and self.build_obj.name() != "generic":
            return self.build_obj

        if user_build_system := self.get_option("override-build-system"):
            self.build_obj = self.build_system_from_name(user_build_system)
            return self.build_obj

        # If not set, let's guess.
        build_type = None
        source_dir = self.fullpath("source")

        # This test must come before the KDE build_system's as cmake's own
        # bootstrap system also has CMakeLists.txt
        if not build_type and os.path.exists(f"{source_dir}/CMakeLists.txt") and os.path.exists(f"{source_dir}/bootstrap"):
            build_type = BuildSystemCMakeBootstrap(self)

        if not build_type and (os.path.exists(f"{source_dir}/CMakeLists.txt") or self.is_kde_project()):
            build_type = BuildSystemKDECMake(self)

        # We have to assign to an array to force glob to return all results,
        # otherwise it acts like a non-reentrant generator whose output depends on
        # how many times it's been called...
        if not build_type and glob.glob(f"{source_dir}/*.pro"):
            build_type = BuildSystemQMake5(self)

        # "configure" is a popular fall-back option even for other build
        # systems so ensure we check last for autotools.
        if not build_type and (os.path.exists(f"{source_dir}/configure") or os.path.exists(f"{source_dir}/autogen.sh")):
            build_type = BuildSystemAutotools(self)

        # Someday move this up, but for now ensure that Meson happens after
        # configure/autotools support is checked for.
        if not build_type and os.path.exists(f"{source_dir}/meson.build"):
            build_type = BuildSystemMeson(self)

        # Don't just assume the build system is KDE-based...
        if not build_type:
            build_type = BuildSystem(self)

        self.build_obj = build_type
        return self.build_obj

    def set_build_system(self, obj: BuildSystem) -> None:
        """
        Sets the build system **object**, although you can find the build system
        type afterwards (see build_system_type).
        """
        Util.assert_isa(obj, BuildSystem)
        self.build_obj = obj

    def build_system_type(self) -> str:
        """
        Current possible build system types: KDE (i.e. cmake), Qt, autotools (either configure or autogen.sh).
        A final possibility is "pendingSource" which simply means that we don't know yet.

        If the build system type is not set ("pendingSource" counts as being set!) when this function is called
        then it will be autodetected if possible, but note that not all possible types will be detected this way.
        If in doubt use setBuildSystemType
        """
        return self.build_system().name()

    def build(self) -> bool:
        """
        Function to build this module.
        Returns:
             False on failure, True on success.
        """
        pathinfo = self.get_install_path_components("build")
        build_system = self.build_system()

        if build_system.name() == "generic" and not Debug().pretending() and not self.has_option("custom-build-command"):
            logger_module.error(f"\tr[b[{self}] does not seem to have a build system to use.")
            return False

        # Ensure we're in a known directory before we start; some options remove
        # the old build directory that a previous module might have been using.
        Util.super_mkdir(pathinfo["path"])
        Util.p_chdir(pathinfo["path"])

        if not self.setup_build_system():
            return False
        if self.get_option("build-system-only"):
            return True

        build_results = build_system.build_internal()
        if not build_results["was_successful"]:
            return False

        self.set_persistent_option("last-build-rev", self.current_scm_revision())

        # TODO: This should be a simple phase to run.
        if self.get_option("run-tests"):
            self.build_system().run_testsuite()

        if not build_results.get("work_done", None) and not self.get_option("refresh-build") and self.get_persistent_option("last-install-rev") is not None:
            logger_module.info("\tNo changes from build, skipping install (--refresh-build this module to force install)")
            return True
        elif not self.get_option("install-after-build"):
            logger_module.info("\tSkipping install due to install-after-build setting")
            return True

        self.ctx.status_view.__init__()  # Clear the progress values after build process, so they do not influence on initial progress of install process. This is needed because currently the install() is invoked from build().
        # TODO: Likewise this should be a phase to run.
        return self.install()

    def setup_build_system(self) -> bool:
        """
        Function to set up the build system in a directory.
        Returns:
             True on success, False (0) on failure.
        """

        build_system = self.build_system()

        if build_system.name() == "generic" and self.has_option("custom-build-command"):
            logger_module.info(f" b[*] No build system detected for b[y[{self}], assuming custom build command will handle")
            return True

        if build_system.name() == "generic" and not Debug().pretending():
            BuildException.croak_internal("Build system determination still pending when build attempted.")

        # Check if a previous build has happened in a different directory (which
        # can happen due to name changes on KDE.org side or flat-layout option
        # toggled)
        builddir = self.fullpath("build")
        old_build_dir = self.get_option("#last-build-dir")
        if not Debug().pretending() and builddir != old_build_dir and os.path.isdir(old_build_dir) and not os.path.exists(builddir):
            logger_module.warning(f" y[b[*] Build directory setting has changed to {builddir}.")
            logger_module.warning(f" y[b[*] Moving old build directory at {old_build_dir} to the new location.")

            try:
                shutil.move(old_build_dir, builddir)
            except Exception as e:
                logger_module.warning(textwrap.dedent(f"""\
                    r[b[*] Unable to move {old_build_dir}
                    r[b[*] to {builddir}
                    r[b[*] Error: {e}
                    y[b[*]
                    y[b[*] Will proceed, generating a new build dir.
                    """))

        refresh_reason = build_system.needs_refreshed()
        if refresh_reason != "":
            # The build system needs created, either because it doesn't exist, or
            # because the user has asked that it be completely rebuilt.
            logger_module.info(f"\tPreparing build system for y[{self}].")

            if not build_system.clean_build_system():
                logger_module.warning(f"\tUnable to clean r[{self}]!")
                return False

        result = build_system.create_build_system()
        if not result:
            logger_module.error(f"\tError creating r[{self}]'s build system!")
            return False

        # Now we're in the checkout directory
        # So, switch to the build dir.
        # builddir is automatically set to the right value for qt
        Util.p_chdir(builddir)

        if not build_system.configure_internal():
            logger_module.error(f"\tUnable to configure r[{self}] with " + self.build_system_type())

            # Add undocumented ".refresh-me" file to build directory to flag
            # for --refresh-build for this module on next run. See also the
            # "needs_refreshed" function.
            if fh := open(".refresh-me", "w"):
                print("# Build directory will be re-generated next kde-builder run", file=fh)
                print("# due to failing to complete configuration on the last run", file=fh)
                fh.close()
            return False
        return True

    def install(self) -> bool:
        """
        Responsible for installing the module (no update, build, etc.)
        Returns:
             False on failure, True on success.
        Exceptions may be thrown for abnormal conditions (e.g. no build dir exists)
        """
        builddir = self.fullpath("build")
        build_sys_file = self.build_system().configured_module_file_name()

        if not Debug().pretending() and not os.path.exists(f"{builddir}/{build_sys_file}"):
            logger_module.warning(f"\tThe build system doesn't exist for r[{self}].")
            logger_module.warning("\tTherefore, we can't install it. y[:-(].")
            return False

        self.setup_environment()

        make_install_opts = self.get_option("make-install-prefix").split(" ")
        make_install_opts = [el for el in make_install_opts if el != ""]  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it.

        # We can optionally uninstall prior to installing
        # to weed out old unused files.
        if self.get_option("use-clean-install") and self.get_persistent_option("last-install-rev"):
            if not self.build_system().uninstall_internal(make_install_opts):
                logger_module.warning(f"\tUnable to uninstall r[{self}] before installing the new build.")
                logger_module.warning("\tContinuing anyways...")
            else:
                self.unset_persistent_option("last-install-rev")

        if not self.build_system().install_internal(make_install_opts):
            logger_module.error(f"\tUnable to install r[{self}]!")
            self.context.mark_module_phase_failed("install", self)
            return False

        if Debug().pretending():
            logger_module.pretend(f"\tWould have installed g[{self}]")
            return True

        # Past this point we know we've successfully installed, for real.

        self.set_persistent_option("last-install-rev", self.current_scm_revision())

        remove_setting = self.get_option("remove-after-install")

        # Possibly remove the srcdir and builddir after install for users with
        # a little bit of HD space.
        if remove_setting == "all":
            # Remove srcdir
            srcdir = self.fullpath("source")
            logger_module.warning(f"\tRemoving b[r[{self} source].")
            Util.safe_rmtree(srcdir)

        if remove_setting == "builddir" or remove_setting == "all":
            # Remove builddir
            logger_module.warning(f"\tRemoving b[r[{self} build directory].")
            Util.safe_rmtree(builddir)

            # We're likely already in the builddir, so chdir back to the root
            os.chdir("/")
        return True

    def uninstall(self) -> bool:
        """
        Handles uninstalling this module

        Returns:
             False on failure, True on success.
        """
        builddir = self.fullpath("build")
        build_sys_file = self.build_system().configured_module_file_name()

        if not Debug().pretending() and not os.path.exists(f"{builddir}/{build_sys_file}"):
            logger_module.warning(f"\tThe build system doesn't exist for r[{self}].")
            logger_module.warning("\tTherefore, we can't uninstall it.")
            return False

        self.setup_environment()

        make_install_opts = self.get_option("make-install-prefix").split(" ")
        make_install_opts = [el for el in make_install_opts if el != ""]  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it.

        if not self.build_system().uninstall_internal(make_install_opts):
            logger_module.error(f"\tUnable to uninstall r[{self}]!")
            self.context.mark_module_phase_failed("install", self)
            return False

        if Debug().pretending():
            logger_module.pretend(f"\tWould have uninstalled g[{self}]")
            return True

        self.unset_persistent_option("last-install-rev")
        return True

    def apply_user_environment(self) -> None:
        """
        Integrates "set-env" option to the build context environment
        """
        ctx = self.context

        # Let's see if the user has set env vars to be set.
        # Note the global set-env must be checked separately anyways, so
        # we limit inheritance when searching.
        if ctx.name == self.name:
            env_dict = ctx.get_option("set-env")
        else:
            env_dict = self.get_option("set-env", "module")

        for key, value in env_dict.items():
            ctx.queue_environment_variable(key, value)

    def setup_environment(self) -> None:
        """
        Establishes proper build environment in the build context. Should be run
        before forking off commands for e.g. updates, builds, installs, etc.
        """
        ctx = self.context
        prefix = self.installation_path()

        # Add global set-envs and context
        self.context.apply_user_environment()

        # Build system's environment injection
        build_system = self.build_system()

        # Suppress injecting qt-install-dir/install-dir related environment variables if a toolchain is also set
        # Let the toolchain files/definitions take care of themselves.
        if build_system.has_toolchain():
            logger_module.debug(f"\tNot setting environment variables for b[{self}]: a custom toolchain is used")
        else:
            installdir = self.get_option("install-dir")
            qt_installdir = self.get_option("qt-install-dir")
            libname = self.get_option("libname")  # e.g. "lib" or "lib64"

            # Ensure the platform libraries we're building can be found, as long as they
            # are not the system's own libraries.
            for platformDir in [qt_installdir, installdir]:
                if not platformDir:  # OK, assume system platform is usable
                    continue
                if platformDir == "/usr":  # Don't "fix" things if system platform manually set
                    continue

                ctx.prepend_environment_value("PKG_CONFIG_PATH", f"{platformDir}/{libname}/pkgconfig")
                ctx.prepend_environment_value("LD_LIBRARY_PATH", f"{platformDir}/{libname}")
                ctx.prepend_environment_value("PATH", f"{platformDir}/bin")

            binpath = self.get_option("binpath")
            libpath = self.get_option("libpath")

            if binpath:
                ctx.prepend_environment_value("PATH", binpath)
            if libpath:
                ctx.prepend_environment_value("LD_LIBRARY_PATH", libpath)

        build_system.prepare_module_build_environment(ctx, self, prefix)

        # Read in user environment defines
        if self.name != ctx.name:  # pl2py: in perl the compare function was called here. See comment there. We just compare here without that function.
            self.apply_user_environment()

    def get_log_dir(self) -> str:
        """
        Returns the path to the log directory used during this run for this
        ``Module``, based on an autogenerated unique id. The id doesn't change
        once generated within a single run of the script.
        """
        return self.context.get_log_dir_for(self)

    def get_log_path(self, path: str) -> str:
        """
        Returns a full path that can be open()'d to write a log
        file, based on the given basename (with extension).
        Updates the "latest" symlink as well, unlike get_log_dir
        Use when you know you're going to create a new log
        """
        return self.context.get_log_path_for(self, path)

    # This is left here only for reference. todo After dropping perl version, we can delete this comment.
    # def compare(self, other):
    #     # pl2py: the only place where this function was called in perl was the comparison operator in the end of setup_environment function.
    #     # It returned -1, 0, 1 depending on if self.name is less, equal or bigger than ctx.name.
    #     # The interesting thing is that despite function returns some value, when it arrives to statement `my $n = $self == $ctx;` it became "converted" to the wanted.
    #     # For example, when names are different, and -1 is returned by compare, $n gets the empty string (which reads as false).
    #     # And if names are the same, (for example, I intentionally made a module called "global", 0 is returned, and 1 is arrived to $n (which reads as true).
    #     # So instead of using this function, we will just compare as needed in the place where that comparison was invoked.
    #     # But I (Andrew Shark) will place the code which was the effect of calling this comparison here, for reference.
    #     return self.name == other.name

    def update(self, ipc, ctx) -> bool:
        module_name = self.name
        module_src_dir = self.get_source_dir()
        kdesrc = ctx.get_source_dir()

        if kdesrc != module_src_dir:
            # This module has a different source directory, ensure it exists.
            if not Util.super_mkdir(module_src_dir):
                logger_module.error(f"Unable to create separate source directory for r[{self}]: {module_src_dir}")
                ipc.send_ipc_message(IPC.MODULE_FAILURE, module_name)

        # Check for whether path to source dir has changed due to directory-layout
        # option or changes to metadata.
        fullpath = self.fullpath("source")
        old_source_dir = self.get_option("#last-source-dir")
        if not Debug().pretending() and fullpath != old_source_dir and os.path.isdir(old_source_dir) and not os.path.exists(fullpath):
            logger_module.warning(f" y[b[*] Source directory setting has changed to {fullpath}.")
            logger_module.warning(f" y[b[*] Moving old source directory at {old_source_dir} to the new location.")

            try:
                shutil.move(old_source_dir, fullpath)
            except Exception as e:
                logger_module.warning(textwrap.dedent(f"""
                    r[b[*] Unable to move {old_source_dir}
                    r[b[*] to {fullpath}
                    r[b[*] Error: {e}
                    y[b[*]
                    y[b[*] Will proceed, generating a new source dir.
                    """))
        count = None
        return_value = None

        try:
            count = self.scm().update_internal(ipc)
        except Exception as e:
            traceback.print_exc()
            reason = IPC.MODULE_FAILURE

            if BuildException.had_an_exception(e):
                if e.exception_type == "ConflictPresent":
                    reason = IPC.MODULE_CONFLICT
                else:
                    ctx.mark_module_phase_failed("build", self)
                e = e.message

            logger_module.error(f"Error updating r[{self}], removing from list of packages to build.")
            logger_module.error(f" > y[{e}]")

            ipc.send_ipc_message(reason, module_name)
            self.phases.filter_out_phase("build")
            return_value = False
        else:
            message = ""
            if count is None:
                message = Debug().colorize("b[y[Unknown changes].")
                ipc.notify_update_success(module_name, message)
            elif count:
                if count == 1:
                    message = "1 file affected."
                if count != 1:
                    message = f"{count} files affected."
                ipc.notify_update_success(module_name, message)
            else:
                message = "0 files affected."
                refresh_reason = self.build_system().needs_refreshed()
                ipc.send_ipc_message(IPC.MODULE_UPTODATE, f"{module_name},{refresh_reason}")

            # We doing e.g. --src-only, the build phase that normally outputs
            # number of files updated doesn't get run, so manually mention it
            # here.
            if not ipc.supports_concurrency():
                logger_module.info(f"\t{self} update complete, {message}")

            return_value = True
        logger_module.info("")  # Print empty line.
        return return_value

    # @override
    def set_option(self, options: dict) -> None:
        """
        This calls :meth:`OptionsBase.set_option` and performs any Module-specific
        handling.
        """

        # Ensure we don't accidentally get fed module-set options
        for mso in ["use-modules", "ignore-modules"]:
            if mso in options:
                logger_module.error(f" r[b[*] module b[{self}] should be declared as module-set to use b[{mso}]")
                raise BuildExceptionConfig(mso, f"Option {mso} can only be used in module-set")

        # Special case handling.
        if "filter-out-phases" in options:
            for phase in options["filter-out-phases"].split(" "):
                self.phases.filter_out_phase(phase)
            del options["filter-out-phases"]

        # Phases changes handling
        #
        # The context phases were handled by cmdline. The module-sets will eventually be expanded to modules. For module, we will handle its phases.
        if "no-src" in options:
            self.phases.filter_out_phase("update")
            del options["no-src"]
        if "no-install" in options:
            self.phases.filter_out_phase("install")
            del options["no-install"]
        if "no-tests" in options:
            self.phases.filter_out_phase("test")  # May not work properly yet.
            del options["no-tests"]
        if "no-build" in options:
            self.phases.filter_out_phase("build")
            del options["no-build"]
        if "uninstall" in options:
            # Not useful yet. Currently only may be useful to disable uninstallation when uninstalling with cmdline ("uninstall" run_mode)
            if self.phases.has("uninstall"):
                self.phases.reset_to(["uninstall"])
            else:
                self.phases.clear()
            del options["uninstall"]
        if "build-only" in options:
            if self.phases.has("build"):
                self.phases.reset_to(["build"])
            else:
                self.phases.clear()
            del options["build-only"]
        if "install-only" in options:
            # Not useful yet, because install is invoked by run_mode or in the end of building function. See a todo with text "Likewise this should be a phase to run."
            if self.phases.has("install"):
                self.phases.reset_to(["install"])
            else:
                self.phases.clear()
            del options["install-only"]

        OptionsBase.set_option(self, options)

    # @override(check_signature=False)
    def get_option(self, key: str, level_limit="allow-inherit") -> str | bool | dict | None:
        """
        This function returns an option value for a given module. Some globals
        can't be overridden by a module's choice (but see 2nd parameter below).
        If so, the module's choice will be ignored, and a warning will be issued.

        Option names are case-sensitive!

        Some options (e.g. cmake-options, configure-flags) have the global value
        and then the module's own value appended together. To get the actual
        module setting you must use the level limit parameter set to "module".

        Likewise, some qt module options do not obey the previous proviso since
        Qt options are not likely to agree nicely with generic KDE build_system
        options.

        Parameters:
            key: Name of option
            level_limit: Level limit (optional). If not present, then the value
                "allow-inherit" is used. Options:
                  - allow-inherit: Module value is used if present (with exceptions),
                    otherwise global is used.
                  - module: Only module value is used (if you want only global then use the
                    buildContext) NOTE: This overrides global "sticky" options as well!

        Returned type - for example used in
          bool - "#guessed-kde-project"
          None - unexisting key in module-only level
          dict - "set-env"
          str - almost everything else
        """

        ctx = self.context

        # Some global options would probably make no sense applied to Qt.
        qt_copy_overrides = ["branch", "configure-flags", "tag", "cxxflags"]
        if key in qt_copy_overrides and self.build_system_type() == "Qt":
            level_limit = "module"

        Util.assert_in(level_limit, ["allow-inherit", "module"])

        # If module-only, check that first.
        if level_limit == "module":
            return self.options[key] if key in self.options else None

        ctx_value = ctx.get_option(key)  # we'll use this a lot from here

        # Some global options always override module options.
        if ctx.has_sticky_option(key):
            return ctx_value

        # Some options append to the global (e.g. conf flags)
        conf_flags = ["cmake-options", "configure-flags", "cxxflags"]
        if key in conf_flags and ctx_value:
            return (f"{ctx_value} " + self.options.get(key, "")).strip()

        # Everything else overrides the global option, unless it's simply not
        # set at all.
        return self.options.get(key, ctx_value)

    def get_persistent_option(self, key: str) -> str | int | None:
        """
        Gets persistent options set for this module. First parameter is the name
        of the option to lookup. None is returned if the option is not set,
        although even if the option is set, the value returned might be empty.
        Note that ``BuildContext`` also has this function, with a slightly
        different signature, which OVERRIDEs this function since Perl does not
        have parameter-based method overloading.

        Return types: the same as :meth:`BuildContext.get_persistent_option()`
        """
        return self.context.get_persistent_option(self.name, key)

    def set_persistent_option(self, key: str, value) -> None:
        """
        Sets a persistent option (i.e. survives between processes) for this module.
        Parameters:
            key: The name of the persistent option.
            value: Its actual value.
        See the warning for get_persistent_option above, it also applies for this
        method vs. :meth:`BuildContext.set_persistent_option`
        """
        return self.context.set_persistent_option(self.name, key, value)

    def unset_persistent_option(self, key: str) -> None:
        """
        Unsets a persistent option for this module.
        Only parameter is the name of the option to unset.
        """
        self.context.unset_persistent_option(self.name, key)

    def fullpath(self, dirtype: str) -> str:
        # Returns the path to the desired directory type (source or build),
        # including the module destination directory itself.
        Util.assert_in(dirtype, ["build", "source"])

        pathinfo = self.get_install_path_components(dirtype)
        return pathinfo["fullpath"]

    def full_project_path(self) -> str:
        """
        Returns the "full kde-projects path" for the module. As should be obvious by
        the description, this only works for modules with scm type that is a
        :class:`UpdaterKDEProject` (or its subclasses), but modules that don't fall into this
        hierarchy will just return the module name (with no path components) anyway.
        """
        return self.get_option("#kde-project-path", "module") or self.name

    def is_kde_project(self) -> bool:
        """
        Returns true if this module is (or was derived from) a kde-projects module.
        """
        return self.scm_type() == "proj"

    def dest_dir(self) -> str:
        """
        Function to return the name of the destination directory for the
        checkout and build routines. Based on the dest-dir option. The return
        value will be relative to the src/build dir. The user may use the
        "$MODULE" or "${MODULE}" sequences, which will be replaced by the name of
        the module in question.
        """
        dest_dir = self.get_option("dest-dir")
        base_path = None

        layout = self.get_option("directory-layout")
        if layout == "flat":
            base_path = self.name
        elif layout == "invent":  # invent layout is the modern layout for proper KDE projects
            base_path = self.get_option("#kde-repo-path", "module")
            base_path = base_path or self.name  # Default if not provided in repo-metadata
        elif layout == "metadata":
            base_path = self.get_option("#kde-project-path", "module")
            base_path = base_path or self.name  # Default if not provided in repo-metadata
        else:
            if not self.has_option("#warned-invalid-directory-layout"):  # avoid spamming
                logger_module.warning(f"y[ * Invalid b[directory-layout]y[ value: \"{layout}\". Will use b[flat]y[ instead for b[{self}]")
                self.set_option({"#warned-invalid-directory-layout": True})
            base_path = self.name

        # Note the default dest-dir option is "${MODULE}" so this normally is used
        dest_dir = re.sub(r"(\$\{MODULE})|(\$MODULE\b)", base_path, dest_dir)

        return dest_dir

    def installation_path(self) -> str:
        """
        Function to return the installation path of a given module (the value
        that is passed to the CMAKE_INSTALL_PREFIX CMake option).
        It is based on the "install-dir" option.
        The user may use "$MODULE" or "${MODULE}" in the "install-dir" option to have
        them replaced by the name of the module in question.
        """
        path = self.get_option("install-dir")
        module_name = self.name
        path = re.sub(r"(\$\{MODULE})|(\$MODULE\b)", module_name, path)

        return path

    def get_post_build_messages(self) -> list[str]:
        """
        Returns a list of any "post-build" messages that have been set for the module
        to show after the build has ended. These may be messages such as warning of a
        local source conflict that may have scrolled past or similar things the user
        needs to know about.

        Each entry in the list will be a text message that should be shown (perhaps
        with additional formatting).
        """
        return self.post_build_msgs

    def add_post_build_message(self, new_msg: str) -> None:
        """
        Adds the given message to the list of post-build messages to show to the user
        """
        self.post_build_msgs.append(new_msg)
