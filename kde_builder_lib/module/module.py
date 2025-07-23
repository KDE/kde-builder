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
import sys
import traceback
from typing import TYPE_CHECKING

from ..kb_exception import KBException
from ..kb_exception import KBRuntimeError
from ..kb_exception import ProgramError
from ..kb_exception import SetOptionError
from ..build_system.autotools import BuildSystemAutotools
from ..build_system.build_system import BuildSystem
from ..build_system.kde_cmake import BuildSystemKDECMake
from ..build_system.meson import BuildSystemMeson
from ..build_system.qmake5 import BuildSystemQMake5
from ..build_system.qmake6 import BuildSystemQMake6
from ..build_system.qt5 import BuildSystemQt5
from ..debug import Debug
from ..debug import KBLogger
from ..ipc.ipc import IPC
from ..options_base import OptionsBase
from ..updater.kde_project import UpdaterKDEProject
from ..updater.kde_project_metadata import UpdaterKDEProjectMetadata
from ..updater.qt5 import UpdaterQt5
from ..updater.updater import Updater
from ..util.util import Util
from ..util.textwrap_mod import textwrap

if TYPE_CHECKING:
    from ..build_context import BuildContext
    from ..module_set.module_set import ModuleSet
    from ..phase_list import PhaseList

logger_module = KBLogger.getLogger("module")


