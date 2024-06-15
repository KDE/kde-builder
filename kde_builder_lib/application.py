# SPDX-FileCopyrightText: 2013, 2014, 2015, 2016, 2018, 2019, 2020, 2021, 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import atexit
import fileinput
import glob
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import textwrap
from time import sleep
from time import time
import traceback
from typing import Callable
from typing import NoReturn

from kde_builder_lib.build_exception import BuildException
from kde_builder_lib.build_exception import BuildException_Config
from .build_context import BuildContext
from .build_system.qmake5 import BuildSystem_QMake5
from .cmd_line import Cmdline
from .debug import Debug
from .debug import kbLogger
from .debug_order_hints import DebugOrderHints
from .dependency_resolver import DependencyResolver
from .module.module import Module
from .module_resolver import ModuleResolver
from .module_set.kde_projects import ModuleSet_KDEProjects
from .module_set.module_set import ModuleSet
from .module_set.qt5 import ModuleSet_Qt5
from .options_base import OptionsBase
from .recursive_fh import RecursiveFH
from .start_program import StartProgram
from .task_manager import TaskManager
from .updater.updater import Updater
from .util.util import Util

logger_var_subst = kbLogger.getLogger("variables_substitution")
logger_app = kbLogger.getLogger("application")


class Application:
    """
    Contains the application-layer logic (e.g. creating a build context, reading
    options, parsing command-line, etc.). Most of the specific tasks are delegated
    to supporting classes, this class primarily does the orchestration that goes
    from reading command line options, choosing which modules to build, overseeing
    the build process, and reporting the results to the user.

    Examples:
    ::

        app = kde_builder_lib.Application.Application(sys.argv)
        result = app.runAllModulePhases()
        app.finish(result)
    """

    # We use a named remote to make some git commands work that don't accept the full path.
    KDE_PROJECT_ID = "kde-projects"  # git-repository-base for sysadmin/repo-metadata. The value is determined as "kde:$repoPath.git", where $repoParh is read from yaml metadata file for each module.
    QT_PROJECT_ID = "qt-projects"  # git-repository-base for qt.io Git repo. The value is set as "https://invent.kde.org/qt/qt/qt5.git" when the module set transforms to qt5 super module.

    def __init__(self, options: list[str]):
        self.context = BuildContext()

        self.metadata_module = None
        self.run_mode = "build"
        self.modules = None
        self.module_factory = None  # ref to sub that makes a new Module. # See generateModuleList
        self._base_pid = os.getpid()  # See finish()

        # Default to colorized output if sending to TTY
        Debug().setColorfulOutput(True if sys.stdout.isatty() else False)

        workLoad = self.generateModuleList(options)
        if not workLoad.get("build", None):
            if len(options) == 2 and options[0] == "--metadata-only" and options[1] == "--metadata-only":  # Exactly this command line from FirstRun
                return  # Avoid exit, we can continue in the --install-distro-packages in FirstRun
                # Todo: Currently we still need to exit when normal use like `kde-builder --metadata-only`, because otherwise script tries to proceed with "my $result = $app->runAllModulePhases();". Fix it.
            print("No modules to build, exiting.\n")
            exit(0)  # todo When --metadata-only was used and $self->context->{rcFile} is not /fake/dummy_config, before exiting, it should store persistent option for last-metadata-update.

        self.modules: list[Module] = workLoad["selectedModules"]
        self.workLoad = workLoad
        self.context.setupOperatingEnvironment()  # i.e. niceness, ulimits, etc.

        # After this call, we must run the finish() method
        # to cleanly complete process execution.
        if not Debug().pretending() and not self.context.takeLock():  # todo move takeLock to the place before the actual work, not when creating an instance of Application.
            print(f"{sys.argv[0]} is already running!\n")
            exit(1)  # Don't finish(), it's not our lockfile!!

        # os.setpgrp()  # Create our own process group, its id will be equal to self._base_pid. Needed to send signal to the whole group when exiting.
        self._already_got_signal = False  # Used to prevent secondary invocation of signal handler

        # Install signal handlers to ensure that the lockfile gets closed.
        def signal_handler(signum, frame):
            # import setproctitle
            if self._already_got_signal:
                # if not os.getpid() == self._base_pid:
                #     print(f"\nWarning: Signal {signal.strsignal(signum)} ({signal.Signals(signum).name}) received in main process {os.getpid()} ({setproctitle.getproctitle()}), but already received it, ignoring.")
                # else:
                #     print(f"\nWarning: Signal {signal.strsignal(signum)} ({signal.Signals(signum).name}) received in subprocess {os.getpid()} ({setproctitle.getproctitle()}), but already received it, ignoring.")
                return

            self._already_got_signal = True

            if not os.getpid() == self._base_pid:
                # print(f"\Signal {signal.strsignal(signum)} ({signal.Signals(signum).name}) received in subprocess {os.getpid()} ({setproctitle.getproctitle()}).")
                sys.exit(signum)
            else:
                print(f"\nSignal {signal.strsignal(signum)} ({signal.Signals(signum).name}) received, terminating.")
                self._already_got_signal = True
                signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignoring the SIGINT signal from now, so when we send it to group, it will be ignored in current process.
                os.killpg(self._base_pid, signal.SIGINT)  # Sending SIGINT to all processes in our process group.
                # Even after we sent it to all processes in group, the updater process sometimes got hanged with futex_wait_queue.
                # As a crutch for now, will send this signal again, after a bit of waiting.
                sleep(0.3)
                os.killpg(self._base_pid, signal.SIGINT)  # Sending it again.
                atexit.unregister(self.finish)  # Remove their finish, doin' it manually
                self.finish(5)

        self._installSignalHandlers(signal_handler)

    @staticmethod
    def _yieldModuleDependencyTreeEntry(nodeInfo: dict, module: Module, context: dict) -> None:
        depth = nodeInfo["depth"]
        index = nodeInfo["idx"]
        count = nodeInfo["count"]
        build = nodeInfo["build"]
        currentItem = nodeInfo["currentItem"]
        currentBranch = nodeInfo["currentBranch"]
        parentItem = nodeInfo["parentItem"]
        parentBranch = nodeInfo["parentBranch"]

        buildStatus = "built" if build else "not built"
        statusInfo = f"({buildStatus}: {currentBranch})" if currentBranch else f"({buildStatus})"

        connectorStack = context["stack"]

        prefix = connectorStack.pop()

        while context["depth"] > depth:
            prefix = connectorStack.pop()
            context["depth"] -= 1

        connectorStack.append(prefix)

        if depth == 0:
            connector = prefix + " ── "
            connectorStack.append(prefix + (' ' * 4))
        else:
            connector = prefix + ("└── " if index == count else "├── ")
            connectorStack.append(prefix + (" " * 4 if index == count else "│   "))

        context["depth"] = depth + 1
        context["report"](connector + currentItem + " " + statusInfo)

    @staticmethod
    def _yieldModuleDependencyTreeEntry_FullPath(nodeInfo: dict, module: Module, context: dict) -> None:
        depth = nodeInfo["depth"]
        currentItem = nodeInfo["currentItem"]

        connectorStack = context["stack"]

        prefix = connectorStack.pop()

        while context["depth"] > depth:
            prefix = connectorStack.pop()
            context["depth"] -= 1

        connectorStack.append(prefix)

        connector = prefix
        connectorStack.append(prefix + currentItem + "/")

        context["depth"] = depth + 1
        context["report"](connector + currentItem)

    def generateModuleList(self, options: list[str]) -> dict:
        """
        Generates the build context and module list based on the command line options
        and module selectors provided, resolves dependencies on those modules if needed,
        filters out ignored or skipped modules, and sets up the module factory.

        After this function is called all module set selectors will have been
        expanded, and we will have downloaded kde-projects metadata.

        Returns:
            dict: A dict containing the following entries:

            - selectedModules: the selected modules to build
            - dependencyInfo: reference to dependency info object as created by :class:`DependencyResolver`
            - build: whether to actually perform a build action
        """
        argv = options

        # Note: Don't change the order around unless you're sure of what you're
        # doing.

        ctx = self.context
        deferredOptions = []  # 'options' blocks

        # Process --help, etc. first.
        c = Cmdline()
        opts: dict = c.readCommandLineOptionsAndSelectors(argv)

        selectors: list[str] = opts["selectors"]
        cmdlineOptions: dict = opts["opts"]
        cmdlineGlobalOptions: dict = cmdlineOptions["global"]
        ctx.phases.reset_to(opts["phases"])
        self.run_mode: str = opts["run_mode"]

        # Convert list to hash for lookup
        ignored_in_cmdline = {selector: True for selector in opts["ignore-modules"]}
        startProgramAndArgs: list[str] = opts["start-program"]

        # rc-file needs special handling.
        rcFile = cmdlineGlobalOptions["rc-file"] if "rc-file" in cmdlineGlobalOptions.keys() else ""
        rcFile = re.sub(r"^~", os.environ.get("HOME"), rcFile)
        if rcFile:
            ctx.setRcFile(rcFile)

        # pl2py: this was commented there in perl.
        # disable async if only running a single phase.
        #   if len(ctx.phases.phaselist) == 1:
        #     cmdlineGlobalOptions["async"] = 0

        ctx.setOption(cmdlineGlobalOptions)

        # We download repo-metadata before reading config, because config already includes the module-definitions from it.
        self._downloadKDEProjectMetadata()  # Uses test data automatically

        # _readConfigurationOptions will add pending global opts to ctx while ensuring
        # returned modules/sets have any such options stripped out. It will also add
        # module-specific options to any returned modules/sets.
        fh = ctx.loadRcFile()
        optionModulesAndSets: list[Module | ModuleSet] = self._readConfigurationOptions(ctx, fh, cmdlineGlobalOptions, deferredOptions)
        fh.close()

        ctx.loadPersistentOptions()

        # After we have read config, we know owr persistent options, and can read/overwrite them.
        if ctx.getOption("metadata-update-skipped"):
            lastUpdate = ctx.getPersistentOption("global", "last-metadata-update") or 0
            if (int(time()) - lastUpdate) >= 7200:
                logger_app.warning(" r[b[*] Skipped metadata update, but it hasn't been updated recently!")
            ctx.setPersistentOption("global", "last-metadata-update", int(time()))
        else:
            ctx.setPersistentOption("global", "last-metadata-update", int(time()))  # do not care of previous value, just overwrite if it was there

        # The user might only want metadata to update to allow for a later
        # --pretend run, check for that here.
        if "metadata-only" in cmdlineGlobalOptions:
            return {}

        if "resume" in cmdlineGlobalOptions:
            moduleList = ctx.getPersistentOption("global", "resume-list")
            if not moduleList:
                logger_app.error("b[--resume] specified, but unable to find resume point!")
                logger_app.error("Perhaps try b[--resume-from] or b[--resume-after]?")
                BuildException.croak_runtime("Invalid --resume flag")
            if selectors:
                logger_app.debug("Some selectors were presented alongside with --resume, ignoring them.")
            selectors = moduleList.split(", ")

        if "rebuild-failures" in cmdlineGlobalOptions:
            moduleList = ctx.getPersistentOption("global", "last-failed-module-list")
            if not moduleList:
                logger_app.error("b[y[--rebuild-failures] was specified, but unable to determine")
                logger_app.error("which modules have previously failed to build.")
                BuildException.croak_runtime("Invalid --rebuild-failures flag")
            if selectors:
                logger_app.debug("Some selectors were presented alongside with --rebuild-failures, ignoring them.")
            selectors = re.split(r",\s*", moduleList)

        if "list-installed" in cmdlineGlobalOptions:
            for key in ctx.persistent_options.keys():
                if "install-dir" in ctx.persistent_options[key]:
                    print(key)
            exit(0)

        ignored_in_global_section = {selector: True for selector in ctx.options["ignore-modules"].split(" ") if selector != ""}  # do not place empty string key, there is a check with empty string element of module's module_set later (in post-expansion ignored-selectors check).
        ctx.options["ignore-modules"] = ""

        # For user convenience, cmdline ignored selectors would not override the config selectors. Instead, they will be merged.
        ignoredSelectors = {**ignored_in_cmdline, **ignored_in_global_section}

        if startProgramAndArgs:
            StartProgram.execute_built_binary(ctx, startProgramAndArgs)  # noreturn

        if not Debug().isTesting():
            # Running in a test harness, avoid downloading metadata which will be
            # ignored in the test or making changes to git config
            Updater.verifyGitConfig(ctx)

        # At this point we have our list of candidate modules / module-sets (as read in
        # from rc-file). The module sets have not been expanded into modules.
        # We also might have cmdline "selectors" to determine which modules or
        # module-sets to choose. First let's select module sets, and expand them.

        globalCmdlineArgs = list(cmdlineGlobalOptions.keys())
        commandLineModules = len(selectors)

        moduleResolver = ModuleResolver(ctx)
        moduleResolver.setCmdlineOptions(cmdlineOptions)
        moduleResolver.setDeferredOptions(deferredOptions)
        moduleResolver.setInputModulesAndOptions(optionModulesAndSets)
        moduleResolver.setIgnoredSelectors(list(ignoredSelectors.keys()))

        self._defineNewModuleFactory(moduleResolver)

        if commandLineModules:
            modules = moduleResolver.resolveSelectorsIntoModules(selectors)
        else:
            # Build everything in the rc-file, in the order specified.
            modules = moduleResolver.expandModuleSets(optionModulesAndSets)

        # If modules were on the command line then they are effectively forced to
        # process unless overridden by command line options as well. If phases
        # *were* overridden on the command line, then no update pass is required
        # (all modules already have correct phases)
        if not commandLineModules:
            modules = Application._updateModulePhases(modules)

        # TODO: Verify this does anything still
        metadataModule = ctx.getKDEProjectsMetadataModule()
        ctx.addToIgnoreList(metadataModule.scm().ignoredModules())

        # Remove modules that are explicitly blanked out in their branch-group
        # i.e. those modules where they *have* a branch-group, and it's set to
        # be empty ("").
        resolver = ctx.moduleBranchGroupResolver()
        branchGroup = ctx.effectiveBranchGroup()

        filtered_modules: list[Module] = []
        for module in modules:
            branch = resolver.findModuleBranch(module.fullProjectPath(), branchGroup) if module.isKDEProject() else True  # Just a placeholder truthy value
            if branch is not None and not branch:
                logger_app.debug(f"Removing {module.fullProjectPath()} due to branch-group")
            if branch is None or branch:  # This is the actual test
                filtered_modules.append(module)
        modules = filtered_modules

        moduleGraph = self._resolveModuleDependencyGraph(modules)

        if not moduleGraph or "graph" not in moduleGraph:
            BuildException.croak_runtime("Failed to resolve dependency graph")

        if "dependency-tree" in cmdlineGlobalOptions or "dependency-tree-fullpath" in cmdlineGlobalOptions:
            depTreeCtx = {
                "stack": [""],
                "depth": 0,
                "report": lambda *args: print(*args, sep="", end="\n")
            }

            if "dependency-tree" in cmdlineGlobalOptions:
                callback = self._yieldModuleDependencyTreeEntry
            else:
                callback = self._yieldModuleDependencyTreeEntry_FullPath

            DependencyResolver.walkModuleDependencyTrees(
                moduleGraph["graph"],
                callback,
                depTreeCtx,
                modules
            )

            result = {
                "dependencyInfo": moduleGraph,
                "selectedModules": [],
                "build": False
            }
            return result

        modules = DependencyResolver.sortModulesIntoBuildOrder(moduleGraph["graph"])

        # Filter --resume-foo options. This might be a second pass, but that should
        # be OK since there's nothing different going on from the first pass (in
        # resolveSelectorsIntoModules) in that event.
        modules = Application._applyModuleFilters(ctx, modules)

        # Check for ignored modules (post-expansion)
        modules = [module for module in modules if
                   module.name not in ignoredSelectors and
                   (module.moduleSet().name if module.moduleSet().name else '') not in ignoredSelectors
                   ]

        result = {
            "dependencyInfo": moduleGraph,
            "selectedModules": modules,
            "build": True
        }
        return result

    def _downloadKDEProjectMetadata(self) -> None:
        """
        Causes kde-projects metadata to be downloaded (unless ``--pretend``, ``--no-src``, or
        ``--no-metadata`` is in effect, although we'll download even in ``--pretend`` if
        nothing is available).
        """

        ctx = self.context
        updateNeeded = False

        wasPretending = Debug().pretending()

        try:
            metadataModule = ctx.getKDEProjectsMetadataModule()

            sourceDir = metadataModule.getSourceDir()
            Debug().setPretending(False)  # We will create the source-dir for metadata even if we were in pretending mode
            if not Util.super_mkdir(sourceDir):
                updateNeeded = True
                BuildException.croak_runtime(f"Could not create {sourceDir} directory!")
            Debug().setPretending(wasPretending)

            moduleSource = metadataModule.fullpath("source")
            updateDesired = not ctx.getOption("no-metadata") and ctx.phases.has("update")
            updateNeeded = (not os.path.exists(moduleSource)) or (not os.listdir(moduleSource))

            if updateNeeded:
                Updater.verifyGitConfig(ctx)  # Set "kde:" aliases, that may not yet be configured at first run, causing git 128 exit status

            if not updateDesired and not updateNeeded:
                ctx.setOption({"metadata-update-skipped": 1})

            if updateNeeded and Debug().pretending():
                logger_app.warning(" y[b[*] Ignoring y[b[--pretend] option to download required metadata\n" +
                                   " y[b[*] --pretend mode will resume after metadata is available.")
                Debug().setPretending(False)

            if (updateDesired and not Debug().pretending()) or updateNeeded:
                orig_wd = os.getcwd()
                metadataModule.scm().updateInternal()
                logger_app.debug("Return to the original working directory after metadata downloading")  # This is needed to pick the config file from that directory
                Util.p_chdir(orig_wd)
                # "last-metadata-update" will be set after config is read, so value will be overriden

            Debug().setPretending(wasPretending)

        except Exception as err:
            Debug().setPretending(wasPretending)

            if updateNeeded:
                raise err

            # Assume previously-updated metadata will work if not updating
            logger_app.warning(" b[r[*] Unable to download required metadata for build process")
            logger_app.warning(" b[r[*] Will attempt to press onward...")
            logger_app.warning(f" b[r[*] Exception message: {err}")

            traceback.print_exc()

    def _resolveModuleDependencyGraph(self, modules: list[Module]) -> dict:
        """
        Returns a graph of Modules according to the KDE project database dependency
        information.

        The sysadmin/repo-metadata repository must have already been updated, and the
        module factory must be setup. The modules for which to calculate the graph
        must be passed in as arguments
        """
        ctx = self.context
        metadataModule = ctx.getKDEProjectsMetadataModule()

        try:
            dependencyResolver = DependencyResolver(self.module_factory)
            branchGroup = ctx.effectiveBranchGroup()

            if Debug().isTesting():
                testDeps = textwrap.dedent("""\
                                           juk: kcalc
                                           dolphin: konsole
                                           kde-builder: juk
                                           """)
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                    temp_file.write(testDeps)
                    temp_file_path = temp_file.name

                dependencies = fileinput.FileInput(files=temp_file_path, mode="r")
                logger_app.debug(" -- Reading dependencies from test data")
                dependencyResolver.readDependencyData(dependencies)
                dependencies.close()

                os.remove(temp_file_path)  # the file was in /tmp, no subfolders needs to be deleted
            else:
                srcdir = metadataModule.fullpath("source")
                dependencies = None

                dependencyFile = f"{srcdir}/dependencies/dependencies_v2-{branchGroup}.json"
                if os.path.exists(dependencyFile) and "KDESRC_BUILD_BETA" in os.environ:
                    try:
                        dependencies = Util.pretend_open(dependencyFile)
                    except Exception as e:
                        print(f"Unable to open {dependencyFile}: {e}")
                        exit(1)

                    logger_app.debug(f" -- Reading dependencies from {dependencyFile}")
                    dependencyResolver.readDependencyData_v2(dependencies)
                else:
                    dependencyFile = f"{srcdir}/dependencies/dependency-data-{branchGroup}"
                    try:
                        dependencies = Util.pretend_open(dependencyFile)
                    except Exception as e:
                        print(f"Unable to open {dependencyFile}: {e}")

                    logger_app.debug(f" -- Reading dependencies from {dependencyFile}")
                    dependencyResolver.readDependencyData(dependencies)

                dependencies.close()

            graph = dependencyResolver.resolveToModuleGraph(modules)

        except Exception as e:
            logger_app.warning(" r[b[*] Problems encountered trying to determing correct module graph:")
            logger_app.warning(f" r[b[*] {e}")
            logger_app.warning(" r[b[*] Will attempt to continue.")

            traceback.print_exc()

            graph = {
                "graph": None,
                "syntaxErrors": 0,
                "cycles": 0,
                "trivialCycles": 0,
                "pathErrors": 0,
                "branchErrors": 0,
                "exception": e
            }

        else:
            if not graph["graph"]:
                logger_app.warning(" r[b[*] Unable to determine correct module graph")
                logger_app.warning(" r[b[*] Will attempt to continue.")

        graph["exception"] = None

        return graph

    def runAllModulePhases(self) -> int | bool:
        """
        Runs all update, build, install, etc. phases. Basically this *is* the
        script. The metadata module must already have performed its update by this point.
        """
        ctx = self.context
        modules = self.modules

        # Add to global module list now that we've filtered everything.
        for module in modules:
            ctx.addModule(module)

        runMode = self.run_mode

        if runMode == "query":
            queryMode = ctx.getOption("query")

            if queryMode == "source-dir":
                def query(x):
                    return x.fullpath("source")
            elif queryMode == "build-dir":
                def query(x):
                    return x.fullpath("build")
            elif queryMode == "install-dir":
                def query(x):
                    return x.installationPath()
            elif queryMode == "project-path":
                def query(x):
                    return x.fullProjectPath()
            elif queryMode == "branch":
                def query(x):
                    return x.scm()._determinePreferredCheckoutSource()[0] or ""
            elif queryMode == "module-set":
                def query(x):
                    return x.module_set.name or "undefined_module-set"
            elif queryMode == "build-system":
                def query(x):
                    return x.buildSystem().name()
            else:  # Default to ->getOption as query method.
                def query(x):
                    return x.getOption(queryMode)

            for m in modules:
                print(f"{m}: ", query(m))

            return 0

        result = None  # shell-style (0 == success)

        # If power-profiles-daemon is in use, request switching to performance mode.
        self._holdPerformancePowerProfileIfPossible()

        if runMode == "build":
            # build and (by default) install.  This will involve two simultaneous
            # processes performing update and build at the same time by default.

            # Check for absolutely essential programs now.
            if not self._check_for_essential_build_programs() and not os.environ.get("KDE_BUILDER_IGNORE_MISSING_PROGRAMS"):
                logger_app.error(" r[b[*] Aborting now to save a lot of wasted time. Export b[KDE_BUILDER_IGNORE_MISSING_PROGRAMS=1] and re-run to continue anyway.")
                result = 1
            else:
                runner = TaskManager(self)
                result = runner.runAllTasks()
        elif runMode == "install":
            # install but do not build (... unless the build_system does that but
            # hey, we tried)
            result = Application._handle_install(ctx)
        elif runMode == "uninstall":
            result = Application._handle_uninstall(ctx)

        if ctx.getOption("purge-old-logs"):
            self._cleanup_log_directory(ctx)

        workLoad = self.workLoad
        dependencyGraph = workLoad["dependencyInfo"]["graph"]
        ctx = self.context

        Application._output_failed_module_lists(ctx, dependencyGraph)

        # Record all failed modules. Unlike the 'resume-list' option this doesn't
        # include any successfully-built modules in between failures.
        failedModules = ",".join(map(str, ctx.listFailedModules()))
        if failedModules:
            # We don't clear the list of failed modules on success so that
            # someone can build one or two modules and still use
            # --rebuild-failures
            ctx.setPersistentOption("global", "last-failed-module-list", failedModules)

        if ctx.getOption("install-login-session") and not Debug().pretending():
            self.install_login_session()

        # Check for post-build messages and list them here
        for m in modules:
            msgs = m.getPostBuildMessages()
            if not msgs:
                continue

            logger_app.warning(f"\ny[Important notification for b[{m}]:")
            for msg in msgs:
                logger_app.warning(f"    {msg}")

        color = "g[b["
        if result:
            color = "r[b["

        smile = ":-(" if result else ":-)"
        logger_app.info(f"\n{color}{smile}")

        return result

    def finish(self, exitcode: int | bool = 0) -> NoReturn:
        """
        Exits the script cleanly, including removing any lock files created.
        Parameters:
            exitcode: Optional; if passed, is used as the exit code, otherwise 0 is used.
        """
        ctx = self.context

        if Debug().pretending() or self._base_pid != os.getpid():
            # Abort early if pretending or if we're not the same process
            # that was started by the user (e.g. async mode, forked pipe-opens
            exit(exitcode)

        ctx.closeLock()
        ctx.storePersistentOptions()

        # modules in different source dirs may have different log dirs. If there
        # are multiple, show them all.

        globalLogBase = ctx.getSubdirPath("log-dir")
        globalLogDir = ctx.getLogDir()
        # global first
        logger_app.warning(f"Your logs are saved in y[{globalLogDir}]")

        for base, log in ctx.logPaths.items():
            if base != globalLogBase:
                logger_app.warning(f"  (additional logs are saved in y[{log}])")

        exit(exitcode)

    # internal helper functions

    @staticmethod
    def _readNextLogicalLine(fileReader: RecursiveFH) -> str | None:
        """
        Reads a "line" from a file. This line is stripped of comments and extraneous
        whitespace. Also, backslash-continued multiple lines are merged into a single
        line.

        Parameters:
            fileReader: The reference to the filehandle to read from.
        Returns:
             The text of the line.
        """
        line = fileReader.readLine()
        while line:
            # Remove trailing newline
            line = line.rstrip("\n")

            # Replace \ followed by optional space at EOL and try again.
            if re.search(r"\\\s*$", line):
                line = re.sub(r"\\\s*$", "", line)
                line += fileReader.readLine()
                continue

            if re.search(r"#.*$", line):
                line = re.sub(r"#.*$", "", line)  # Remove comments
            if re.match(r"^\s*$", line):
                line = fileReader.readLine()
                continue  # Skip blank lines

            return line
        return None

    @staticmethod
    def _splitOptionAndValue_and_substitute_value(ctx: BuildContext, input_line: str, fileReader: RecursiveFH) -> tuple:
        """
        Takes an input line, and extracts it into an option name, and simplified
        value. The value has "false" converted to False, white space simplified (like in
        Qt), tildes (~) in what appear to be path-like entries are converted to
        the home directory path, and reference to global option is substituted with its value.

        Parameters:
            ctx: The build context (used for translating option values).
            input_line: The line to split.
        Returns:
             Tuple (option-name, option-value)
        """
        Util.assert_isa(ctx, BuildContext)
        fileName = fileReader.currentFilename()
        optionRE = re.compile(r"\$\{([a-zA-Z0-9-_]+)}")  # Example of matched string is "${option-name}" or "${_option-name}".

        # The option is the first word, followed by the
        # flags on the rest of the line.  The interpretation
        # of the flags is dependent on the option.
        pattern = re.compile(
            r"^\s*"  # Find all spaces
            r"([-\w]+)"  # First match, alphanumeric, -, and _
            # (?: ) means non-capturing group, so (.*) is $value
            # So, skip spaces and pick up the rest of the line.
            r"(?:\s+(.*))?$"
        )

        match = re.match(pattern, input_line)
        option = match.group(1)
        value = match.group(2) or ""

        value = value.strip()

        # Simplify whitespace.
        value = re.sub(r"\s+", " ", value)

        # Replace reference to global option with their value.
        if re.findall(optionRE, value):
            sub_var_name = re.findall(optionRE, value)[0]
        else:
            sub_var_name = None

        while sub_var_name:
            sub_var_value = ctx.getOption(sub_var_name) or ""
            if not ctx.hasOption(sub_var_name):
                logger_app.warning(f" *\n * WARNING: {sub_var_name} is not set at line y[{fileName}:{fileReader.currentFilehandle().filelineno()}]\n *")

            logger_var_subst.debug(f"Substituting ${sub_var_name} with {sub_var_value}")

            value = re.sub(r"\$\{" + sub_var_name + r"}", sub_var_value, value)

            # Replace other references as well.  Keep this RE up to date with
            # the other one.
            sub_var_name = re.findall(optionRE, value)[0] if re.findall(optionRE, value) else None

        # Replace tildes with home directory.
        while re.search(r"(^|:|=)~/", value):
            value = re.sub(r"(^|:|=)~/", lambda m: m.group(1) + os.getenv("HOME") + "/", value)

        # Check for false keyword and convert it to Python False.
        # pl2py: in perl this is done a bit before, but we do this here. This is because value can be of type bool, and perl automatically compares int (they do not have bool) as a string.
        # If we did that conversion there, we would need to convert it back to string in checks above.
        if value.lower() == "false":
            value = False

        return option, value

    @staticmethod
    def _validateModuleSet(ctx: BuildContext, moduleSet: ModuleSet) -> None:
        """
        Ensures that the given :class:`ModuleSet` has at least a valid repository and
        use-modules setting based on the given BuildContext.
        """
        name = moduleSet.name if moduleSet.name else "unnamed"
        rcSources = Application._getModuleSources(moduleSet)

        # re-read option from module set since it may be pre-set
        selectedRepo = moduleSet.getOption("repository")
        if not selectedRepo:
            logger_app.error(textwrap.dedent(f"""\
            
            There was no repository selected for the y[b[{name}] module-set declared at
                {rcSources}
            
            A repository is needed to determine where to download the source code from.
            
            Most will want to use the b[g[kde-projects] repository. See also
            https://docs.kde.org/?application=kdesrc-build&branch=trunk5&path=kde-modules-and-selection.html#module-sets
            """))
            raise BuildException.make_exception("Config", "Missing repository option")

        repoSet = ctx.getOption("git-repository-base")
        if selectedRepo != Application.KDE_PROJECT_ID and selectedRepo != Application.QT_PROJECT_ID and selectedRepo not in repoSet:
            projectID = Application.KDE_PROJECT_ID
            moduleSetName = moduleSet.name
            moduleSetId = f"module-set ({moduleSetName})" if moduleSetName else "module-set"

            logger_app.error(textwrap.dedent(f"""\
            There is no repository assigned to y[b[{selectedRepo}] when assigning a
            {moduleSetId} at {rcSources}.
            
            These repositories are defined by g[b[git-repository-base] in the global
            section of your configuration.
            
            Make sure you spelled your repository name right, but you probably meant
            to use the magic b[{projectID}] repository for your module-set instead.
            """))

            raise BuildException.make_exception("Config", "Unknown repository base")

    def _parseModuleOptions(self, ctx: BuildContext, fileReader: RecursiveFH, module: OptionsBase, endRE=None):
        """
        Reads in the options from the config file and adds them to the option store.

        Parameters:
            ctx: A BuildContext object to use for creating the returned :class:`Module` under.
            fileReader: A reference to the file handle to read from.
            module: The :class:`OptionsBase` to use (module, module-set, ctx, etc.) For global options, just pass in the BuildContext for this param.
            endRE: Optional, if provided it should be a regexp for the terminator to use for the block being parsed in the rc file.

        Returns:
            The provided :class:`OptionsBase`, with options set as given in the configuration file section being processed.
        """
        Util.assert_isa(module, OptionsBase)

        if not hasattr(Application, "moduleID"):
            Application.moduleID = 0

        # Just look for an end marker if terminator not provided.
        if not endRE:
            endRE = re.compile(r"^\s*end[\w\s]*$")

        self._markModuleSource(module, fileReader.currentFilename() + ":" + str(fileReader.currentFilehandle().filelineno()))
        module.setOption({"#entry_num": Application.moduleID})
        Application.moduleID += 1

        phase_changing_options_canonical = [element.split("|")[0] for element in Cmdline.phase_changing_options]
        all_possible_options = sorted(list(ctx.build_options["global"].keys()) + phase_changing_options_canonical)

        # Read in each option
        line = self._readNextLogicalLine(fileReader)
        while line and not re.search(endRE, line):
            current_file = fileReader.currentFilename()

            # Sanity check, make sure the section is correctly terminated
            if re.match(r"^(module\b|options\b)", line):

                if isinstance(module, BuildContext):
                    endWord = "global"
                elif isinstance(module, ModuleSet):
                    endWord = "module-set"
                elif isinstance(module, Module):
                    endWord = "module"
                else:
                    endWord = "options"

                logger_app.error(f"Invalid configuration file {current_file} at line {fileReader.currentFilehandle().filelineno()}\nAdd an 'end {endWord}' before " + "starting a new module.\n")
                raise BuildException.make_exception("Config", f"Invalid file {current_file}")

            option, value = Application._splitOptionAndValue_and_substitute_value(ctx, line, fileReader)

            if option.startswith("_"):  # option names starting with underscore are treated as user custom variables
                ctx.setOption({option: value})  # merge the option to the build context right now, so we could already (while parsing global section) use this variable in other global options values.
            elif option not in all_possible_options:
                if option == "git-desired-protocol":  # todo This message is temporary. Remove it after 19.07.2024.
                    logger_app.error("y[Please edit your config. Replace \"r[git-desired-protocol]y[\" with \"g[git-push-protocol]y[\".")
                if option == "install-session-driver":  # todo This message is temporary. Remove it after 24.08.2024.
                    logger_app.error("y[Please edit your config. Replace \"r[install-session-driver]y[\" with \"g[install-login-session]y[\".")
                if option == "install-environment-driver":  # todo This message is temporary. Remove it after 24.08.2024.
                    logger_app.error("y[Please edit your config. Replace \"r[install-environment-driver]y[\" with \"g[install-login-session]y[\".")
                raise BuildException_Config(option, f"Unrecognized option \"{option}\" found at {current_file}:{fileReader.currentFilehandle().filelineno()}")

            # This is addition of python version
            if value == "true":
                value = True
            if value == "false":
                value = False

            try:
                module.setOption({option: value})
            except Exception as err:
                if isinstance(err, BuildException_Config):
                    msg = f"{current_file}:{fileReader.currentFilehandle().filelineno()}: " + err.message
                    explanation = err.optionUsageExplanation()
                    if explanation:
                        msg = msg + "\n" + explanation
                    err.message = msg
                raise  # re-throw

            line = self._readNextLogicalLine(fileReader)

        return module

    @staticmethod
    def _markModuleSource(optionsBase: OptionsBase, configSource: str) -> None:
        """
        Marks the given :class:`OptionsBase` subclass (i.e. :class:`Module` or :class:`ModuleSet`) as being
        read in from the given string (filename:line). An OptionsBase can be tagged under multiple files.
        """
        key = "#defined-at"
        sourcesRef = optionsBase.getOption(key) if optionsBase.hasOption(key) else []

        sourcesRef.append(configSource)
        optionsBase.setOption({key: sourcesRef})

    @staticmethod
    def _getModuleSources(optionsBase: ModuleSet) -> str:
        """
        Returns:
             rcfile sources for given OptionsBase (comma-separated).
        """
        key = "#defined-at"
        sourcesRef = optionsBase.getOption(key) or []
        return ", ".join(sourcesRef)

    def _parseModuleSetOptions(self, ctx: BuildContext, fileReader: RecursiveFH, moduleSet: ModuleSet) -> ModuleSet:
        """
        Reads in a "module_set".

        Parameters:
            ctx: The build context.
            fileReader: The filehandle to the config file to read from.
            moduleSet: The :class:`ModuleSet` to use.

        Returns:
            The :class:`ModuleSet` passed in with read-in options set, which may need
            to be further expanded (see :meth:`ModuleSet.convertToModules`).
        """
        moduleSet = self._parseModuleOptions(ctx, fileReader, moduleSet, re.compile(r"^end\s+module(-?set)?$"))

        # Perl-specific note! re-blessing the module set into the right 'class'
        # You'd probably have to construct an entirely new object and copy the
        # members over in other languages.
        if moduleSet.getOption("repository") == Application.KDE_PROJECT_ID:
            moduleSet.__class__ = ModuleSet_KDEProjects
        elif moduleSet.getOption("repository") == Application.QT_PROJECT_ID:
            moduleSet.__class__ = ModuleSet_Qt5
        return moduleSet

    def _readConfigurationOptions(self, ctx: BuildContext, fh: fileinput.FileInput, cmdlineGlobalOptions: dict, deferredOptionsRef: list) -> list[Module | ModuleSet]:
        """
        Reads in the settings from the configuration, passed in as an open filehandle.

        Parameters:
            ctx: The :class:`BuildContext` to update based on the configuration read and
                any pending command-line options (see global options in BuildContext).
            fh: The I/O filehandle object to read from.
            cmdlineGlobalOptions: An input dict mapping command line options to their
                values (if any), so that these may override conflicting entries in the rc-file.
            deferredOptionsRef: A list containing dicts mapping module names to options
                set by any 'options' blocks read in by this function.
                Each key (identified by the name of the 'options' block) will point to a
                dict value holding the options to apply.

        Returns:
            Heterogeneous list of :class:`Module` and :class:`ModuleSet` defined in the
            configuration file. No module sets will have been expanded out (either
            kde-projects or standard sets).

        Raises:
            BuildException_Config
        """
        module_list = []
        rcfile = ctx.rcFile
        option, readModules = None, None

        fileReader = RecursiveFH(rcfile, ctx)
        fileReader.addFile(fh, rcfile)

        # Read in global settings
        while line := fileReader.readLine():
            line = re.sub(r"#.*$", "", line)  # Remove comments
            line = re.sub(r"^\s+", "", line)  # Remove leading whitespace
            if not line:
                continue  # Skip blank lines

            # First command in .kdesrc-buildrc should be a global
            # options declaration, even if none are defined.
            if not re.match(r"^global\s*$", line):
                logger_app.error(f"Invalid configuration file: {rcfile}.")
                logger_app.error(f"Expecting global settings section at b[r[line {fh.filelineno()}]!")
                raise BuildException.make_exception("Config", "Missing global section")

            # Now read in each global option.
            globalOpts = self._parseModuleOptions(ctx, fileReader, OptionsBase())

            # For those options that user passed in cmdline, we do not want their corresponding config options to overwrite build context, so we forget them.
            for key in cmdlineGlobalOptions.keys():
                globalOpts.options.pop(key, None)
            ctx.mergeOptionsFrom(globalOpts)
            break

        using_default = True
        creation_order = False
        seenModules = {}  # NOTE! *not* module-sets, *just* modules.
        seenModuleSets = {}  # and vice versa -- named sets only though!
        seenModuleSetItems = {}  # To track option override modules.

        # Now read in module settings
        while line := fileReader.readLine():
            line = re.sub(r"#.*$", "", line)  # Remove comments
            line = re.sub(r"^\s*", "", line)  # Remove leading whitespace
            if line.strip() == "":
                continue  # Skip blank lines

            # Get modulename (has dash, dots, slashes, or letters/numbers)
            match = re.match(r"^(options|module)\s+([-/.\w]+)\s*$", line)
            option_type, modulename = None, None
            if match:
                option_type, modulename = match.group(1), match.group(2)

            newModule = None

            # 'include' directives can change the current file, so check where we're at
            rcfile = fileReader.currentFilename()

            # Module-set?
            if not modulename:
                moduleSetRE = re.compile(r"^module-set\s*([-/.\w]+)?\s*$")
                match = moduleSetRE.match(line)
                if match:
                    modulename = match.group(1)

                # modulename may be blank -- use the regex directly to match
                if not moduleSetRE.match(line):
                    logger_app.error(f"Invalid configuration file {rcfile}!")
                    logger_app.error(f"Expecting a start of module section at r[b[line {fileReader.currentFilehandle().filelineno()}].")
                    raise BuildException.make_exception("Config", "Ungrouped/Unknown option")

                if modulename and modulename in seenModuleSets.keys():
                    logger_app.error(f"Duplicate module-set {modulename} at {rcfile}:{fileReader.currentFilehandle().filelineno()}")
                    raise BuildException.make_exception("Config", f"Duplicate module-set {modulename} defined at {rcfile}:{fileReader.currentFilehandle().filelineno()}")

                if modulename and modulename in seenModules.keys():
                    logger_app.error(f"Name {modulename} for module-set at {rcfile}:{fileReader.currentFilehandle().filelineno()} is already in use on a module")
                    raise BuildException.make_exception("Config", f"Can't re-use name {modulename} for module-set defined at {rcfile}:{fileReader.currentFilehandle().filelineno()}")

                # A module_set can give us more than one module to add.
                newModule = self._parseModuleSetOptions(ctx, fileReader, ModuleSet(ctx, modulename or f"Unnamed module-set at {rcfile}:{fileReader.currentFilehandle().filelineno()}"))
                creation_order += 1
                newModule.create_id = creation_order

                # Save 'use-modules' entries, so we can see if later module decls
                # are overriding/overlaying their options.
                moduleSetItems = newModule.moduleNamesToFind()
                seenModuleSetItems = {item: newModule for item in moduleSetItems}

                # Reserve enough 'create IDs' for all named modules to use
                creation_order += len(moduleSetItems)
                if modulename:
                    seenModuleSets[modulename] = newModule

            # Duplicate module entry? (Note, this must be checked before the check
            # below for 'options' sets)
            elif modulename in seenModules and option_type != "options":
                logger_app.error(f"Duplicate module declaration b[r[{modulename}] on line {fileReader.currentFilehandle().filelineno()} of {rcfile}")
                raise BuildException.make_exception("Config", f"Duplicate module {modulename} declared at {rcfile}:{fileReader.currentFilehandle().filelineno()}")

            # Module/module-set options overrides
            elif option_type == "options":
                options = self._parseModuleOptions(ctx, fileReader, OptionsBase())

                deferredOptionsRef.append({
                    "name": modulename,
                    "opts": options.options
                })

                # NOTE: There is no duplicate options block checking here, and we
                # now currently rely on there being no duplicate checks to allow
                # for things like kf5-common-options.ksb to be included
                # multiple times.

                continue  # Don't add to module list

            # Must follow 'options' handling
            elif modulename in seenModuleSets:
                logger_app.error(f"Name {modulename} for module at {rcfile}:{fileReader.currentFilehandle().filelineno()} is already in use on a module-set")
                raise BuildException.make_exception("Config", f"Can't re-use name {modulename} for module defined at {rcfile}:{fileReader.currentFilehandle().filelineno()}")
            else:
                newModule = self._parseModuleOptions(ctx, fileReader, Module(ctx, modulename))
                newModule.create_id = creation_order + 1
                creation_order += 1
                seenModules[modulename] = newModule

            module_list.append(newModule)

            using_default = False

        for name, moduleSet in seenModuleSets.items():
            Application._validateModuleSet(ctx, moduleSet)

        # If the user doesn't ask to build any modules, build a default set.
        # The good question is what exactly should be built, but oh well.
        if using_default:
            logger_app.warning(" b[y[*] There do not seem to be any modules to build in your configuration.")
            return []

        return module_list

    @staticmethod
    def _handle_install(ctx: BuildContext) -> bool:
        """
        Handles the installation process. Simply calls "make install" in the build
        directory, though there is also provision for cleaning the build directory
        afterwards, or stopping immediately if there is a build failure (normally
        every built module is attempted to be installed).

        Parameters:
            ctx: BuildContext from which the install list is generated.

        Returns:
             Shell-style success code (0 == success)
        """
        Util.assert_isa(ctx, BuildContext)
        modules = ctx.modulesInPhase("install")

        modules = [module for module in modules if module.buildSystem().needsInstalled()]
        failed = False

        for module in modules:
            ctx.resetEnvironment()
            failed = not module.install() or failed

            if failed and module.getOption("stop-on-failure"):
                logger_app.warning("y[Stopping here].")
                return True  # Error
        return failed

    @staticmethod
    def _handle_uninstall(ctx: BuildContext) -> bool:
        """
        Handles the uninstall process. Simply calls "make uninstall" in the build
        directory, while assuming that Qt or CMake actually handles it.

        The order of the modules is often significant, and it may work better to
        uninstall modules in reverse order from how they were installed. However, this
        code does not automatically reverse the order; modules are uninstalled in the
        order determined by the build context.

        This function obeys the 'stop-on-failure' option supported by _handle_install.

        Parameters:
            ctx: Build Context from which the uninstall list is generated.

        Returns:
             Shell-style success code (0 == success)
        """
        Util.assert_isa(ctx, BuildContext)
        modules = ctx.modulesInPhase("uninstall")

        modules = [module for module in modules if module.buildSystem().needsInstalled()]
        failed = False

        for module in modules:
            ctx.resetEnvironment()
            failed = not module.uninstall() or failed

            if failed and module.getOption("stop-on-failure"):
                logger_app.warning("y[Stopping here].")
                return True  # Error
        return failed

    @staticmethod
    def _applyModuleFilters(ctx: BuildContext, moduleList: list[Module]) -> list[Module]:
        """
        Applies any module-specific filtering that is necessary after reading command
        line and rc-file options. (This is as opposed to phase filters, which leave
        each module as-is but change the phases they operate as part of, this
        function could remove a module entirely from the build).

        Used for --resume-{from,after} and --stop-{before,after}, but more could be
        added in theory.
        This function supports --{resume,stop}-* for both modules and module-sets.

        Parameters:
            ctx: :class:`BuildContext` in use.
            moduleList: List of :class:`Module` or :class:`ModuleSet` to apply filters on.

        Returns:
            List of :class:`Modules` or :class:`ModuleSet` with any inclusion/exclusion filters
            applied. Do not assume this list will be a strict subset of the input list,
            however the order will not change amongst the input modules.
        """
        Util.assert_isa(ctx, BuildContext)

        if not ctx.getOption("resume-from") and not ctx.getOption("resume-after") and not ctx.getOption("stop-before") and not ctx.getOption("stop-after"):
            logger_app.debug("No command-line filter seems to be present.")
            return moduleList

        if ctx.getOption("resume-from") and ctx.getOption("resume-after"):
            # This one's an error.
            logger_app.error(textwrap.dedent("""\
            You specified both r[b[--resume-from] and r[b[--resume-after] but you can only
            use one.
            """))
            BuildException.croak_runtime("Both --resume-after and --resume-from specified.")

        if ctx.getOption("stop-before") and ctx.getOption("stop-after"):
            # This one's an error.
            logger_app.error(textwrap.dedent("""\
            You specified both r[b[--stop-before] and r[b[--stop-after] but you can only
            use one.
            """))
            BuildException.croak_runtime("Both --stop-before and --stop-from specified.")

        if not moduleList:  # Empty input?
            return []

        resumePoint = ctx.getOption("resume-from") or ctx.getOption("resume-after")
        startIndex = len(moduleList)

        if resumePoint:
            logger_app.debug(f"Looking for {resumePoint} for --resume-* option")

            # || 0 is a hack to force Boolean context.
            filterInclusive = ctx.getOption("resume-from") or 0
            found = 0

            for i in range(len(moduleList)):
                module = moduleList[i]

                found = module.name == resumePoint
                if found:
                    startIndex = i if filterInclusive else i + 1
                    startIndex = min(startIndex, len(moduleList) - 1)
                    break
        else:
            startIndex = 0

        stopPoint = ctx.getOption("stop-before") or ctx.getOption("stop-after")
        stopIndex = 0

        if stopPoint:
            logger_app.debug(f"Looking for {stopPoint} for --stop-* option")

            # || 0 is a hack to force Boolean context.
            filterInclusive = ctx.getOption("stop-before") or 0
            found = 0

            for i in range(startIndex, len(moduleList)):
                module = moduleList[i]

                found = module.name == stopPoint
                if found:
                    stopIndex = i - (1 if filterInclusive else 0)
                    break
        else:
            stopIndex = len(moduleList) - 1

        if startIndex > stopIndex or len(moduleList) == 0:
            # Lost all modules somehow.
            BuildException.croak_runtime(f"Unknown resume -> stop point {resumePoint} -> {stopPoint}.")

        return moduleList[startIndex:stopIndex + 1]  # pl2py: in python the stop index is not included, so we add +1

    def _defineNewModuleFactory(self, resolver: ModuleResolver) -> None:
        """
        This defines the factory function needed for lower-level code to properly be
        able to create :class:`Module` objects from just the module name, while still
        having the options be properly set and having the module properly tied into a
        context.
        """
        ctx = self.context

        self.module_factory = lambda modu: resolver.resolveModuleIfPresent(modu)
        # We used to need a special module-set to ignore virtual deps (they
        # would throw errors if the name did not exist). But, the resolver
        # handles that fine as well.

    @staticmethod
    def _updateModulePhases(modules: list[Module]) -> list[Module]:
        """
        Updates the built-in phase list for all Modules passed into this function in
        accordance with the options set by the user.
        """
        logger_app.debug("Filtering out module phases.")
        for module in modules:
            if module.getOption("manual-update") or module.getOption("no-src"):
                module.phases.clear()
                continue

            if module.getOption("manual-build"):
                module.phases.filterOutPhase("build")
                module.phases.filterOutPhase("test")
                module.phases.filterOutPhase("install")

            if not module.getOption("install-after-build"):
                module.phases.filterOutPhase("install")
            if module.getOption("run-tests"):
                module.phases.addPhase("test")
        return modules

    def _cleanup_log_directory(self, ctx: BuildContext) -> None:
        """
        This function removes log directories from old kde-builder runs. All log
        directories not referenced by log_dir/latest somehow are made to go away.

        Parameters:
            ctx: Build context.

        Returns:
            None
        """
        Util.assert_isa(ctx, BuildContext)
        logdir = ctx.getSubdirPath("log-dir")

        if not os.path.exists(f"{logdir}/latest"):  # Could happen for error on first run...
            return 0

        # This glob relies on the date being in the specific format YYYY-MM-DD-ID
        dirs = glob.glob(f"{logdir}/????-??-??-??/")

        needed_table = {}
        for trackedLogDir in [f"{logdir}/latest", f"{logdir}/latest-by-phase"]:
            if not os.path.isdir(trackedLogDir):
                continue
            needed = self._reachableModuleLogs(trackedLogDir)

            # Convert a list to a hash lookup since Perl lacks a "list-has"
            needed_table.update({key: 1 for key in needed})

        length = len(dirs) - len(needed_table)
        logger_app.debug(f"Removing g[b[{length}] out of g[b[{len(dirs) - 1}] old log directories...")

        for d in dirs:
            match = re.search(r"(\d{4}-\d{2}-\d{2}-\d{2})", d)
            dir_id = match.group(1) if match else None
            if dir_id and not needed_table.get(dir_id):
                Util.safe_rmtree(d)

    @staticmethod
    def _output_possible_solution(ctx: BuildContext, fail_list: list[Module]) -> None:
        """
        Print out a "possible solution" message.
        It will display a list of command lines to run.

        No message is printed out if the list of failed modules is empty, so this
        function can be called unconditionally.

        Parameters:
            ctx: Build Context
            fail_list: List of :class:`Module` that had failed to build/configure/cmake.

        Returns:
            None
        """

        Util.assert_isa(ctx, BuildContext)

        if not fail_list:
            return
        if Debug().pretending():
            return

        moduleNames = []

        for module in fail_list:
            logfile = module.getOption("#error-log-file")

            if re.match(r"/cmake\.log$", logfile) or re.match(r"/meson-setup\.log$", logfile):
                moduleNames.append(module.name)

        if len(moduleNames) > 0:
            names = ", ".join(fail_list)
            logger_app.warning(textwrap.dedent(f"""
            Possible solution: Install the build dependencies for the modules:
            {names}
            You can use 'sudo apt build-dep <source_package>', 'sudo dnf builddep <package>', 'sudo zypper --plus-content repo-source source-install --build-deps-only <source_package>' or a similar command for your distro of choice.
            See https://community.kde.org/Get_Involved/development/Install_the_dependencies"""))

    @staticmethod
    def _output_failed_module_list(ctx: BuildContext, message: str, fail_list: list[Module]) -> None:
        """
        Print out an error message, and a list of modules that match that error
        message. It will also display the log file name if one can be determined.
        The message will be displayed all in uppercase, with PACKAGES prepended, so
        all you have to do is give a descriptive message of what this list of
        packages failed at doing.

        No message is printed out if the list of failed modules is empty, so this
        function can be called unconditionally.

        Parameters:
            ctx: Build Context
            message: Message to print (e.g. "failed to foo")
            fail_list: List of :class:`Module` that had failed to foo

        Returns:
            None
        """
        Util.assert_isa(ctx, BuildContext)
        message = message.upper()  # Be annoying

        if not fail_list:
            return

        logger_app.debug(f"Message is {message}")
        logger_app.debug("\tfor " + ", ".join([str(m) for m in fail_list]))

        homedir = os.environ.get("HOME")
        logfile = None

        logger_app.warning(f"\nr[b[<<<  PACKAGES {message}  >>>]")

        for module in fail_list:
            logfile = module.getOption("#error-log-file")

            # async updates may cause us not to have a error log file stored.  There's only
            # one place it should be though, take advantage of side-effect of log_command()
            # to find it.
            if not logfile:
                logdir = module.getLogDir() + "/error.log"
                if os.path.exists(logdir):
                    logfile = logdir

            if not logfile:
                logfile = "No log file"

            if Debug().pretending():
                logger_app.warning(f"r[{module}]")
            if not Debug().pretending():
                logger_app.warning(f"r[{module}] - g[{logfile}]")

    @staticmethod
    def _output_failed_module_lists(ctx: BuildContext, moduleGraph: dict) -> None:
        """
        This function reads the list of failed modules for each phase in the build
        context and calls _output_failed_module_list for all the module failures.

        Parameters:
            ctx: Build context
            moduleGraph:

        Return value:
            None
        """
        Util.assert_isa(ctx, BuildContext)

        extraDebugInfo = {
            "phases": {},
            "failCount": {}
        }
        actualFailures: list[Module] = []

        # This list should correspond to the possible phase names (although
        # it doesn't yet since the old code didn't, TODO)
        for phase in ctx.phases.phaselist:
            failures: list[Module] = ctx.failedModulesInPhase(phase)
            for failure in failures:
                # we already tagged the failure before, should not happen but
                # make sure to check to avoid spurious duplicate output
                if extraDebugInfo["phases"].get(failure, None):
                    continue

                extraDebugInfo["phases"][failure] = phase
                actualFailures.append(failure)
            Application._output_failed_module_list(ctx, f"failed to {phase}", failures)

        # See if any modules fail continuously and warn specifically for them.
        super_fail = [module for module in ctx.modules if (module.getPersistentOption("failure-count") or 0) > 3]

        for m in super_fail:
            # These messages will print immediately after this function completes.
            num_failures = m.getPersistentOption("failure-count")
            m.addPostBuildMessage(f"y[{m}] has failed to build b[{num_failures}] times.")

        top = 5
        numSuggestedModules = len(actualFailures)

        # Omit listing $top modules if there are that many or fewer anyway.
        # Not much point ranking 4 out of 4 failures,
        # this feature is meant for 5 out of 65

        if numSuggestedModules > top:
            sortedForDebug = DebugOrderHints.sortFailuresInDebugOrder(moduleGraph, extraDebugInfo, actualFailures)

            logger_app.info(f"\nThe following top {top} may be the most important to fix to " +
                            "get the build to work, listed in order of 'probably most " +
                            "interesting' to 'probably least interesting' failure:\n")
            for item in sortedForDebug[:top]:  # pl2py: in python the stop point is not included, so we add +1
                logger_app.info(f"\tr[b[{item}]")

        Application._output_possible_solution(ctx, actualFailures)

    @staticmethod
    def _installTemplatedFile(sourcePath: str, destinationPath: str, ctx: BuildContext) -> None:
        """
        This function takes a given file and a build context, and installs it to a
        given location while expanding out template entries within the source file.

        The template language is *extremely* simple: <% foo %> is replaced entirely
        with the result of `ctx.getOption(foo)`. If the result
        evaluates false for any reason than an exception is thrown. No quoting of
        any sort is used in the result, and there is no way to prevent expansion of
        something that resembles the template format.

        Multiple template entries on a line will be replaced.

        The destination file will be created if it does not exist. If the file
        already exists then an exception will be thrown.

        Error handling: Any errors will result in an exception being thrown.

        Parameters:
            sourcePath: Pathname to the source file (use absolute paths)
            destinationPath: Pathname to the destination file (use absolute paths)
            ctx: Build context to use for looking up template values

        Returns:
             None
        """

        Util.assert_isa(ctx, BuildContext)

        try:
            input_file = fileinput.FileInput(files=sourcePath, mode="r")
        except OSError as e:
            BuildException.croak_runtime(f"Unable to open template source $sourcePath: {e}")

        try:
            output_file = open(destinationPath, "w")
        except OSError as e:
            BuildException.croak_runtime(f"Unable to open template output $destinationPath: {e}")

        for line in input_file:
            if line is None:
                os.unlink(destinationPath)
                BuildException.croak_runtime(f"Failed to read from {sourcePath} at line {input_file.filelineno()}")

            # Some lines should only be present in the source as they aid with testing.
            if "kde-builder: filter" in line:
                continue

            pattern = re.compile(
                r"<% \s*"  # Template bracket and whitespace
                r"([^\s%]+)"  # Capture variable name
                r"\s*%>"  # remaining whitespace and closing bracket
            )
            match = re.search(pattern, line)
            if match:
                def repl():
                    optval = ctx.getOption(match.group(1))
                    if optval is None:  # pl2py: perl // "logical defined-or" operator checks the definedness, not truth. So empty string is considered as normal value.
                        BuildException.croak_runtime(f"Invalid variable {match.group(1)}")
                    return optval

                line = re.sub(pattern, repl(), line)  # Replace all matching expressions, use extended regexp with comments, and replacement is Python code to execute.

            try:
                output_file.write(line)
            except Exception as e:
                BuildException.croak_runtime(f"Unable to write line to {destinationPath}: {e}")

    @staticmethod
    def _installCustomFile(ctx: BuildContext, sourceFilePath: str, destFilePath: str, md5KeyName: str) -> None:
        """
        This function installs a source file to a destination path, assuming the
        source file is a "templated" source file (see also _installTemplatedFile), and
        records a digest of the file actually installed. This function will overwrite
        a destination if the destination is identical to the last-installed file.

        Error handling: Any errors will result in an exception being thrown.

        Parameters:
            ctx: Build context to use for looking up template values.
            sourceFilePath: The full path to the source file.
            destFilePath: The full path to the destination file (incl. name).
            md5KeyName: The key name to use for searching/recording installed MD5 digest.
        
        Returns:
             None
        """
        Util.assert_isa(ctx, BuildContext)
        baseName = os.path.basename(sourceFilePath)

        if os.path.exists(destFilePath):
            existingMD5 = ctx.getPersistentOption("/digests", md5KeyName) or ""

            if hashlib.md5(open(destFilePath, "rb").read()).hexdigest() != existingMD5:
                if not ctx.getOption("#delete-my-settings"):
                    logger_app.error(f"\tr[*] Installing \"b[{baseName}]\" would overwrite an existing file:")
                    logger_app.error(f"\tr[*]  y[b[{destFilePath}]")
                    logger_app.error(f"\tr[*] If this is acceptable, please delete the existing file and re-run,")
                    logger_app.error(f"\tr[*] or pass b[--delete-my-settings] and re-run.")

                    return
                elif not Debug().pretending():
                    shutil.copy(destFilePath, f"{destFilePath}.kde-builder-backup")

        if not Debug().pretending():
            Application._installTemplatedFile(sourceFilePath, destFilePath, ctx)
            ctx.setPersistentOption("/digests", md5KeyName, hashlib.md5(open(destFilePath, "rb").read()).hexdigest())

    def install_login_session(self) -> None:
        """
        This function makes an entire built-from-source Plasma session accessible from the SDDM login screen.

        It copies the needed files to the specific locations. After this, you can log out and select your new
        Plasma session in SDDM's session chooser menu.

        Before invoking the installation script (install-sessions.sh), this function checks if the invocation is
        actually needed. The check is made for each file that is going to be installed by the script. If at least one
        file is not presented in the destination location, or its md5 hash sum differs from the file to be installed,
        then the installation script is invoked. Otherwise, invocation is skipped, so user is not asked to enter sudo
        password.
        """

        RealBinDir = os.path.dirname(os.path.realpath(sys.modules["__main__"].__file__))

        ctx = self.context
        pws_builddir = ctx.getOption("build-dir") + "/plasma-workspace"
        install_sessions_script = pws_builddir + "/login-sessions/install-sessions.sh"
        startplasma_dev_script = pws_builddir + "/login-sessions/startplasma-dev.sh"
        libexecdir = f"""{ctx.getOption("install-dir")}/{ctx.getOption("libname")}/libexec"""

        if not os.path.isfile(install_sessions_script) or not os.path.isfile(startplasma_dev_script):
            logger_app.debug(" b[*] Unable to find login-sessions scripts in plasma-workspace build directory.\n"
                             "   You need to build plasma-workspace first. Cancelling login session installation.")
            return

        def get_md5(path: str):
            return hashlib.md5(open(path, "rb").read()).hexdigest()

        new_files_map = {}

        def check_match(sourcefile, destfile):
            source_md5 = get_md5(sourcefile)
            if os.path.exists(destfile):
                dest_md5 = get_md5(destfile)
                if source_md5 == dest_md5:
                    return
            new_files_map[sourcefile] = destfile

        def gen_new_files_map():
            plasmaver = ""
            if "6" in ctx.getOption("branch-group"):
                plasmaver = "6"

            check_match(pws_builddir + f"/login-sessions/plasmax11-dev{plasmaver}.desktop",
                        f"/usr/local/share/xsessions/plasmax11-dev{plasmaver}.desktop")
            check_match(pws_builddir + f"/login-sessions/plasmawayland-dev{plasmaver}.desktop",
                        f"/usr/local/share/wayland-sessions/plasmawayland-dev{plasmaver}.desktop")
            check_match(pws_builddir + "/prefix.sh",
                        libexecdir + "/plasma-dev-prefix.sh")
            check_match(startplasma_dev_script,
                        libexecdir + "/startplasma-dev.sh")
            check_match(RealBinDir + "/data/00-plasma.conf.in",
                        "/etc/dbus-1/session.d/00-plasma.conf")

            dbus1_files_dir = ctx.getOption("install-dir") + "/share/dbus-1"

            needed_dbus1_files = sorted([item.removeprefix(dbus1_files_dir) for item in glob.glob(dbus1_files_dir + "/**/*", recursive=True) if os.path.isfile(item)])

            for file in needed_dbus1_files:
                check_match(dbus1_files_dir + file, "/opt/kde-dbus-scripts" + file)

        gen_new_files_map()

        if new_files_map:
            logger_app.warning(" b[*] Installing login session")
            msg = "   These files needs to be (re)installed:\n    "
            for k, v in new_files_map.items():
                msg += f"\n     {k} -> {new_files_map[k]}"
            logger_app.info(msg)
            logger_app.info(f" b[*] Running script: {install_sessions_script}")
            subprocess.run([install_sessions_script])
            logger_app.warning(" b[*] Install login sessions script finished.")
        else:
            logger_app.debug(" b[*] No need to run install-sessions.sh, all files are already installed and up to date.")

    def _check_for_essential_build_programs(self) -> bool:
        """
        Checks if programs which are absolutely essential to the *build* process are available.
        The check is made for modules that are actually present in the build context.

        Returns:
            False if not all required programs are present. True otherwise.
        """
        ctx = self.context
        installdir = ctx.getOption("install-dir")
        qt_installdir = ctx.getOption("qt-install-dir")
        preferred_paths = [f"{installdir}/bin", f"{qt_installdir}/bin"]

        if Debug().pretending():
            return True

        buildModules = ctx.modulesInPhase("build")
        requiredPrograms = {}
        modulesRequiringProgram = {}

        for module in ctx.modulesInPhase("build"):
            progs = module.buildSystem().requiredPrograms()

            requiredPrograms = {prog: 1 for prog in progs}

            for prog in progs:
                if not modulesRequiringProgram.get(prog, None):
                    modulesRequiringProgram[prog] = {}
                modulesRequiringProgram[prog][module.name] = 1

        wasError = False
        for prog in requiredPrograms.keys():
            requiredPackages = {
                "qmake": "Qt",
                "cmake": "CMake",
                "meson": "Meson",
                "ninja": "Ninja",
            }

            preferredPath = Util.locate_exe(prog, preferred_paths)
            programPath = preferredPath or Util.locate_exe(prog)

            # qmake is not necessarily named "qmake"
            if not programPath and prog == "qmake":
                programPath = BuildSystem_QMake5.absPathToQMake()

            if not programPath:
                # Don't complain about Qt if we're building it...
                if prog == "qmake" and [x for x in buildModules if x.buildSystemType() == "Qt" or x.buildSystemType() == "Qt5"] or Debug().pretending():
                    continue

                wasError = True
                reqPackage = requiredPackages.get(prog) or prog

                modulesNeeding = modulesRequiringProgram[prog].keys()

                logger_app.error(textwrap.dedent(f"""\

                Unable to find r[b[{prog}]. This program is absolutely essential for building
                the modules: y[{", ".join(modulesNeeding)}].

                Please ensure the development packages for
                {reqPackage} are installed by using your distribution's package manager.
                """))
        return not wasError

    def _reachableModuleLogs(self, logdir: str) -> list[str]:
        """
        Returns a list of module directories IDs (based on YYYY-MM-DD-XX format) that must be kept due to being
        referenced from the "<log-dir>/latest/<module_name>" symlink and from the "<log-dir>/latest-by-phase/<module_name>/*.log" symlinks.

        This function may call itself recursively if needed.

        Parameters:
            logdir: The log directory under which to search for symlinks, including the "/latest" or "/latest-by-phase"
            part of the path.
        """
        links = []

        try:
            with os.scandir(logdir) as entries:
                for entry in entries:
                    if entry.is_symlink():  # symlinks to files/folders
                        link = os.readlink(entry.path)
                        links.append(link)
                    elif not re.match(r"^\.{1,2}$", entry.name) and not entry.is_file():  # regular (not symlinks) files/folders
                        # Skip . and .. directories
                        # Skip regular files (note that it is not a symlink to file, because of previous is_symlink check). _reachableModuleLogs expects a directory as parameter, but there may be files, for example ".directory".
                        links.extend(self._reachableModuleLogs(os.path.join(logdir, entry.name)))  # for regular directories, get links from it
        except OSError as e:
            BuildException.croak_runtime(f"Can't opendir {logdir}: {e}")

        # Extract numeric directories IDs from directories/files paths in links list.
        dirs = [re.search(r"(\d{4}-\d\d-\d\d-\d\d)", d).group(1) for d in links if re.search(r"(\d{4}-\d\d-\d\d-\d\d)", d)]  # if we use pretending, then symlink will point to /dev/null, so check if found matching group first

        # Convert to unique list by abusing hash keys.
        tempHash = {a_dir: None for a_dir in dirs}

        return list(tempHash.keys())

    @staticmethod
    def _installSignalHandlers(handlerRef: Callable) -> None:
        """
        Installs the given function as a signal handler for a set of signals which
        could kill the program.

        Parameters:
            handlerRef: A function to act as the handler.
        """
        signals = [signal.SIGHUP, signal.SIGINT, signal.SIGQUIT, signal.SIGABRT, signal.SIGTERM, signal.SIGPIPE]
        for sig in signals:
            signal.signal(sig, handlerRef)

    def _holdPerformancePowerProfileIfPossible(self):
        try:
            import dbus  # Do not import in the beginning of file, user may have not installed dbus-python module (we optionally require it)

            # Even when dbus-python is not installed, this module may still be imported successfully.
            # So check if dbus has some needed attributes, that way we will be sure that module can be used.
            if not hasattr(dbus, "SystemBus"):
                logger_app.warning("Looks like python-dbus package is not installed. Skipping dbus calls.")
                return

            try:
                system_bus = dbus.SystemBus()

                if Debug().pretending():
                    logger_app.info("d[Would hold performance profile")
                    return

                logger_app.info("Holding performance profile")

                service = system_bus.get_object("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles")
                ppd = dbus.Interface(service, "net.hadess.PowerProfiles")

                # The hold will be automatically released once kde-builder exits
                performance_cookie = ppd.HoldProfile("performance", f"building modules (pid: {self._base_pid})", "kde-builder")

                session_bus = dbus.SessionBus()
                proxy = session_bus.get_object("org.freedesktop.PowerManagement", "/org/freedesktop/PowerManagement/Inhibit")
                iface = dbus.Interface(proxy, "org.freedesktop.PowerManagement.Inhibit")

                # The inhibition will be automatically released once kde-builder exits
                sleep_cookie = iface.Inhibit("kde-builder", "Building modules")

            except dbus.DBusException as e:
                logger_app.warning(f"Error accessing dbus: {e}")
        except ImportError:  # even though the import is going ok even in case python-dbus is not installed, just to be safe, will catch import error
            logger_app.warning("Could not import dbus module. Skipping dbus calls.")
            return
