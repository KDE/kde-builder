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

from kde_builder.debug import Debug
from kde_builder.debug import KBLogger
from kde_builder.kb_exception import ProgramError
from kde_builder.util.logged_subprocess import UtilLoggedSubprocess
from kde_builder.util.util import Util

if TYPE_CHECKING:
    from kde_builder.module.module import Module


logger_logged_cmd = KBLogger.getLogger("logged-command")
logger_buildsystem = KBLogger.getLogger("build-system")


class BuildSystem:
    """
    Base class for the various build systems.

    Includes built-in implementations of generic functions and supports hooks for subclasses to
    provide needed detailed functionality.

    ::

        buildsys = module.build_system()

        if not buildsys.has_toolchain():
            buildsys.prepare_module_build_environment()

        results = buildsys.build_internal()
    """

    def __init__(self, module: Module):
        self.module = module

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

    def _num_cores_to_use(self) -> int | None:
        """
        Return cpu cores limit to apply during the build.
        """
        num_cores: str = self.module.get_option("num-cores")

        # If set to empty, accept user's decision
        if num_cores == "":
            return None

        if num_cores == "auto":
            # If the build_system can manage it and the user doesn't care, that's OK too
            if self.supports_auto_parallelism():
                return None
            else:
                cores: int = self.auto_cores_number()
        else:
            cores = int(num_cores)
            # If user sets cores to something silly, set it to a failsafe.
            if cores <= 0:
                cores = 4

        return cores

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
        if module.get_option("clean-build"):
            return "the option clean-build was set"
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

    def required_programs(self) -> list[str]:
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

    def build_commands(self) -> list[str]:
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

    def supports_auto_parallelism(self) -> bool:
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
        num_cores = self._num_cores_to_use()

        if num_cores:
            # Prepend parallelism arg to allow user settings to override
            build_options = ["-j", str(num_cores)] + build_options

        return build_options

    def build_internal(self) -> bool:
        build_options = self.get_build_options()
        custom_targets = self.module.get_option("targets")
        if custom_targets:
            msg = "Building custom targets..."
            targets = custom_targets
        else:
            msg = "Compiling..."
            targets = None
        args = self.build_system_args(targets=targets, make_options=build_options)
        ret = self._run_build_system_command(
            message=msg,
            logname="build",
            args=args,
        )
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

        Returns:
            bool: False if unable to install, True otherwise.
        """
        module = self.module

        args = self.build_system_args(targets=["install"], prefix_options=cmd_prefix)
        ret = self._run_build_system_command(
            message=f"Installing g[{module}]",
            logname="install",
            args=args,
        )
        return ret

    def uninstall_internal(self, cmd_prefix: list[str]) -> bool:
        """
        Uninstall a previously installed module.

        All options passed are prefixed to the eventual command to be run.

        Returns:
            bool: False if unable to uninstall, True otherwise.
        """
        module = self.module
        module.unset_persistent_option("last-install-rev")
        args = self.build_system_args(targets=["uninstall"], prefix_options=cmd_prefix)
        ret = self._run_build_system_command(
            message=f"Uninstalling g[{module}]",
            logname="uninstall",
            args=args,
        )
        return ret

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

            # This variant of run_logged() runs the function prune_under_directory(builddir)
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

    def _build_system_args_common(
            self,
            prefix_options: list[str] | None = None,
        ) -> list[str]:
        """
        Prepare common arguments (i.e. valid for all build systems) for the build system command.

        Args:
            prefix_options: List of command line arguments to prefix *before* the
                make command, used for make-install-prefix support for e.g. sudo
        """
        module = self.module

        if prefix_options is None:
            prefix_options = []

        prefix_opts = prefix_options

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
        args = [*prefix_opts, *taskset_args]
        return args

    def build_system_args(
            self,
            targets: None | list[str],
            make_options: list[str] | None = None,
            prefix_options: list[str] | None = None,
        ) -> list[str]:
        """
        Prepare arguments for the build system command.

        Note that the make/ninja command is based on the results of the `build_commands()`
        function which should be overridden if necessary by subclasses. Each
        command should be the command name (i.e. no path).

        The first command name found which resolves to an executable on the
        system will be used.

        Args:
            make_options: List of command line arguments to pass to make/ninja.
            targets: None, or a valid build targets list e.g. ["install"].
            prefix_options: List of command line arguments to prefix *before* the
                make/ninja command, used for make-install-prefix support for e.g. sudo.
        """
        args = self._build_system_args_common(prefix_options)
        build_command = self.default_build_command()

        if not build_command:
            logger_buildsystem.error(f" r[b[*] Unable to find the g[{build_command}] executable!")
            return []

        args.append(build_command)
        if targets:
            args.extend(targets)

        if make_options is None:
            make_options = []
        args.extend(make_options)

        return args

    def _run_build_system_command(self, message: str, logname: str, args: list[str]) -> bool:
        """
        Run make/ninja/cmake and process the output in order to provide progress updates.

        Args:
            message: The message to display to the user while the build happens ("Compiling...", "Installing...", etc.).
            logname: The name of the log file to use (relative to the log directory).
            args: An array with the command and its arguments. i.e. ["command", "arg1", "arg2"]

        Returns:
            bool: True on success, False on failure.
        """
        if not args:
            return False

        module = self.module
        builddir = module.fullpath("build")
        result = False
        ctx = module.context

        # There are situations when we don't want progress output:
        # 1. If we're not printing to a terminal.
        # 2. When we're debugging (we'd interfere with debugging output).
        if not sys.stderr.isatty() or logger_logged_cmd.isEnabledFor(logging.DEBUG):
            logger_buildsystem.warning(f"\t{message}")

            result = Util.good_exitcode(Util.run_logged(module, logname, builddir, args))

            return result

        a_time = int(time.time())

        status_viewer = ctx.status_view
        status_viewer.status = Debug().colorize(f"\t{message}")
        status_viewer.current_project_phase = self.module.current_phase
        status_viewer.update()

        if logger_logged_cmd.level == logging.INFO and ctx.status_view.current_project_cur_progress == -1:
            # When user configured logged-command logger to not print the output of the command to console (i.e. logged-command level is higher than DEBUG), but still print the info of started and finished logged command,
            # (i.e. logged-command level is lower than WARNING), in other words, when logged-command level is INFO, the user will want to see the initial status message.
            # status_viewer lines are assumed to be overwritten by some line at the end. For example, the initial status line is "        Installing ark". It then is replaced by progress status line "66.7%   Installing ark".
            # And then finally is replaced with "        Installing ark succeeded (after 3 seconds)".
            # So to keep that initial line "        Installing ark", we need to add a new line after statusView prints its line and moves cursor to the beginning of line.
            print("\n", end="")

        warnings = 0

        def on_child_output(input_line):
            """Called in parent process."""
            if input_line is None:
                return

            percentage = None
            match = re.search(r"^\[\s*([0-9]+)%]", input_line)
            if match:
                percentage = int(match.group(1))

            if percentage:
                status_viewer.current_project_full_progress = 100
                status_viewer.set_progress(percentage)
            else:
                x, y = None, None
                match = re.search(r"^\[([0-9]+)/([0-9]+)] ", input_line)
                if match:
                    x, y = int(match.group(1)), int(match.group(2))

                if x and y:
                    # ninja-syntax
                    status_viewer.current_project_full_progress = y
                    status_viewer.set_progress(x)

            if "warning: " in input_line:
                nonlocal warnings
                warnings += 1

        cmd = UtilLoggedSubprocess().module(module).log_to(logname).chdir_to(builddir).set_command(args)

        cmd.child_output_handler = on_child_output

        try:
            exitcode = cmd.start()
            result = exitcode == 0
        except Exception as err:
            logger_buildsystem.error(f" r[b[*] Hit error building {module}: b[{err}]")
            result = False

        # Cleanup TTY output.
        a_time = Util.prettify_seconds(int(time.time()) - a_time)
        status = "g[b[succeeded]" if result else "r[b[failed]"
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