class Module(OptionsBase):
    """
    Represents a source code module of some sort that can be updated, built, tested and installed.

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
        OptionsBase.__init__(self)
        self.name = name

        if not self.name:
            raise ProgramError("Empty Module constructed")

        # Think of it as a runtime serial number for the created module.
        # The assigned number depends on the position the module was appeared in the build configs.
        # It is used in _compare_build_order_depends() as a pre-last way of ordering modules for building.
        self.create_id = 0

        # If building a BuildContext instead of a `Module`, then the context
        # can't have been set up yet...
        if self.__class__.__name__ != "BuildContext" and ctx.__class__.__name__ != "BuildContext":
            raise ProgramError(f"Invalid context {ctx}")

        phases = None
        if ctx:
            # Clone the passed-in phases so we can be different. They may be modified later in set_option.
            phases = copy.copy(ctx.phases)

        # newOptions:
        self.scm_obj: Updater | None = None
        self.build_obj: BuildSystem | None = None
        self.phases: PhaseList = phases
        self.context = ctx
        self.module_set: ModuleSet | None = None  # in perl it was called module-set (i.e. via "-")
        self.post_build_msgs: list[str] = []
        self.env: dict[str, str] = {}
        self.current_phase: str | None = None  # for disabling the line "# with environment: .../kde-builder.env" in logged commands for git commands

        if self.__class__.__name__ != "BuildContext":
            # Avoid setting this for BuildContext, because it has its own option value type verification code, which needs BuildContext to be already initialized
            # (for reading self.all_boolean_options).
            # But currently, BuildContext is inherited from Module, so we initialize Module first (as part of BuildContext initialization).
            # TODO make a proper inheritance scheme. The BuildContext and Module most likely should be inherited from common abstract class.

            # Record current values of what would be last source/build dir, if present,
            # before they are potentially reset during the module build.
            self.set_option("#last-source-dir", self.get_persistent_option("source-dir") or "")
            self.set_option("#last-build-dir", self.get_persistent_option("build-dir") or "")

    def __str__(self) -> str:  # Add stringify operator.
        return self.name

    def get_module_set(self):
        """
        Return the :class:`ModuleSet` that was assigned earlier. If no ModuleSet was assigned, return a valid (but null) ModuleSet.
        """
        from ..module_set.null import ModuleSetNull
        if not self.module_set:
            self.module_set = ModuleSetNull()
        return self.module_set

    def set_module_set(self, module_set: ModuleSet) -> None:
        """
        Specify the `ModuleSet` this module was spawned from. Optional.
        """
        from ..module_set.module_set import ModuleSet
        Util.assert_isa(module_set, ModuleSet)
        self.module_set = module_set

    def get_absolute_path(self, option_name: str) -> str:
        """
        Converts the value of path-like option to an absolute path. Non-absolute paths in option values are treated as subdirs of source-dir.

        Handles tilde expansion and relative paths.

        Args:
            option_name: The option key (e.g. "build-dir" or "log-dir") to read and interpret.
        """
        directory = self.get_option(option_name)

        # If build-dir starts with a slash, it is an absolute path.
        if directory.startswith("/"):
            return directory

        # Make sure we got a valid option result.
        if not directory:
            raise ValueError(f"Reading option for {option_name} gave empty directory!")

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
        Return the directory that a module should be installed in.

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

        Args:
            dirtype: Either "source" or "build".

        Returns:
            dict
        """
        module = self

        destdir = module.dest_dir()
        srcbase = module.get_source_dir()
        if dirtype == "build":
            srcbase = module.get_absolute_path("build-dir")

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
        Return absolute base path to the source directory.

        Do note that this returns the *base* path to the source directory,
        without the module name or kde_projects stuff appended. If you want that, use :meth:`fullpath()`.
        """
        return self.get_absolute_path("source-dir")

    def scm(self):
        """
        Returns the `Updater` plugin.
        """
        return self.scm_obj

    def set_scm_type(self, scm_type: str) -> None:
        """
        Set the source control plugin (git, kde-projects) based on the given scm_type name.

        Normally auto-detection is used instead, this permits manual setup.
        """
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
        Return the name of the scm plugin, as determined by :meth:`scm()`.

        Return value: "git" at this point, as appropriate.
        """
        return self.scm().name()

    def current_scm_revision(self) -> str:
        """
        Return a string with scm-specific revision ID.

        Can be a Git-style SHA or something else entirely.
        Can case an autodetection of the scm plugin.
        """
        return self.scm().current_revision_internal()

    def build_system_from_name(self, name: str) -> BuildSystem:
        """
        As with :meth:`set_scm_type()`, used to manually set the build system plugin. This is exposed to the user as "override-build-system".

        Returns a new build system object, given the appropriate name.
        This is a suboptimal way to fix the problem of allowing users to override
        the detected build system (we could instead use introspection to figure out
        available build systems at runtime). However, KISS...
        """
        build_system_classes = {
            "generic": BuildSystem,
            "qmake": BuildSystemQMake5,
            "qmake6": BuildSystemQMake6,
            "kde": BuildSystemKDECMake,
            "qt5": BuildSystemQt5,
            "autotools": BuildSystemAutotools,
            "meson": BuildSystemMeson,
        }

        class_name = build_system_classes.get(name.lower())
        if not class_name:
            raise KBRuntimeError(f"Invalid build system {name} requested")
        return class_name(self)

    def build_system(self) -> BuildSystem:
        """
        Autodetects the appropriate build system plugin if not already done (or manually set) and then returns the `BuildSystem` plugin.
        """
        if self.build_obj and self.build_obj.name() != "generic":
            return self.build_obj

        if user_build_system := self.get_option("override-build-system"):
            self.build_obj = self.build_system_from_name(user_build_system)
            return self.build_obj

        # If not set, let's guess.
        build_type = None
        source_dir = self.fullpath("source")

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
        Set the build system **object**, although you can find the build system type afterwards (see build_system_type).

        Like :meth:`build_system_from_name()`, but passes the proper `BuildSystem` directly.
        """
        Util.assert_isa(obj, BuildSystem)
        self.build_obj = obj

    def build_system_type(self) -> str:
        """
        Return the name of the build system plugin, as determined by :meth:`build_system()`.

        Current possible build system types: KDE (i.e. cmake), Qt, autotools (either configure or autogen.sh).
        A final possibility is "pendingSource" which simply means that we don't know yet.

        If the build system type is not set ("pendingSource" counts as being set!) when this function is called
        then it will be autodetected if possible, but note that not all possible types will be detected this way.
        """
        return self.build_system().name()

    def build(self) -> bool:
        """
        Execute the build and install (or pretends to in pretend mode) using the appropriate build system. Can also run the testsuite as part of the build.

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

        if self.get_option("run-tests"):
            self.build_system().run_testsuite()

        if not build_results.get("work_done", None) and not self.get_option("refresh-build") and self.get_persistent_option("last-install-rev") is not None:
            logger_module.info("\tNo changes from build, skipping install (--refresh-build this project to force install)")
            return True
        elif not self.phases.has("install"):
            logger_module.info("\tSkipping install due to disabled install phase.")
            return True

        self.context.status_view.__init__()  # Clear the progress values after build process, so they do not influence on initial progress of install process. This is needed because currently the install() is invoked from build().
        # TODO: this should be a phase to run.
        return self.install()

    def setup_build_system(self) -> bool:
        """
        Set up the build system for the module to permit :meth:`build()` to work, including creating build dir, running cmake/configure/etc.

        It is called automatically but will not take any action if the build system is already established.

        Returns:
             True on success, False (0) on failure.
        """
        build_system = self.build_system()

        if build_system.name() == "generic" and self.has_option("custom-build-command"):
            logger_module.info(f" b[*] No build system detected for b[y[{self}], assuming custom build command will handle")
            return True

        if build_system.name() == "generic" and not Debug().pretending():
            raise ProgramError("Build system determination still pending when build attempted.")

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
        Install (or pretend to install) the module.

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
            logger_module.debug(f"\tWould have installed g[{self}]")
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
        Uninstall (or pretend to uninstall) the module.

        Not normally called but can be configured to be called.

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
            self.context.mark_module_phase_failed("uninstall", self)
            return False

        if Debug().pretending():
            logger_module.debug(f"\tWould have uninstalled g[{self}]")
            return True

        self.unset_persistent_option("last-install-rev")
        return True

    def setup_environment(self) -> None:
        """
        Establish proper build environment.

        Should be run before forking off commands for e.g. updates, builds, installs, etc.
        """
        module_set_env_dict = self.get_option("set-env", "module")  # limit inheritance when searching
        global_set_env_dict = self.context.get_option("set-env")

        # Add global set-env to module set-env (only for those variables that are not defined in module, i.e. those that are not overriding the global).
        for key, value in global_set_env_dict.items():
            if key not in module_set_env_dict:
                self.queue_environment_variable(key, value)

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
            for platform_dir in [qt_installdir, installdir]:
                if not platform_dir:  # OK, assume system platform is usable
                    continue
                if platform_dir == "/usr":  # Don't "fix" things if system platform manually set
                    continue

                self.prepend_environment_value("PKG_CONFIG_PATH", f"{platform_dir}/{libname}/pkgconfig")
                self.prepend_environment_value("LD_LIBRARY_PATH", f"{platform_dir}/{libname}")
                self.prepend_environment_value("PATH", f"{platform_dir}/bin")

            binpath = self.get_option("binpath")
            libpath = self.get_option("libpath")

            if binpath:
                self.prepend_environment_value("PATH", binpath)
            if libpath:
                self.prepend_environment_value("LD_LIBRARY_PATH", libpath)

        build_system.prepare_module_build_environment()

        # Add module's set-envs
        for key, value in module_set_env_dict.items():
            self.queue_environment_variable(key, value)

    def get_log_dir(self) -> str:
        """
        Return the base path to the log directory for this module during this execution.

        **NOTE** Different modules can have different base paths.
        The dir name is based on an autogenerated unique id. The id doesn't change once generated within a single run of the kde-builder.
        """
        return self.context.get_log_dir_for(self)

    def get_log_path(self, path: str) -> str:
        """
        Return a full path that can be open()'d to write a log file, based on the given basename (with extension).

        Updates the "latest" symlink as well, unlike get_log_dir
        Use when you know you're going to create a new log
        """
        return self.context.get_log_path_for(self, path)

    def update(self, ipc: IPC, ctx: BuildContext) -> bool:
        """
        Execute the update (or pretends to do so) using the appropriate source control system.

        Returns:
             False on failure, True on success.
        """
        module_name = self.name
        module_src_dir = self.get_source_dir()
        kdesrc = ctx.get_source_dir()

        if kdesrc != module_src_dir:
            # This module has a different source directory, ensure it exists.
            if not Util.super_mkdir(module_src_dir):
                logger_module.error(f"\tUnable to create separate source directory for r[{self}]: {module_src_dir}")
                ipc.send_ipc_message(IPC.MODULE_FAILURE, module_name)
                self.current_phase = None
                logger_module.info("")  # Print empty line.
                return False

        # Check for whether path to source dir has changed due to directory-layout
        # option or changes to metadata.
        fullpath = self.fullpath("source")
        old_source_dir = self.get_option("#last-source-dir")
        if not Debug().pretending() and fullpath != old_source_dir and os.path.isdir(old_source_dir) and not os.path.exists(fullpath):
            logger_module.warning(f"""\
                \ty[b[*] Source directory setting has changed to {fullpath}.
                \ty[b[*] Moving old source directory at {old_source_dir} to the new location.""")

            try:
                shutil.move(old_source_dir, fullpath)
            except Exception as e:
                logger_module.warning(textwrap.dedent(f"""\
                    \tr[b[*] Unable to move {old_source_dir}
                    \tr[b[*] to {fullpath}
                    \tr[b[*] Error: {e}
                    \ty[b[*] Will proceed, generating a new source dir."""))

        self.current_phase = "update"

        try:
            count = self.scm().update_internal(ipc)
        except Exception as e:
            if not isinstance(e, KBException):
                # Do not print traceback for our KBException type exceptions, as we want just a short error message in the output.
                # Still print the traceback in case it is other Exception type, as this may help to debug problems in case something went wrong in our code.
                traceback.print_exc()

            ctx.mark_module_phase_failed("update", self)

            if isinstance(e, KBException):
                e_str = e.message
            else:
                e_str = str(e)

            logger_module.error(f"{e_str}")
            if not ipc.supports_concurrency():  # Because in async mode, this will be written by kde-builder-build (main) process.
                logger_module.error(f"\tError updating r[{self.name}], removing from list of projects to build.")

            ipc.send_ipc_message(IPC.MODULE_FAILURE, module_name)
            self.phases.filter_out_phase("build")
            return_value = False
        else:  # executed if there were no exceptions in try block
            message = ""
            if count:
                if count == 1:
                    message = "1 commit pulled."
                if count != 1:
                    message = f"{count} commits pulled."
                ipc.notify_update_success(module_name, message)
            else:
                message = "0 commits pulled."
                refresh_reason = self.build_system().needs_refreshed()
                ipc.send_ipc_message(IPC.MODULE_UPTODATE, f"{module_name},{refresh_reason}")

            # We doing e.g. --src-only, the build phase that normally outputs
            # number of files updated doesn't get run, so manually mention it
            # here.
            if not ipc.supports_concurrency():
                logger_module.info(f"\t{self} update complete, {message}")

            return_value = True
        self.current_phase = None
        logger_module.info("")  # Print empty line.
        return return_value

    # @override
    def set_option(self, opt_name: str, opt_val) -> None:
        """
        Set a configuration option that can be checked later using :meth:`get_option()`.

        Normally set from user input (cmdline or rc-file) but supports ways for kde-builder to internally override user settings or set hidden flags
        for action in later phases. Does not survive beyond the current execution.
        This calls :meth:`OptionsBase.set_option` and performs any Module-specific handling.
        """
        # Ensure we don't accidentally get fed module-set options
        for mso in ["use-projects", "ignore-projects"]:
            if opt_name == mso:
                logger_module.error(f" r[b[*] project b[{self}] should be declared as group to use b[{mso}]")
                raise SetOptionError(mso, f"Option {mso} can only be used in group")

        # Special case handling.
        if opt_name == "filter-out-phases":
            for phase in opt_val.split(" "):
                self.phases.filter_out_phase(phase)
            return

        # Phases changes handling
        #
        # The context phases were handled by cmdline. The module-sets will eventually be expanded to modules. For module, we will handle its phases.
        if opt_name == "no-src":
            self.phases.filter_out_phase("update")
            return
        if opt_name == "no-install":
            self.phases.filter_out_phase("install")
            return
        if opt_name == "no-build":
            self.phases.filter_out_phase("build")
            return
        if opt_name == "uninstall":
            # Not useful yet. Currently only may be useful to disable uninstallation when uninstalling with cmdline ("uninstall" run_mode)
            if self.phases.has("uninstall"):
                self.phases.reset_to(["uninstall"])
            else:
                self.phases.clear()
            return
        if opt_name == "build-only":
            if self.phases.has("build"):
                self.phases.reset_to(["build"])
            else:
                self.phases.clear()
            return
        if opt_name == "install-only":
            # Not useful yet, because install is invoked by run_mode or in the end of building function. See a todo with text "Likewise this should be a phase to run."
            if self.phases.has("install"):
                self.phases.reset_to(["install"])
            else:
                self.phases.clear()
            return

        OptionsBase.set_option(self,  opt_name, opt_val)

    # @override(check_signature=False)
    def get_option(self, key: str, level_limit="allow-inherit") -> str | bool | dict | None:
        """
        Return an option value for a given module.

        Some globals can't be overridden by a module's choice (but see level_limit parameter below).
        If so, the module's choice will be ignored, and a warning will be issued.

        Option names are case-sensitive!

        Some options (e.g. cmake-options, configure-flags, meson-options) have the global value
        and then the module's own value appended together. To get the actual
        module setting you must use the level limit parameter set to "module".

        Likewise, some qt module options do not obey the previous proviso since
        Qt options are not likely to agree nicely with generic KDE build_system
        options.

        Options starting with "#" can only be set internally (i.e. not from rc-file
        or cmdline) so this can be used as a way to tag modules with data meant not
        to be user-accessible.

        Args:
            key: Name of option
            level_limit: Level limit (optional). If not present, then the value
                "allow-inherit" is used. Options:
                  - allow-inherit: Module value is used if present (with exceptions),
                    otherwise global is used.
                  - module: Only module value is used (if you want only global then use the
                    buildContext).

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

        # Some options append to the global (e.g. conf flags)
        conf_flags = ["cmake-options", "configure-flags", "cxxflags", "meson-options"]
        if key in conf_flags and ctx_value:
            return (f"{ctx_value} " + self.options.get(key, "")).strip()

        # Everything else overrides the global option, unless it's simply not set at all.
        return self.options.get(key, ctx_value)

    def get_persistent_option(self, key: str) -> str | int | None:
        """
        Return option value that had been set in a previous kde-builder run (saved in a file on disk).

        Args:
             key: The name of the option to lookup.

        None is returned if the option is not set, although even if the option is set, the value returned might be empty.

        Return types: the same as :meth:`BuildContext.get_persistent_option()`
        """
        return self.context.get_persistent_option(self.name, key)

    def set_persistent_option(self, key: str, value) -> None:
        """
        Set an option to a string value, that will be read-in again on the next kde-builder run and can then be queried again.

        Args:
            key: The name of the persistent option.
            value: Its actual value.
        See the warning for get_persistent_option above, it also applies for this
        method vs. :meth:`BuildContext.set_persistent_option`
        """
        return self.context.set_persistent_option(self.name, key, value)

    def unset_persistent_option(self, key: str) -> None:
        """
        Remove an existing persistent option.

        Args:
            key: The name of the option to unset.
        """
        self.context.unset_persistent_option(self.name, key)

    def fullpath(self, dirtype: str) -> str:
        """
        Return the absolute full path to the source or build directory, including any module name or dest-dir.

        This is the directory you can git-clone to, cd to for build, etc.
        """
        # Returns the path to the desired directory type (source or build),
        # including the module destination directory itself.
        Util.assert_in(dirtype, ["build", "source"])

        pathinfo = self.get_install_path_components(dirtype)
        return pathinfo["fullpath"]

    def full_project_path(self) -> str:
        """
        Return the "legacy kde project path" for the module.

        E.g. for the "juk" module, would return "kde/kdemultimedia/juk".
        This only works for modules with scm type that is a
        :class:`UpdaterKDEProject` (or its subclasses), but modules that don't fall into this
        hierarchy will just return the module name (with no path components) anyway.
        """
        return self.get_option("#kde-project-path", "module") or self.name

    def is_kde_project(self) -> bool:
        """
        Return true if this module is (or was derived from) a kde-projects module.
        """
        return self.scm_type() == "proj"

    def dest_dir(self) -> str:
        """
        Return the "dest-dir" for the module, used for the checkout and build routines.

        The return value will be relative to the src/build dir. The user may use the
        "$MODULE" or "${MODULE}" sequences, which will be replaced by the name of the module in question.

        dest-dir is effectively just a way to modify the on-disk module name. It used to be used more heavily
        to allow for having multiple build/source directories for a given module (varying by branch or tag),
        but even with git this value may change for KDE-based repositories to set subdirectories that match KDE project
        paths. Supports expanding "$MODULE" or "${MODULE}" sequences to what otherwise would have been the dest-dir.
        """
        dest_dir = self.get_option("dest-dir")

        # Note the default dest-dir option is "${MODULE}"
        if "${MODULE}" in dest_dir or "$MODULE" in dest_dir:
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
                    self.set_option("#warned-invalid-directory-layout", True)
                base_path = self.name

            dest_dir = dest_dir.replace("$MODULE", base_path)
            dest_dir = dest_dir.replace("${MODULE}", base_path)

        return dest_dir

    def installation_path(self) -> str:
        """
        Return the installation path of a given module.

        This is the value that is passed to the CMAKE_INSTALL_PREFIX CMake option.
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
        Return a list of any "post-build" messages that have been set for the module to show after the build has ended.

        These may be messages such as warning of a local source conflict that may have scrolled past or similar things the user
        needs to know about.

        Each entry in the list will be a text message that should be shown (perhaps with additional formatting).
        """
        return self.post_build_msgs

    def set_resolved_repository(self) -> None:
        """
        Resolves any magic values (such as "kde-projects") and git-repository-base in "repository" option and sets the "#resolved-repository" internal option.

        Resolved value is either a full url like "https://invent.kde.org/sysadmin/dummy.git" or an aliased shortened url like "kde:sysadmin/dummy.git".
        """
        selected_repo = self.get_option("repository")
        repo_set: dict = self.context.get_option("git-repository-base")

        if not selected_repo:
            # Empty repository ("") does not immediately mean error. For example, user may want to work on their new/tutorial project,
            # and the local project does not have a remote url. Users could additionally specify no-src option for such projects.
            # The error however will happen in case they _attempt_ to update sources when "repository" is empty.
            self.set_option("#resolved-repository", "")

        elif selected_repo == "kde-projects":
            proj_db = self.context.get_project_data_reader().repositories
            if self.name in proj_db:
                value = proj_db[self.name]["repo"]
                self.set_option("#resolved-repository", value)
            else:
                logger_module.debug(f"Project y[{self.name}] is not recognized as KDE project, but it has y[repository] set as kde-projects. Cannot resolve it.")
                self.set_option("#resolved-repository", "")

        elif selected_repo in repo_set:
            base_path = repo_set[selected_repo]
            resolved = base_path + self.name
            logger_module.debug(f"Resolving {self.name} repository option with using git-repository-base to {resolved}")
            self.set_option("#resolved-repository", resolved)

        elif selected_repo == "qt-projects":
            self.set_option("#resolved-repository", "https://invent.kde.org/qt/qt/qt5.git")

        else:
            self.set_option("#resolved-repository", selected_repo)

        return

    def add_post_build_message(self, new_msg: str) -> None:
        """
        Add the given message to the list of post-build messages to show to the user.
        """
        self.post_build_msgs.append(new_msg)

    def queue_environment_variable(self, key: str, value: str) -> None:
        """
        Add an environment variable and value to the list of environment variables to apply for the next subprocess execution.

        Note that these changes are /not/ reflected in the current environment,
        so if you are doing something that requires that kind of update you
        should do that yourself (but remember to have some way to restore the old
        value if necessary).
        """
        logger_module.debug(f"\tQueueing g[{key}] to be set to y[{value}]")
        self.env[key] = value

    def reset_environment(self) -> None:
        """
        Clear the list of environment variables to set for log_command runs.
        """
        self.env = {}

    def commit_environment_changes(self) -> None:
        """
        Apply all changes queued by queue_environment_variable to the actual environment irretrievably.

        Use this before exec()'ing another child, for instance.
        """
        for key, value in self.env.items():
            logger_module.debug(f"\tSetting environment variable g[{key}] to g[b[{value}]")
            os.environ[key] = value

        if self.name == "sysadmin-repo-metadata":
            return

        if self.current_phase == "update":
            # Skip creating build dir in the update phase, to not confuse user if they just update sources.
            # And in the update phase, we do not set environment variables anyway.
            return

        build_dir = self.fullpath("build")
        if not os.path.exists(build_dir):
            Util.super_mkdir(build_dir)

        with open(self.fullpath("build") + "/kde-builder.env", "w") as f:
            f.write("# kate: syntax bash;\n")
            for key, value in self.env.items():
                f.write(f"{key}={value}\n")

    def prepend_environment_value(self, env_name: str, path_element: str) -> None:
        """
        Add the given library paths to the path already given in an environment variable.

        In addition, detected "system paths" are stripped to ensure
        that we don't inadvertently re-add a system path to be promoted over the
        custom code we're compiling (for instance, when a system Qt is used and
        installed to /usr).

        If the environment variable to be modified has already been queued using
        queue_environment_variable, then that (queued) value will be modified and
        will take effect with the next forked subprocess.

        Otherwise, the current environment variable value will be used, and then
        queued. Either way the current environment will be unmodified afterward.

        Args:
            env_name: The name of the environment variable to modify
            path_element: The value to be prepended to the current environment path. I.e. passing "/some/new/path" would set the value to "/some/new/path:/already/existing/path".
        """
        if env_name in self.env:
            cur_paths = self.env[env_name].split(":")
        elif env_name in os.environ:
            cur_paths = os.environ.get(env_name, "").split(":")
        else:
            cur_paths = []

        # pl2py: this is kde-builder specific code (not from kdesrc-build).
        # Some modules use python packages in their build process. For example, breeze-gtk uses python-cairo.
        # We want the build process to use system installed package rather than installed in virtual environment.
        # We remove the current virtual environment path from PATH, because Cmake FindPython3 module always considers PATH,
        # see https://cmake.org/cmake/help/latest/module/FindPython3.html
        # If user did not provide cmake options -DPython3_FIND_VIRTUALENV=STANDARD and -DPython3_FIND_UNVERSIONED_NAMES=FIRST,
        # they will be automatically added (see get_final_cmake_options()).
        if sys.prefix != sys.base_prefix and env_name == "PATH":
            if f"{sys.prefix}/bin" in cur_paths:
                logger_module.debug(f"\tRemoving python virtual environment path y[{sys.prefix}/bin] from y[PATH], to allow build process to find system python packages outside virtual environment.")
                cur_paths.remove(f"{sys.prefix}/bin")
            else:
                logger_module.debug(f"\tVirtual environment path y[{sys.prefix}/bin] was already removed from y[PATH].")

        # Filter out entries to add that are already in the environment from the system.
        if path_element in cur_paths:
            logger_module.debug(f"\tNot prepending y[{path_element}] to y[{env_name}] as it appears " + f"to already be defined in y[{env_name}].")

        if path_element not in cur_paths:
            join_list = [path_element] + cur_paths
        else:
            join_list = cur_paths

        env_value = ":".join(join_list)

        env_value = re.sub(r"^:*", "", env_value)
        env_value = re.sub(r":*$", "", env_value)  # Remove leading/trailing colons
        env_value = re.sub(r":+", ":", env_value)  # Remove duplicate colons

        self.queue_environment_variable(env_name, env_value)

    def set_error_logfile(self, logfile: str) -> None:
        """
        Mark a file as being the error log for a module. This also creates a symlink in the module log directory for easy viewing.

        Args:
            logfile: The filename in the log directory of the error log.
        """
        if not logfile:
            return

        logdir = self.get_log_dir()

        if self.has_option("#error-log-file"):
            logger_module.error(f"{self} already has error log set, tried to set to r[b[{logfile}]")
            return

        self.set_option("#error-log-file", f"{logdir}/{logfile}")
        logger_module.debug(f"Logfile for {self} is {logfile}")

        # Setup symlink in the module log directory pointing to the appropriate
        # file. Make sure to remove it first if it already exists.
        if os.path.islink(f"{logdir}/error.log"):
            os.unlink(f"{logdir}/error.log")

        if os.path.exists(f"{logdir}/error.log"):
            # Maybe it was a regular file?
            logger_module.error("r[b[ * Unable to create symlink to error log file]")
            return

        if os.path.exists(logdir):  # pl2py: in unit test, the log dir is not created. In perl symlinking just does not care and proceeds, but in python the exception is thrown. So we make this check.
            os.symlink(f"{logfile}", f"{logdir}/error.log")

    # @override
    def verify_option_value_type(self, option_name, option_value) -> None:
        """
        Ensure we are setting the correct type for value of option.
        """
        self.context.verify_option_value_type(option_name, option_value)
