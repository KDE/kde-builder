# SPDX-FileCopyrightText: 2012, 2015, 2018, 2021, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations
import os.path
import sys
import re
import time
import logging

from ..BuildException import BuildException
from ..Util.Util import Util
from ..Util.LoggedSubprocess import Util_LoggedSubprocess
from ..Debug import Debug, kbLogger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..Module.Module import Module
    from ..BuildContext import BuildContext

# use ksb::StatusView;

logger_logged_cmd = kbLogger.getLogger("logged-command")
logger_buildsystem = kbLogger.getLogger("build-system")


class BuildSystem:
    """
    Abstract base module for the various build systems, includes built-in
    implementations of generic functions and supports hooks for subclasses to
    provide needed detailed functionality.

    ::

        buildsys = module.buildSystem()  # auto-detects

        if not buildsys.hasToolchain():
            buildsys.prepareModuleBuildEnvironment()

        results = buildsys.buildInternal()

        if (results["was_successful"] and buildsys.needsInstalled()):
            buildsys.installInternal()
    """

    def __init__(self, module):
        self.module = module

        # This is simply the 'default' build system at this point, so options
        # intended for unique/bespoke build systems should be stripped from global
        # before being applied to a module.
        if not self.__class__.__name__ == "BuildSystem_KDECMake":
            self._maskGlobalBuildSystemOptions()

    def _maskGlobalBuildSystemOptions(self) -> None:
        """
        Removes or masks global build system-related options, so that they aren't
        accidentally picked up for use with our non-default build system.
        Module-specific options are left intact.
        """
        module = self.module
        ctx = module.buildContext()
        buildSystemOptions = ["cmake-options", "cmake-generator", "configure-flags", "custom-build-command", "cxxflags", "make-options", "run-tests", "use-clean-install"]

        for opt in buildSystemOptions:
            # If an option is present, and not set at module-level, it must be
            # global. Can't use getOption() method due to recursion.
            if ctx.options[opt] and not module.options.get(opt, None):
                module.options[opt] = ""

    def hasToolchain(self) -> bool:
        """
        Check if a (custom) toolchain is defined.
        If a build system is configured with a (custom) toolchain, it is assumed that
         - the user knows what they are doing, or
         - they are using an SDK that knows what it is about

        In either case, kde-builder will avoid touching the environment variables to
        give the custom configuration maximum "power" (including foot shooting power).
        """
        return False

    def module(self):
        return self.module

    def buildConstraints(self) -> dict:
        """
        Returns a dict holding the resource constraints to try to apply during the
        build. Buildsystems should apply the constraints they understand before
        running the build command.
        ::

            {
              "compute": OPTIONAL, if set a max number of CPU cores to use, or '1' if unable to tell
              # no other constraints supported
            }
        """
        cores = self.module.getOption("num-cores")

        # If set to empty, accept user's decision
        if not cores:
            return {}

        # If the buildsystem can manage it and the user doesn't care, that's OK too
        if self.supportsAutoParallelism() and cores == "auto":
            return {}

        max_cores = os.cpu_count()
        if not max_cores:
            max_cores = 1

        if cores == "auto" and max_cores > 1:
            cores = max_cores

        # If user sets cores to something silly, set it to a failsafe.
        if int(cores) <= 0:
            cores = 4

        return {"compute": cores}

    def needsRefreshed(self) -> str:
        """
        Function to determine if a given module needs to have the build system
        recreated from scratch.
        If so, it returns a non-empty string
        """
        Util.assert_isa(self, BuildSystem)
        module = self.module
        builddir = module.fullpath("build")
        confFileKey = self.configuredModuleFileName()

        if not os.path.exists(f"{builddir}"):
            return "the build directory doesn't exist"
        if os.path.exists(f"{builddir}/.refresh-me"):
            return "the last configure failed"  # see Module.pm
        if module.getOption("refresh-build"):
            return "the option refresh-build was set"
        if not os.path.exists(f"{builddir}/{confFileKey}"):
            return f"{builddir}/{confFileKey} is missing"
        return ""

    def prepareModuleBuildEnvironment(self, ctx: BuildContext, module: Module, prefix: str) -> None:
        """
        Called by the module being built before it runs its build/install process. Should
        set up any needed environment variables, build context settings, etc., in preparation
        for the build and install phases. Should take `hasToolchain()` into account here.
        """
        pass

    @staticmethod
    def needsInstalled() -> bool:
        """
        Returns true if the module should have make install run in order to be
        used, or false if installation is not required or possible.
        """
        return True

    @staticmethod
    def requiredPrograms() -> list[str]:
        """
        This should return a list of executable names that must be present to
        even bother attempting to use this build system. An empty list should be
        returned if there's no required programs.
        """
        return []

    @staticmethod
    def name() -> str:
        return "generic"

    @staticmethod
    def buildCommands() -> list[str]:
        """
        Returns a list of possible build commands to run, any one of which should
        be supported by the build system.
        """
        # Non Linux systems can sometimes fail to build when GNU Make would work,
        # so prefer GNU Make if present, otherwise try regular make.
        return ["gmake", "make"]

    def defaultBuildCommand(self) -> str:
        # Convert the path to an absolute path since I've encountered a sudo
        # that is apparently unable to guess.  Maybe it's better that it
        # doesn't guess anyways from a security point-of-view.
        buildCommand = next((bc for bc in self.buildCommands() if Util.locate_exe(bc)), None)
        if buildCommand is None:
            logger_buildsystem.warning(" y[*] Not found any of these executables: '" + "' '".join(self.buildCommands()) + "'. buildCommand will be undefined.")
        return buildCommand

    @staticmethod
    def supportsAutoParallelism() -> bool:
        """
        Returns a boolean value indicating if the buildsystem will automatically
        perform a parallel build without needing the -j command line option (or
        equivalent).

        If the build system returns false then that means auto-detection by
        kde-builder should be used to set the -j flag to something appropriate.

        The base implementation always returns false, this is meant to be overridden in
        subclasses.
        """
        return False

    def buildInternal(self, optionsName: str = "make-options") -> dict:
        """
        Return value style: dict to build results object (see safe_make)
        """

        # I removed the default value to num-cores but forgot to account for old
        # configs that needed a value for num-cores, as this is handled
        # automatically below. So filter out the naked -j for configs where what
        # previously might have been "-j 4" is now only "-j". See
        # https://invent.kde.org/sdk/kdesrc-build/-/issues/78
        optionVal = self.module.getOption(optionsName)

        # Look for -j being present but not being followed by digits
        if re.search(r"(^|[^a-zA-Z0-9_])-j$", optionVal) or re.search(r"(^|[^a-zA-Z_])-j(?! *[0-9]+)", optionVal):
            logger_buildsystem.warning(" y[b[*] Removing empty -j setting during build for y[b[" + str(self.module) + "]")
            optionVal = re.sub(r"(^|[^a-zA-Z_])-j *", r"\1", optionVal)  # Remove the -j entirely for now

        makeOptions = optionVal.split(" ")
        makeOptions = [el for el in makeOptions if el != ""]  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it.

        # Look for CPU core limits to enforce. This handles core limits for all
        # current build systems.
        buildConstraints = self.buildConstraints()
        numCores = buildConstraints.get("compute", None)

        if numCores:
            # Prepend parallelism arg to allow user settings to override
            makeOptions.insert(0, str(numCores))
            makeOptions.insert(0, "-j")

        return self.safe_make({
            "target": None,
            "message": "Compiling...",
            "make-options": makeOptions,
            "logbase": "build",
        })

    def configureInternal(self) -> bool:
        """
        Return value style: boolean
        """
        # It is possible to make it here if there's no source dir and if we're
        # pretending. If we're not actually pretending then this should be a
        # bug...
        if Debug().pretending():
            return True
        BuildException.croak_internal("We were not supposed to get to this point...")

    @staticmethod
    def configuredModuleFileName() -> str:
        """
        Returns name of file that should exist (relative to the module's build directory)
        if the module has been configured.
        """
        return "Makefile"

    def runTestsuite(self) -> bool:
        """
        Runs the testsuite for the given module.
        Returns true if a testsuite is present and all tests passed, false otherwise.
        """
        module = self.module
        logger_buildsystem.info(f"\ty[{module}] does not support the b[run-tests] option")
        return False

    def installInternal(self, cmdPrefix: list[str]) -> bool:
        """
        Used to install a module (that has already been built, tested, etc.)
        All options passed are prefixed to the eventual command to be run.
        Returns boolean false if unable to install, true otherwise.
        """
        module = self.module

        return self.safe_make({
            "target": "install",
            "message": f"Installing g[{module}]",
            "prefix-options": cmdPrefix,
        })["was_successful"]

    def uninstallInternal(self, cmdPrefix: list[str]) -> bool:
        """
        Used to uninstall a previously installed module.
        All options passed are prefixed to the eventual command to be run.
        Returns boolean false if unable to uninstall, true otherwise.
        """
        module = self.module
        module.unsetPersistentOption("last-install-rev")
        return self.safe_make({
            "target": "uninstall",
            "message": f"Uninstalling g[{module}]",
            "prefix-options": cmdPrefix,
        })["was_successful"]

    def cleanBuildSystem(self) -> int:
        """
        Function to clean the build system for the given module. Works by
        recursively deleting the directory and then recreating it.
        Returns:
             0 for failure, non-zero for success.
        """
        Util.assert_isa(self, BuildSystem)
        module = self.module
        srcdir = module.fullpath("source")
        builddir = module.fullpath("build")

        if Debug().pretending():
            logger_buildsystem.pretend(f"\tWould have cleaned build system for g[{module}]")
            return 1

        # Use an existing directory
        if os.path.exists(builddir) and builddir != srcdir:
            logger_buildsystem.info(f"\tRemoving files in build directory for g[{module}]")

            clean_promise = Util.prune_under_directory_p(module, builddir)
            result = Util.await_result(clean_promise)

            # This variant of log_command runs the sub prune_under_directory($builddir)
            # in a forked child, so that we can log its output.
            if not result:
                logger_buildsystem.error(f" r[b[*]\tFailed to clean build directory.  Verify the permissions are correct.")
                return 0  # False for this function.

            module.unsetPersistentOption("last-build-rev")
            # keep last-install-rev since that tracks the install dir.

            # Let users know we're done so they don't wonder why rm -rf is taking so
            # long and oh yeah, why's my HD so active?...
            logger_buildsystem.info("\tOld build system cleaned, starting new build system.")
        elif not Util.super_mkdir(builddir):
            logger_buildsystem.error(f"\tUnable to create directory r[{builddir}].")
            return 0
        return 1

    @staticmethod
    def needsBuilddirHack() -> bool:
        return False  # By default all build systems are assumed to be sane

    def createBuildSystem(self) -> Promise:
        """
        Creates the build directory for the associated module, and handles
        pre-configure setup that might be necessary to permit the build to complete
        from the build directory.

        Returns:
             A promise that resolves to a boolean result value (true == success)
        """
        Util.assert_isa(self, BuildSystem)
        module = self.module
        builddir = module.fullpath("build")
        srcdir = module.fullpath("source")

        if not os.path.exists(f"{builddir}") and not Util.super_mkdir(f"{builddir}"):
            logger_buildsystem.error(f"\tUnable to create build directory for r[{module}]!!")
            return Promise.resolve(0)

        if builddir != srcdir and self.needsBuilddirHack():
            def func(result):
                if not result:
                    logger_buildsystem.error(f"\tUnable to setup symlinked build directory for r[{module}]!!")
                return result

            promise = Util.safe_lndir_p(srcdir, builddir).then(func)
            return promise

        return Promise.resolve(1)

    def safe_make(self, optsRef: dict) -> dict:
        """
        Function to run the build command with the arguments given by the
        passed dict, laid out as:
        ::

            {
               target         : None, or a valid build target e.g. 'install',
               message        : 'Compiling.../Installing.../etc.'
               make-options   : [ list of command line arguments to pass to make. See
                                   make-options ],
               prefix-options : [ list of command line arguments to prefix *before* the
                                   make command, used for make-install-prefix support for
                                   e.g. sudo ],
               logbase        : 'base-log-filename',
            }

        target and message are required. logbase is required if target is left
        undefined, but otherwise defaults to the same value as target.

        Note that the make command is based on the results of the "buildCommands"
        function which should be overridden if necessary by subclasses. Each
        command should be the command name (i.e. no path). The user may override
        the command used (for build only) by using the "custom-build-command"
        option.

        The first command name found which resolves to an executable on the
        system will be used, if no command this function will fail.

        Returns a dict:
        ::

            {
              was_successful : $bool, (if successful)
              warnings       : $int,  (num of warnings, in [0..INT_MAX])
              work_done      : $bool, (true if the make command had work to do, may be needlessly set)
            }
        """
        Util.assert_isa(self, BuildSystem)
        module = self.module

        commandToUse = module.getOption("custom-build-command")
        buildCommand = None
        buildCommandLine = []

        # Check for custom user command. We support command line options being
        # passed to the command as well.
        if commandToUse:
            buildCommand, *buildCommandLine = Util.split_quoted_on_whitespace(commandToUse)
            commandToUse = buildCommand  # Don't need whole cmdline in any errors.
            buildCommand = Util.locate_exe(buildCommand)
        else:
            # command line options passed in optsRef
            commandToUse = buildCommand = self.defaultBuildCommand()

        if not buildCommand:
            logger_buildsystem.error(f" r[b[*] Unable to find the g[{commandToUse}] executable!")
            return {"was_successful": 0}

        # Make it prettier if pretending (Remove leading directories).
        if Debug().pretending():
            buildCommand = re.sub(r"^/.*/", "", buildCommand)

        # Simplify code by forcing lists to exist.
        if "prefix-options" not in optsRef:
            optsRef["prefix-options"] = []
        if "make-options" not in optsRef:
            optsRef["make-options"] = []

        prefixOpts = optsRef["prefix-options"]

        # If using sudo ensure that it doesn't wait on tty, but tries to read from
        # stdin (which should fail as we redirect that from /dev/null)
        if prefixOpts and prefixOpts[0] == "sudo" and [opt for opt in prefixOpts if opt != "-S"]:
            prefixOpts.insert(1, "-S")  # Add -S right after 'sudo'

        # Assemble arguments
        args = [*prefixOpts, buildCommand, *buildCommandLine]
        if optsRef["target"]:
            args.append(optsRef["target"])
        args.extend(optsRef["make-options"])

        logname = optsRef.get("logbase", optsRef.get("logfile", optsRef.get("target", "")))  # pl2py: if all of these are undefined, logname remains undef in perl. But undef in perl becomes empty string when stringified.

        builddir = module.fullpath("build")
        builddir = re.sub(r"/*$", "", builddir)  # Remove trailing /

        Util.p_chdir(builddir)

        return self._runBuildCommand(optsRef["message"], logname, args)

    def _runBuildCommand(self, message: str, filename: str, argRef: list[str]) -> dict:
        """
        Function to run make and process the build process output in order to
        provide completion updates. This procedure takes the same arguments as
        log_command() (described here as well), except that the callback argument
        is not used.

        Parameters:
            message: The message to display to the user while the build happens.
            filename: The name of the log file to use (relative to the log directory).
            argRef: An array with the command and its arguments. i.e. ['command', 'arg1', 'arg2']

        Returns:
             Dict as defined by safe_make
        """

        module = self.module
        builddir = module.fullpath("build")
        resultRef = {"was_successful": 0}
        ctx = module.buildContext()

        # There are situations when we don't want progress output:
        # 1. If we're not printing to a terminal.
        # 2. When we're debugging (we'd interfere with debugging output).
        if not sys.stderr.isatty() or logger_logged_cmd.isEnabledFor(logging.DEBUG):
            logger_buildsystem.warning(f"\t{message}")

            resultRef["was_successful"] = Util.good_exitcode(Util.run_logged(module, filename, builddir, argRef))

            # pl2py: this was not in kdesrc-build, but without it, the behavior is different when debugging vs when not debugging.
            # When the module was built successfully, and you were using --debug, then you will get the message:
            #  "No changes from build, skipping install"
            # from Module.build() method. This is due to "work_done" key was missing in returned dict when debugging.
            # So I (Andrew Shark) will make these scenarios behave similarly disregarding if debugging or not.
            resultRef["work_done"] = 1

            return resultRef

        a_time = int(time.time())

        statusViewer = ctx.statusViewer()
        statusViewer.setStatus(f"\t{message}")
        statusViewer.update()

        if logger_logged_cmd.level == logging.INFO and ctx.statusViewer().cur_progress == -1:
            # When user configured logged-command logger to not print the output of the command to console (i.e. logged-command level is higher than DEBUG), but still print the info of started and finished logged command,
            # (i.e. logged-command level is lower than WARNING), in other words, when logged-command level is INFO, the user will want to see the initial status message.
            # statusViewer lines are assumed to be overwritten by some line at the end. For example, the initial status line is "        Installing ark". It then is replaced by progress status line "66.7%   Installing ark".
            # And then finally is replaced with "        Installing ark succeeded (after 3 seconds)".
            # So to keep that initial line "        Installing ark", we need to add a new line after statusView prints its line and moves cursor to the beginning of line.
            print("\n", end="")

        # TODO More details
        warnings = 0
        workDoneFlag = 1

        def log_command_callback(input_line):
            if input_line is None:
                return

            percentage = None
            match = re.search(r"^\[\s*([0-9]+)%]", input_line)
            if match:
                percentage = int(match.group(1))

            if percentage:
                statusViewer.setProgressTotal(100)
                statusViewer.setProgress(percentage)
            else:
                x, y = None, None
                match = re.search(r"^\[([0-9]+)/([0-9]+)] ", input_line)
                if match:
                    x, y = int(match.group(1)), int(match.group(2))

                if x and y:
                    # ninja-syntax
                    statusViewer.setProgressTotal(y)
                    statusViewer.setProgress(x)

            # pl2py: was commented there
            # see sdk/kdesrc-build#107
            # breaks compile if there is nothing to build but just stuff to install after changes
            # $workDoneFlag = 0 if $input =~ /^ninja: no work to do/;

            if "warning: " in input_line:
                nonlocal warnings
                warnings += 1

        cmd = Util_LoggedSubprocess().module(module).log_to(filename).chdir_to(builddir).set_command(argRef)

        def on_child_output(line):
            # called in parent!
            log_command_callback(line)

        cmd.on({"child_output": on_child_output})

        def _then(exitcode):
            nonlocal resultRef
            resultRef = {
                "was_successful": exitcode == 0,
                "warnings": warnings,
                "work_done": workDoneFlag,
            }

        def _catch(err):
            logger_buildsystem.error(f" r[b[*] Hit error building {module}: b[{err}]")
            resultRef["was_successful"] = 0

        promise = cmd.start().then(_then).catch(_catch)

        Promise.wait(promise)

        # Cleanup TTY output.
        a_time = Util.prettify_seconds(int(time.time()) - a_time)
        status = "g[b[succeeded]" if resultRef["was_successful"] else "r[b[failed]"
        statusViewer.releaseTTY(f"\t{message} {status} (after {a_time})\n")

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
            self.module.setPersistentOption("last-compile-warnings", warnings)

        return resultRef
