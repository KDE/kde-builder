# SPDX-FileCopyrightText: 2012, 2015, 2018, 2021, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import logging
import os.path
import re
import sys
import time
from typing import TYPE_CHECKING

from ..kb_exception import ProgramError
from ..debug import Debug
from ..debug import KBLogger
from ..util.logged_subprocess import UtilLoggedSubprocess
from ..util.util import Util

if TYPE_CHECKING:
    from ..module.module import Module


logger_logged_cmd = KBLogger.getLogger("logged-command")
logger_buildsystem = KBLogger.getLogger("build-system")


class BuildSystem:
    """
    Base class for the various build systems.

    Includes built-in implementations of generic functions and supports hooks for subclasses to
    provide needed detailed functionality.

    ::

        buildsys = module.build_system()  # auto-detects

        if not buildsys.has_toolchain():
            buildsys.prepare_module_build_environment()

        results = buildsys.build_internal()

        if (results["was_successful"] and buildsys.needs_installed()):
            buildsys.install_internal()
    """

    def __init__(self, module: Module):
        self.module = module

        # This is simply the "default" build system at this point, so options
        # intended for unique/bespoke build systems should be stripped from global
        # before being applied to a module.
        if not self.__class__.__name__ == "BuildSystemKDECMake":
            self._mask_global_build_system_options()

    def _mask_global_build_system_options(self) -> None:
        """
        Remove or mask global build system-related options.

        This is done so that they aren't accidentally picked up for use with our non-default build system.
        Module-specific options are left intact.
        """
        module = self.module
        ctx = module.context
        build_system_options = ["cmake-options", "cmake-generator", "configure-flags", "custom-build-command", "cxxflags", "make-options", "run-tests", "use-clean-install"]

        for opt in build_system_options:
            # If an option is present, and not set at module-level, it must be
            # global. Can't use get_option() method due to recursion.
            if ctx.options[opt] and not module.options.get(opt, None):
                module.options[opt] = ""

    def has_toolchain(self) -> bool:
        """
        Check if a (custom) toolchain is defined.

        If a build system is configured with a (custom) toolchain, it is assumed that
         - the user knows what they are doing, or
         - they are using an SDK that knows what it is about

        In either case, kde-builder will avoid touching the environment variables to
        give the custom configuration maximum "power" (including foot shooting power).
        """
        return False

    @staticmethod
    def auto_cores_number() -> int:
        """
        Get the number of cores to use if user set their num-cores or taskset-cpu-list to auto.
        """
        max_cores = os.cpu_count()
        if max_cores is None or max_cores <= 1:
            return 1
        return int(max_cores * 0.8)

    def build_constraints(self) -> dict[str, int]:
        """
        Return a dict holding the resource constraints to try to apply during the build.

        Buildsystems should apply the constraints they understand before
        running the build command.
        ::

            {
              "compute": OPTIONAL, if set a max number of CPU cores to use, or "1" if unable to tell
              # no other constraints supported
            }
        """
        cores = self.module.get_option("num-cores")

        # If set to empty, accept user's decision
        if cores == "":
            return {}

        if cores == "auto":
            # If the build_system can manage it and the user doesn't care, that's OK too
            if self.supports_auto_parallelism():
                return {}
            else:
                cores = self.auto_cores_number()

        # If user sets cores to something silly, set it to a failsafe.
        if int(cores) <= 0:
            cores = 4

        return {"compute": cores}

    def needs_refreshed(self) -> str:
        """
        Determine if a given module needs to have the build system recreated from scratch.

        If so, it returns a non-empty string.
        """
        module = self.module
        builddir = module.fullpath("build")
        conf_file_key = self.configured_module_file_name()

        if not os.path.exists(f"{builddir}"):
            return "the build directory doesn't exist"
        if os.path.exists(f"{builddir}/.refresh-me"):
            return "the last configure failed"  # see module.py
        if module.get_option("refresh-build"):
            return "the option refresh-build was set"
        if not os.path.exists(f"{builddir}/{conf_file_key}"):
            return f"{builddir}/{conf_file_key} is missing"
        return ""

    def prepare_module_build_environment(self) -> None:
        """
        Set up any needed environment variables, build context settings, etc., in preparation for the build and install phases.

        Called by the module being built before it runs its build/install process.
        Should take `has_toolchain()` into account here.
        """
        pass

    @staticmethod
    def needs_installed() -> bool:
        """
        Return true if the module should have make install run in order to be used, or false if installation is not required or possible.
        """
        return True

    @staticmethod
    def required_programs() -> list[str]:
        """
        Return a list of executable names that must be present to even bother attempting to use this build system.

        An empty list should be returned if there's no required programs.
        """
        return []

    @staticmethod
    def name() -> str:
        return "generic"

    def build_options_name(self) -> str:
        return "make-options"

    @staticmethod
    def build_commands() -> list[str]:
        """
        Return a list of possible build commands to run, any one of which should be supported by the build system.
        """
        # Non Linux systems can sometimes fail to build when GNU Make would work,
        # so prefer GNU Make if present, otherwise try regular make.
        return ["gmake", "make"]

    def default_build_command(self) -> str:
        # Convert the path to an absolute path since I've encountered a sudo
        # that is apparently unable to guess.  Maybe it's better that it
        # doesn't guess anyways from a security point-of-view.
        build_command = next((bc for bc in self.build_commands() if Util.locate_exe(bc)), None)
        if build_command is None:
            logger_buildsystem.warning(" y[*] Not found any of these executables: '" + "' '".join(self.build_commands()) + "'. build_command will be undefined.")
        return build_command

    @staticmethod
    def supports_auto_parallelism() -> bool:
        """
        Indicate if the build_system will automatically perform a parallel build without needing the -j command line option (or equivalent).

        If the build system returns false then that means auto-detection by
        kde-builder should be used to set the -j flag to something appropriate.

        The base implementation always returns false, this is meant to be overridden in
        subclasses.
        """
        return False

    def get_build_options(self) -> list[str]:
        options_name = self.build_options_name()
        assert options_name in ["make-options", "ninja-options"]

        # I removed the default value to num-cores but forgot to account for old
        # configs that needed a value for num-cores, as this is handled
        # automatically below. So filter out the naked -j for configs where what
        # previously might have been "-j 4" is now only "-j". See
        # https://invent.kde.org/sdk/kdesrc-build/-/issues/78
        option_val = self.module.get_option(options_name)

        # Look for -j being present but not being followed by digits
        if re.search(r"(^|[^a-zA-Z0-9_])-j$", option_val) or re.search(r"(^|[^a-zA-Z_])-j(?! *[0-9]+)", option_val):
            logger_buildsystem.warning(" y[b[*] Removing empty -j setting during build for y[b[" + str(self.module) + "]")
            option_val = re.sub(r"(^|[^a-zA-Z_])-j *", r"\1", option_val)  # Remove the -j entirely for now

        build_options = option_val.split(" ")
        build_options = [el for el in build_options if el != ""]  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it.

        # Look for CPU core limits to enforce. This handles core limits for all current build systems.
        build_constraints = self.build_constraints()
        num_cores = build_constraints.get("compute", None)

        if num_cores:
            # Prepend parallelism arg to allow user settings to override
            build_options = ["-j", str(num_cores)] + build_options

        return build_options

    def build_internal(self) -> dict:
        """
        Return dict with build results (see safe_make).
        """
        build_options = self.get_build_options()
        ret = self.safe_make({
            "target": None,
            "message": "Compiling...",
            "make-options": build_options,
            "logbase": "build",
        })
        return ret

    def configure_internal(self) -> bool:
        # It is possible to make it here if there's no source dir and if we're
        # pretending. If we're not actually pretending then this should be a
        # bug...
        if Debug().pretending():
            return True
        raise ProgramError("We were not supposed to get to this point...")

    @staticmethod
    def configured_module_file_name() -> str:
        """
        Return name of file that should exist (relative to the module's build directory) if the module has been configured.
        """
        return "Makefile"

    def run_testsuite(self) -> False:
        """
        Run the testsuite for the given module.

        Returns true if a testsuite is present and all tests passed, false otherwise.
        """
        module = self.module
        logger_buildsystem.info(f"\ty[{module}] does not support the b[run-tests] option")
        return False

    def install_internal(self, cmd_prefix: list[str]) -> bool:
        """
        Install a module (that has already been built, tested, etc.).

        All options passed are prefixed to the eventual command to be run.
        Returns boolean false if unable to install, true otherwise.
        """
        module = self.module

        return self.safe_make({
            "target": "install",
            "message": f"Installing g[{module}]",
            "prefix-options": cmd_prefix,
        })["was_successful"]

    def uninstall_internal(self, cmd_prefix: list[str]) -> bool:
        """
        Uninstall a previously installed module.

        All options passed are prefixed to the eventual command to be run.
        Returns boolean false if unable to uninstall, true otherwise.
        """
        module = self.module
        module.unset_persistent_option("last-install-rev")
        return self.safe_make({
            "target": "uninstall",
            "message": f"Uninstalling g[{module}]",
            "prefix-options": cmd_prefix,
        })["was_successful"]

    def clean_build_system(self) -> int:
        """
        Clean the build system for the given module.

        Works by recursively deleting the directory and then recreating it.

        Returns:
             0 for failure, non-zero for success.
        """
        module = self.module
        srcdir = module.fullpath("source")
        builddir = module.fullpath("build")

        if Debug().pretending():
            logger_buildsystem.debug(f"\tWould have cleaned build system for g[{module}]")
            return 1

        # Use an existing directory
        if os.path.exists(builddir) and builddir != srcdir:
            logger_buildsystem.info(f"\tRemoving files in build directory for g[{module}]")

            result = Util.prune_under_directory(module, builddir)

            # This variant of log_command runs the sub prune_under_directory($builddir)
            # in a forked child, so that we can log its output.
            if not result:
                logger_buildsystem.error(" r[b[*]\tFailed to clean build directory. Verify the permissions are correct.")
                return 0  # False for this function.

            module.unset_persistent_option("last-build-rev")
            # keep last-install-rev since that tracks the install dir.

            # Let users know we're done so they don't wonder why rm -rf is taking so
            # long and oh yeah, why's my HD so active?...
            logger_buildsystem.info("\tOld build system cleaned, starting new build system.")
        elif not Util.super_mkdir(builddir):
            logger_buildsystem.error(f"\tUnable to create directory r[{builddir}].")
            return 0
        return 1

    def create_build_system(self) -> int:
        """
        Create the build directory for the associated module, and handle pre-configure setup.

        Pre-configure setup might be necessary to permit the build to complete from the build directory.

        Returns:
             1 on success, 0 on failure.
        """
        module = self.module
        builddir = module.fullpath("build")

        if not os.path.exists(f"{builddir}") and not Util.super_mkdir(f"{builddir}"):
            logger_buildsystem.error(f"\tUnable to create build directory for r[{module}]!!")
            return 0

        return 1

    def safe_make(self, opts: dict) -> dict:
        """
        Run the build command with the arguments given by the passed dict.

        Passed dict is laid out as:
        ::

            {
               target         : None, or a valid build target e.g. "install",
               message        : "Compiling.../Installing.../etc."
               make-options   : [ list of command line arguments to pass to make. See
                                   make-options ],
               prefix-options : [ list of command line arguments to prefix *before* the
                                   make command, used for make-install-prefix support for
                                   e.g. sudo ],
               logbase        : "base-log-filename",
            }

        target and message are required. logbase is required if target is left
        undefined, but otherwise defaults to the same value as target.

        Note that the make command is based on the results of the "build_commands"
        function which should be overridden if necessary by subclasses. Each
        command should be the command name (i.e. no path). The user may override
        the command used (for build only) by using the "custom-build-command"
        option.

        The first command name found which resolves to an executable on the
        system will be used, if no command this function will fail.

        Returns a dict:
        ::

            {
              was_successful : bool  # if successful
              warnings       : int  # num of warnings
              work_done      : bool  # true if the make command had work to do, may be needlessly set
            }
        """
        module = self.module

        command_to_use = module.get_option("custom-build-command")
        build_command = None
        build_command_line = []

        # Check for custom user command. We support command line options being
        # passed to the command as well.
        if command_to_use:
            build_command, *build_command_line = Util.split_quoted_on_whitespace(command_to_use)
            command_to_use = build_command  # Don't need whole cmdline in any errors.
            build_command = Util.locate_exe(build_command)
        else:
            # command line options passed in opts
            command_to_use = build_command = self.default_build_command()

        if not build_command:
            logger_buildsystem.error(f" r[b[*] Unable to find the g[{command_to_use}] executable!")
            return {"was_successful": 0}

        # Make it prettier if pretending (Remove leading directories).
        if Debug().pretending():
            build_command = re.sub(r"^/.*/", "", build_command)

        # Simplify code by forcing lists to exist.
        if "prefix-options" not in opts:
            opts["prefix-options"] = []
        if "make-options" not in opts:
            opts["make-options"] = []

        prefix_opts = opts["prefix-options"]

        taskset_args = []
        taskset_opt = module.get_option("taskset-cpu-list")

        if taskset_opt:
            arg_str = taskset_opt
            if taskset_opt == "auto":
                auto_num = self.auto_cores_number()
                arg_str = f"0-{auto_num}"

            taskset_args = ["taskset", "--cpu-list", arg_str]

        # If using sudo ensure that it doesn't wait on tty, but tries to read from
        # stdin (which should fail as we redirect that from /dev/null)
        if prefix_opts and prefix_opts[0] == "sudo" and [opt for opt in prefix_opts if opt != "-S"]:
            prefix_opts.insert(1, "-S")  # Add -S right after "sudo"

        # Assemble arguments
        args = [*prefix_opts, *taskset_args, build_command, *build_command_line]
        if opts["target"]:
            args.append(opts["target"])
        args.extend(opts["make-options"])

        logname = opts.get("logbase", opts.get("logfile", opts.get("target", "")))  # pl2py: if all of these are undefined, logname remains undef in perl. But undef in perl becomes empty string when stringified.

        builddir = module.fullpath("build")
        builddir = re.sub(r"/*$", "", builddir)  # Remove trailing /

        Util.p_chdir(builddir)

        return self._run_build_command(opts["message"], logname, args)

    def _run_build_command(self, message: str, filename: str, args: list[str]) -> dict:
        """
        Run make and process the build process output in order to provide completion updates.

        This procedure takes the same arguments as
        log_command() (described here as well), except that the callback argument
        is not used.

        Args:
            message: The message to display to the user while the build happens.
            filename: The name of the log file to use (relative to the log directory).
            args: An array with the command and its arguments. i.e. ["command", "arg1", "arg2"]

        Returns:
             Dict as defined by safe_make
        """
        module = self.module
        builddir = module.fullpath("build")
        result = {"was_successful": 0}
        ctx = module.context

        # There are situations when we don't want progress output:
        # 1. If we're not printing to a terminal.
        # 2. When we're debugging (we'd interfere with debugging output).
        if not sys.stderr.isatty() or logger_logged_cmd.isEnabledFor(logging.DEBUG):
            logger_buildsystem.warning(f"\t{message}")

            result["was_successful"] = Util.good_exitcode(Util.run_logged(module, filename, builddir, args))

            # pl2py: this was not in kdesrc-build, but without it, the behavior is different when debugging vs when not debugging.
            # When the module was built successfully, and you were using --debug, then you will get the message:
            #  "No changes from build, skipping install"
            # from Module.build() method. This is due to "work_done" key was missing in returned dict when debugging.
            # So I (Andrew Shark) will make these scenarios behave similarly disregarding if debugging or not.
            result["work_done"] = 1

            return result

        a_time = int(time.time())

        status_viewer = ctx.status_view
        status_viewer.set_status(f"\t{message}")
        status_viewer.update()

        if logger_logged_cmd.level == logging.INFO and ctx.status_view.cur_progress == -1:
            # When user configured logged-command logger to not print the output of the command to console (i.e. logged-command level is higher than DEBUG), but still print the info of started and finished logged command,
            # (i.e. logged-command level is lower than WARNING), in other words, when logged-command level is INFO, the user will want to see the initial status message.
            # status_viewer lines are assumed to be overwritten by some line at the end. For example, the initial status line is "        Installing ark". It then is replaced by progress status line "66.7%   Installing ark".
            # And then finally is replaced with "        Installing ark succeeded (after 3 seconds)".
            # So to keep that initial line "        Installing ark", we need to add a new line after statusView prints its line and moves cursor to the beginning of line.
            print("\n", end="")

        # TODO More details
        warnings = 0
        work_done_flag = 1

        def log_command_callback(input_line):
            if input_line is None:
                return

            percentage = None
            match = re.search(r"^\[\s*([0-9]+)%]", input_line)
            if match:
                percentage = int(match.group(1))

            if percentage:
                status_viewer.set_progress_total(100)
                status_viewer.set_progress(percentage)
            else:
                x, y = None, None
                match = re.search(r"^\[([0-9]+)/([0-9]+)] ", input_line)
                if match:
                    x, y = int(match.group(1)), int(match.group(2))

                if x and y:
                    # ninja-syntax
                    status_viewer.set_progress_total(y)
                    status_viewer.set_progress(x)

            # pl2py: was commented there
            # see sdk/kdesrc-build#107
            # breaks compile if there is nothing to build but just stuff to install after changes
            # $work_done_flag = 0 if $input =~ /^ninja: no work to do/;

            if "warning: " in input_line:
                nonlocal warnings
                warnings += 1

        cmd = UtilLoggedSubprocess().module(module).log_to(filename).chdir_to(builddir).set_command(args)

        def on_child_output(line):
            # called in parent!
            log_command_callback(line)

        cmd.on({"child_output": on_child_output})

        try:
            exitcode = cmd.start()
            result = {
                "was_successful": exitcode == 0,
                "warnings": warnings,
                "work_done": work_done_flag,
            }
        except Exception as err:
            logger_buildsystem.error(f" r[b[*] Hit error building {module}: b[{err}]")
            result["was_successful"] = 0

        # Cleanup TTY output.
        a_time = Util.prettify_seconds(int(time.time()) - a_time)
        status = "g[b[succeeded]" if result["was_successful"] else "r[b[failed]"
        status_viewer.release_tty(f"\t{message} {status} (after {a_time})\n")

        if warnings:
            if warnings < 3:
                count = 1
            elif warnings < 10:
                count = 2
            elif warnings < 30:
                count = 3
            else:
                count = 4

            msg = f"""{"-" * count} b[y[{warnings}] {"-" * count}"""
            logger_buildsystem.warning(f"\tNote: {msg} compile warnings")
            self.module.set_persistent_option("last-compile-warnings", warnings)

        return result
