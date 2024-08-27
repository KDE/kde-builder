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
from kde_builder_lib.build_exception import SetOptionError
from .build_context import BuildContext
from .build_system.qmake5 import BuildSystemQMake5
from .cmd_line import Cmdline
from .debug import Debug
from .debug import KBLogger
from .debug_order_hints import DebugOrderHints
from .dependency_resolver import DependencyResolver
from .module.module import Module
from .module_resolver import ModuleResolver
from .module_set.kde_projects import ModuleSetKDEProjects
from .module_set.module_set import ModuleSet
from .module_set.qt5 import ModuleSetQt5
from .options_base import OptionsBase
from .recursive_fh import RecursiveFH
from .start_program import StartProgram
from .task_manager import TaskManager
from .updater.updater import Updater
from .util.util import Util

logger_var_subst = KBLogger.getLogger("variables_substitution")
logger_app = KBLogger.getLogger("application")


class Application:
    """
    Contains the application-layer logic (e.g. creating a build context, reading options, parsing command-line, etc.).

    Most of the specific tasks are delegated
    to supporting classes, this class primarily does the orchestration that goes
    from reading command line options, choosing which modules to build, overseeing
    the build process, and reporting the results to the user.

    Examples:
    ::

        app = kde_builder_lib.Application.Application(sys.argv)
        result = app.run_all_module_phases()
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
        self.module_factory = None  # function that makes a new Module. See generate_module_list
        self._base_pid = os.getpid()  # See finish()

        # Default to colorized output if sending to TTY
        Debug().set_colorful_output(True if sys.stdout.isatty() else False)

        work_load = self.generate_module_list(options)
        if not work_load.get("build", None):
            if len(options) == 2 and options[0] == "--metadata-only" and options[1] == "--metadata-only":  # Exactly this command line from FirstRun
                return  # Avoid exit, we can continue in the --install-distro-packages in FirstRun
                # Todo: Currently we still need to exit when normal use like `kde-builder --metadata-only`, because otherwise script tries to proceed with "result = app.run_all_module_phases()". Fix it.
            print("No modules to build, exiting.\n")
            exit(0)  # todo When --metadata-only was used and self.context.rc_file is not /fake/dummy_config, before exiting, it should store persistent option for last-metadata-update.

        self.modules: list[Module] = work_load["selected_modules"]
        self.work_load = work_load
        self.context.setup_operating_environment()  # i.e. niceness, ulimits, etc.

        # After this call, we must run the finish() method
        # to cleanly complete process execution.
        if not Debug().pretending() and not self.context.take_lock():  # todo move take_lock to the place before the actual work, not when creating an instance of Application.
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

        self._install_signal_handlers(signal_handler)

    @staticmethod
    def _yield_module_dependency_tree_entry(node_info: dict, module: Module, context: dict) -> None:
        depth = node_info["depth"]
        index = node_info["idx"]
        count = node_info["count"]
        build = node_info["build"]
        current_item = node_info["current_item"]
        current_branch = node_info["current_branch"]

        build_status = "built" if build else "not built"
        status_info = f"({build_status}: {current_branch})" if current_branch else f"({build_status})"

        connector_stack = context["stack"]

        prefix = connector_stack.pop()

        while context["depth"] > depth:
            prefix = connector_stack.pop()
            context["depth"] -= 1

        connector_stack.append(prefix)

        if depth == 0:
            connector = prefix + " ── "
            connector_stack.append(prefix + (" " * 4))
        else:
            connector = prefix + ("└── " if index == count else "├── ")
            connector_stack.append(prefix + (" " * 4 if index == count else "│   "))

        context["depth"] = depth + 1
        context["report"](connector + current_item + " " + status_info)

    @staticmethod
    def _yield_module_dependency_tree_entry_full_path(node_info: dict, module: Module, context: dict) -> None:
        depth = node_info["depth"]
        current_item = node_info["current_item"]

        connector_stack = context["stack"]

        prefix = connector_stack.pop()

        while context["depth"] > depth:
            prefix = connector_stack.pop()
            context["depth"] -= 1

        connector_stack.append(prefix)

        connector = prefix
        connector_stack.append(prefix + current_item + "/")

        context["depth"] = depth + 1
        context["report"](connector + current_item)

    def generate_module_list(self, options: list[str]) -> dict:
        """
        Generate the build context and module list based on the command line options and module selectors provided.

        Resolves dependencies on those modules if needed,
        filters out ignored or skipped modules, and sets up the module factory.

        After this function is called all module set selectors will have been
        expanded, and we will have downloaded kde-projects metadata.

        Returns:
            dict:
                {
                    "selected_modules": the selected modules to build
                    "dependency_info": reference to dependency info object as created by :class:`DependencyResolver`
                    "build": whether to actually perform a build action
                }
        """
        argv = options

        # Note: Don't change the order around unless you're sure of what you're
        # doing.

        ctx = self.context
        deferred_options = []  # "options" blocks

        # Process --help, etc. first.
        c = Cmdline()
        opts: dict = c.read_command_line_options_and_selectors(argv)

        selectors: list[str] = opts["selectors"]
        cmdline_options: dict = opts["opts"]
        cmdline_global_options: dict = cmdline_options["global"]
        ctx.phases.reset_to(opts["phases"])
        self.run_mode: str = opts["run_mode"]

        # Convert list to dict for lookup
        ignored_in_cmdline = {selector: True for selector in opts["ignore-modules"]}
        start_program_and_args: list[str] = opts["start-program"]

        # rc-file needs special handling.
        rc_file = cmdline_global_options["rc-file"] if "rc-file" in cmdline_global_options.keys() else ""
        rc_file = re.sub(r"^~", os.environ.get("HOME"), rc_file)
        if rc_file:
            ctx.set_rc_file(rc_file)

        # pl2py: this was commented there in perl.
        # disable async if only running a single phase.
        #   if len(ctx.phases.phaselist) == 1:
        #     cmdline_global_options["async"] = 0

        ctx.set_option(cmdline_global_options)

        # We download repo-metadata before reading config, because config already includes the module-definitions from it.
        self._download_kde_project_metadata()  # Uses test data automatically

        # _read_configuration_options will add pending global opts to ctx while ensuring
        # returned modules/sets have any such options stripped out. It will also add
        # module-specific options to any returned modules/sets.
        fh = ctx.load_rc_file()
        option_modules_and_sets: list[Module | ModuleSet] = self._read_configuration_options(ctx, fh, cmdline_global_options, deferred_options)
        fh.close()

        ctx.load_persistent_options()

        # After we have read config, we know owr persistent options, and can read/overwrite them.
        if ctx.get_option("metadata-update-skipped"):
            last_update = ctx.get_persistent_option("global", "last-metadata-update") or 0
            if (int(time()) - last_update) >= 7200:
                logger_app.warning(" r[b[*] Skipped metadata update, but it hasn't been updated recently!")
            ctx.set_persistent_option("global", "last-metadata-update", int(time()))
        else:
            ctx.set_persistent_option("global", "last-metadata-update", int(time()))  # do not care of previous value, just overwrite if it was there

        # The user might only want metadata to update to allow for a later
        # --pretend run, check for that here.
        if "metadata-only" in cmdline_global_options:
            return {}

        if "resume" in cmdline_global_options:
            module_list = ctx.get_persistent_option("global", "resume-list")
            if not module_list:
                logger_app.error("b[--resume] specified, but unable to find resume point!")
                logger_app.error("Perhaps try b[--resume-from] or b[--resume-after]?")
                BuildException.croak_runtime("Invalid --resume flag")
            if selectors:
                logger_app.debug("Some selectors were presented alongside with --resume, ignoring them.")
            selectors = module_list.split(", ")

        if "rebuild-failures" in cmdline_global_options:
            module_list = ctx.get_persistent_option("global", "last-failed-module-list")
            if not module_list:
                logger_app.error("b[y[--rebuild-failures] was specified, but unable to determine")
                logger_app.error("which modules have previously failed to build.")
                BuildException.croak_runtime("Invalid --rebuild-failures flag")
            if selectors:
                logger_app.debug("Some selectors were presented alongside with --rebuild-failures, ignoring them.")
            selectors = re.split(r",\s*", module_list)

        if "list-installed" in cmdline_global_options:
            for key in ctx.persistent_options.keys():
                if "install-dir" in ctx.persistent_options[key]:
                    print(key)
            exit(0)

        ignored_in_global_section = {selector: True for selector in ctx.options["ignore-modules"].split(" ") if selector != ""}  # do not place empty string key, there is a check with empty string element of module's module_set later (in post-expansion ignored-selectors check).
        ctx.options["ignore-modules"] = ""

        # For user convenience, cmdline ignored selectors would not override the config selectors. Instead, they will be merged.
        ignored_selectors = {**ignored_in_cmdline, **ignored_in_global_section}

        if start_program_and_args:
            StartProgram.execute_built_binary(ctx, start_program_and_args)  # noreturn

        if not Debug().is_testing():
            # Running in a test harness, avoid downloading metadata which will be
            # ignored in the test or making changes to git config
            Updater.verify_git_config(ctx)

        # At this point we have our list of candidate modules / module-sets (as read in
        # from rc-file). The module sets have not been expanded into modules.
        # We also might have cmdline "selectors" to determine which modules or
        # module-sets to choose. First let's select module sets, and expand them.

        command_line_modules = len(selectors)

        module_resolver = ModuleResolver(ctx)
        module_resolver.cmdline_options = cmdline_options
        module_resolver.set_deferred_options(deferred_options)
        module_resolver.set_input_modules_and_options(option_modules_and_sets)
        module_resolver.ignored_selectors = list(ignored_selectors.keys())

        self._define_new_module_factory(module_resolver)

        if command_line_modules:
            modules = module_resolver.resolve_selectors_into_modules(selectors)
        else:
            # Build everything in the rc-file, in the order specified.
            modules = module_resolver.expand_module_sets(option_modules_and_sets)

        # If modules were on the command line then they are effectively forced to
        # process unless overridden by command line options as well. If phases
        # *were* overridden on the command line, then no update pass is required
        # (all modules already have correct phases)
        if not command_line_modules:
            modules = Application._update_module_phases(modules)

        # TODO: Verify this does anything still
        metadata_module = ctx.get_kde_projects_metadata_module()
        ctx.add_to_ignore_list(metadata_module.scm().ignored_modules())

        # Remove modules that are explicitly blanked out in their branch-group
        # i.e. those modules where they *have* a branch-group, and it's set to
        # be empty ("").
        resolver = ctx.module_branch_group_resolver()
        branch_group = ctx.effective_branch_group()

        filtered_modules: list[Module] = []
        for module in modules:
            if module.get_module_set().name in ["qt5-set", "qt6-set"]:
                if module.get_option("install-dir") == "":
                    # User may have set their qt-install-dir option to empty string (the default), which means disabling building qt modules.
                    # But still user can accidentally request to build some qt modules (by explicitly specifying such modules in cmdline, or
                    # by building all when not specifying any). We should not allow building qt modules in such case.
                    # Otherwise, as their real "install-dir" is empty, their CMAKE_INSTALL_PREFIX will be incorrect (set to empty), and such
                    # modules could not pass cmake configure.
                    logger_app.debug(f"Removing {module.full_project_path()} due to qt-install-dir")
                    continue

            if module.is_kde_project():
                branch = resolver.find_module_branch(module.full_project_path(), branch_group)
            else:
                branch = True  # Just a placeholder truthy value

            if branch is not None and not branch:  # i.e. the branch is explicitly specified as empty string
                logger_app.debug(f"Removing {module.full_project_path()} due to branch-group")
                continue

            filtered_modules.append(module)

        modules = filtered_modules

        module_graph = self._resolve_module_dependency_graph(modules)

        if not module_graph or "graph" not in module_graph:
            BuildException.croak_runtime("Failed to resolve dependency graph")

        if "dependency-tree" in cmdline_global_options or "dependency-tree-fullpath" in cmdline_global_options:
            dep_tree_ctx = {
                "stack": [""],
                "depth": 0,
                "report": lambda *args: print(*args, sep="", end="\n")
            }

            if "dependency-tree" in cmdline_global_options:
                callback = self._yield_module_dependency_tree_entry
            else:
                callback = self._yield_module_dependency_tree_entry_full_path

            DependencyResolver.walk_module_dependency_trees(
                module_graph["graph"],
                callback,
                dep_tree_ctx,
                modules
            )

            result = {
                "dependency_info": module_graph,
                "selected_modules": [],
                "build": False
            }
            return result

        modules = DependencyResolver.sort_modules_into_build_order(module_graph["graph"])

        # Filter --resume-foo options. This might be a second pass, but that should
        # be OK since there's nothing different going on from the first pass (in
        # resolve_selectors_into_modules) in that event.
        modules = Application._apply_module_filters(ctx, modules)

        # Check for ignored modules (post-expansion)
        modules = [module for module in modules if
                   module.name not in ignored_selectors and
                   (module.get_module_set().name if module.get_module_set().name else "") not in ignored_selectors
                   ]

        result = {
            "dependency_info": module_graph,
            "selected_modules": modules,
            "build": True
        }
        return result

    def _download_kde_project_metadata(self) -> None:
        """
        Download kde-projects metadata, unless ``--pretend``, ``--no-src``, or ``--no-metadata`` is in effect.

        Although we'll download even in ``--pretend`` if nothing is available.
        """
        ctx = self.context
        update_needed = False

        was_pretending = Debug().pretending()

        try:
            metadata_module = ctx.get_kde_projects_metadata_module()

            source_dir = metadata_module.get_source_dir()
            Debug().set_pretending(False)  # We will create the source-dir for metadata even if we were in pretending mode
            if not Util.super_mkdir(source_dir):
                update_needed = True
                BuildException.croak_runtime(f"Could not create {source_dir} directory!")
            Debug().set_pretending(was_pretending)

            module_source = metadata_module.fullpath("source")
            update_desired = not ctx.get_option("no-metadata") and ctx.phases.has("update")
            update_needed = (not os.path.exists(module_source)) or (not os.listdir(module_source))

            if update_needed:
                Updater.verify_git_config(ctx)  # Set "kde:" aliases, that may not yet be configured at first run, causing git 128 exit status

            if not update_desired and not update_needed:
                ctx.set_option({"metadata-update-skipped": 1})

            if update_needed and Debug().pretending():
                logger_app.warning(" y[b[*] Ignoring y[b[--pretend] option to download required metadata\n" +
                                   " y[b[*] --pretend mode will resume after metadata is available.")
                Debug().set_pretending(False)

            if (update_desired and not Debug().pretending()) or update_needed:
                orig_wd = os.getcwd()
                metadata_module.current_phase = "update"
                metadata_module.scm().update_internal()
                metadata_module.current_phase = None
                logger_app.debug("Return to the original working directory after metadata downloading")  # This is needed to pick the config file from that directory
                Util.p_chdir(orig_wd)
                # "last-metadata-update" will be set after config is read, so value will be overriden

            Debug().set_pretending(was_pretending)

        except Exception as err:
            Debug().set_pretending(was_pretending)

            if update_needed:
                raise err

            # Assume previously-updated metadata will work if not updating
            logger_app.warning(" b[r[*] Unable to download required metadata for build process")
            logger_app.warning(" b[r[*] Will attempt to press onward...")
            logger_app.warning(f" b[r[*] Exception message: {err}")

            traceback.print_exc()

    def _resolve_module_dependency_graph(self, modules: list[Module]) -> dict:
        """
        Return a graph of Modules according to the KDE project database dependency information.

        The sysadmin/repo-metadata repository must have already been updated, and the
        module factory must be setup. The modules for which to calculate the graph
        must be passed in as arguments
        """
        ctx = self.context
        metadata_module = ctx.get_kde_projects_metadata_module()

        try:
            dependency_resolver = DependencyResolver(self.module_factory)
            branch_group = ctx.effective_branch_group()

            if Debug().is_testing():
                test_deps = textwrap.dedent("""\
                                           juk: kcalc
                                           dolphin: konsole
                                           kde-builder: juk
                                           kde-builder: third-party/taglib
                                           """)
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                    temp_file.write(test_deps)
                    temp_file_path = temp_file.name

                dependencies = fileinput.FileInput(files=temp_file_path, mode="r")
                logger_app.debug(" -- Reading dependencies from test data")
                dependency_resolver.read_dependency_data(dependencies)
                dependencies.close()

                os.remove(temp_file_path)  # the file was in /tmp, no subfolders needs to be deleted
            else:
                srcdir = metadata_module.fullpath("source")
                dependencies = None

                dependency_file = f"{srcdir}/dependencies/dependency-data-{branch_group}"
                try:
                    dependencies = Util.pretend_open(dependency_file)
                except Exception as e:
                    print(f"Unable to open {dependency_file}: {e}")

                logger_app.debug(f" -- Reading dependencies from {dependency_file}")
                dependency_resolver.read_dependency_data(dependencies)

                dependencies.close()

            graph = dependency_resolver.resolve_to_module_graph(modules)

        except Exception as e:
            logger_app.warning(" r[b[*] Problems encountered trying to determing correct module graph:")
            logger_app.warning(f" r[b[*] {e}")
            logger_app.warning(" r[b[*] Will attempt to continue.")

            traceback.print_exc()

            graph = {
                "graph": None,
                "syntax_errors": 0,
                "cycles": 0,
                "trivial_cycles": 0,
                "path_errors": 0,
                "branch_errors": 0,
                "exception": e
            }

        else:
            if not graph["graph"]:
                logger_app.warning(" r[b[*] Unable to determine correct module graph")
                logger_app.warning(" r[b[*] Will attempt to continue.")

        graph["exception"] = None

        return graph

    def run_all_module_phases(self) -> int | bool:
        """
        Run all update, build, install, etc. phases.

        Basically this *is* the script. The metadata module must already have performed its update by this point.
        """
        ctx = self.context
        modules = self.modules

        # Add to global module list now that we've filtered everything.
        for module in modules:
            ctx.add_module(module)

        run_mode = self.run_mode

        if run_mode == "query":
            query_mode = ctx.get_option("query")

            if query_mode == "source-dir":
                def query(x):
                    return x.fullpath("source")
            elif query_mode == "build-dir":
                def query(x):
                    return x.fullpath("build")
            elif query_mode == "install-dir":
                def query(x):
                    return x.installation_path()
            elif query_mode == "project-path":
                def query(x):
                    return x.full_project_path()
            elif query_mode == "branch":
                def query(x):
                    return x.scm().determine_preferred_checkout_source()[0] or ""
            elif query_mode == "module-set":
                def query(x):
                    return x.module_set.name or "undefined_module-set"
            elif query_mode == "build-system":
                def query(x):
                    return x.build_system().name()
            else:  # Default to .get_option() as query method.
                def query(x):
                    return x.get_option(query_mode)

            for m in modules:
                print(f"{m}: " + query(m))

            return 0

        result = None  # shell-style (0 == success)

        # If power-profiles-daemon is in use, request switching to performance mode.
        self._hold_performance_power_profile_if_possible()

        if run_mode == "build":
            # build and (by default) install.  This will involve two simultaneous
            # processes performing update and build at the same time by default.

            # Check for absolutely essential programs now.
            if not self._check_for_essential_build_programs() and not os.environ.get("KDE_BUILDER_IGNORE_MISSING_PROGRAMS"):
                logger_app.error(" r[b[*] Aborting now to save a lot of wasted time. Export b[KDE_BUILDER_IGNORE_MISSING_PROGRAMS=1] and re-run to continue anyway.")
                result = 1
            else:
                runner = TaskManager(self)
                result = runner.run_all_tasks()
        elif run_mode == "install":
            # install but do not build (... unless the build_system does that but
            # hey, we tried)
            result = Application._handle_install(ctx)
        elif run_mode == "uninstall":
            result = Application._handle_uninstall(ctx)

        if ctx.get_option("purge-old-logs"):
            self._cleanup_log_directory(ctx)

        work_load = self.work_load
        dependency_graph = work_load["dependency_info"]["graph"]
        ctx = self.context

        Application._output_failed_module_lists(ctx, dependency_graph)

        # Record all failed modules. Unlike the "resume-list" option this doesn't
        # include any successfully-built modules in between failures.
        failed_modules = ",".join(map(str, ctx.list_failed_modules()))
        if failed_modules:
            # We don't clear the list of failed modules on success so that
            # someone can build one or two modules and still use
            # --rebuild-failures
            ctx.set_persistent_option("global", "last-failed-module-list", failed_modules)

        if ctx.get_option("install-login-session") and not Debug().pretending():
            self.install_login_session()

        # Check for post-build messages and list them here
        for m in modules:
            msgs = m.get_post_build_messages()
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
        Exit the script cleanly, including removing any lock files created.

        Args:
            exitcode: Optional; if passed, is used as the exit code, otherwise 0 is used.
        """
        ctx = self.context

        if Debug().pretending() or self._base_pid != os.getpid():
            # Abort early if pretending or if we're not the same process
            # that was started by the user (e.g. async mode, forked pipe-opens
            exit(exitcode)

        ctx.close_lock()
        ctx.store_persistent_options()

        # modules in different source dirs may have different log dirs. If there
        # are multiple, show them all.

        global_log_base = ctx.get_subdir_path("log-dir")
        global_log_dir = ctx.get_log_dir()
        # global first
        logger_app.warning(f"Your logs are saved in y[{global_log_dir}]")

        for base, log in ctx.log_paths.items():
            if base != global_log_base:
                logger_app.warning(f"  (additional logs are saved in y[{log}])")

        exit(exitcode)

    # internal helper functions

    @staticmethod
    def _read_next_logical_line(file_reader: RecursiveFH) -> str | None:
        """
        Read a "line" from a file.

        This line is stripped of comments and extraneous whitespace. Also, backslash-continued multiple lines are merged into a single line.

        Args:
            file_reader: The reference to the filehandle to read from.

        Returns:
             The text of the line.
        """
        line = file_reader.read_line()
        while line:
            # Remove trailing newline
            line = line.rstrip("\n")

            # Replace \ followed by optional space at EOL and try again.
            if re.search(r"\\\s*$", line):
                line = re.sub(r"\\\s*$", "", line)
                line += file_reader.read_line()
                continue

            if re.search(r"#.*$", line):
                line = re.sub(r"#.*$", "", line)  # Remove comments
            if re.match(r"^\s*$", line):
                line = file_reader.read_line()
                continue  # Skip blank lines

            return line
        return None

    @staticmethod
    def _split_option_and_value_and_substitute_value(ctx: BuildContext, input_line: str, file_reader: RecursiveFH) -> tuple:
        """
        Take an input line, and extract it into an option name, and simplified value.

        The value has "false" converted to False, white space simplified (like in
        Qt), tildes (~) in what appear to be path-like entries are converted to
        the home directory path, and reference to global option is substituted with its value.

        Args:
            ctx: The build context (used for translating option values).
            input_line: The line to split.
            file_reader: The recursive filehandle to read from.

        Returns:
             Tuple (option-name, option-value)
        """
        Util.assert_isa(ctx, BuildContext)
        file_name = file_reader.current_filename()
        option_re = re.compile(r"\$\{([a-zA-Z0-9-_]+)}")  # Example of matched string is "${option-name}" or "${_option-name}".

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
        if re.findall(option_re, value):
            sub_var_name = re.findall(option_re, value)[0]
        else:
            sub_var_name = None

        while sub_var_name:
            sub_var_value = ctx.get_option(sub_var_name) or ""
            if not ctx.has_option(sub_var_name):
                logger_app.warning(f" *\n * WARNING: {sub_var_name} is not set at line y[{file_name}:{file_reader.current_filehandle().filelineno()}]\n *")

            logger_var_subst.debug(f"Substituting ${sub_var_name} with {sub_var_value}")

            value = re.sub(r"\$\{" + sub_var_name + r"}", sub_var_value, value)

            # Replace other references as well.  Keep this RE up to date with
            # the other one.
            sub_var_name = re.findall(option_re, value)[0] if re.findall(option_re, value) else None

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
    def _validate_module_set(ctx: BuildContext, module_set: ModuleSet) -> None:
        """
        Ensure that the given :class:`ModuleSet` has at least a valid repository and use-modules setting based on the given BuildContext.
        """
        name = module_set.name if module_set.name else "unnamed"
        rc_sources = Application._get_module_sources(module_set)

        # re-read option from module set since it may be pre-set
        selected_repo = module_set.get_option("repository")
        if not selected_repo:
            logger_app.error(textwrap.dedent(f"""\

            There was no repository selected for the y[b[{name}] module-set declared at
                {rc_sources}

            A repository is needed to determine where to download the source code from.

            Most will want to use the b[g[kde-projects] repository. See also
            https://docs.kde.org/?application=kdesrc-build&branch=trunk5&path=kde-modules-and-selection.html#module-sets
            """))
            raise BuildException("Config", "Missing repository option")

        repo_set = ctx.get_option("git-repository-base")
        if selected_repo != Application.KDE_PROJECT_ID and selected_repo != Application.QT_PROJECT_ID and selected_repo not in repo_set:
            project_id = Application.KDE_PROJECT_ID
            module_set_name = module_set.name
            module_set_id = f"module-set ({module_set_name})" if module_set_name else "module-set"

            logger_app.error(textwrap.dedent(f"""\
            There is no repository assigned to y[b[{selected_repo}] when assigning a
            {module_set_id} at {rc_sources}.

            These repositories are defined by g[b[git-repository-base] in the global
            section of your configuration.

            Make sure you spelled your repository name right, but you probably meant
            to use the magic b[{project_id}] repository for your module-set instead.
            """))

            raise BuildException("Config", "Unknown repository base")

    def _parse_module_options(self, ctx: BuildContext, file_reader: RecursiveFH, module: OptionsBase, end_re=None):
        """
        Read in the options from the config file and add them to the option store.

        Args:
            ctx: A BuildContext object to use for creating the returned :class:`Module` under.
            file_reader: A reference to the file handle to read from.
            module: The :class:`OptionsBase` to use (module, module-set, ctx, etc.) For global options, just pass in the BuildContext for this param.
            end_re: Optional, if provided it should be a regexp for the terminator to use for the block being parsed in the rc file.

        Returns:
            The provided :class:`OptionsBase`, with options set as given in the configuration file section being processed.
        """
        Util.assert_isa(module, OptionsBase)

        if not hasattr(Application, "moduleID"):
            Application.moduleID = 0

        # Just look for an end marker if terminator not provided.
        if not end_re:
            end_re = re.compile(r"^\s*end[\w\s]*$")

        self._mark_module_source(module, file_reader.current_filename() + ":" + str(file_reader.current_filehandle().filelineno()))
        module.set_option({"#entry_num": Application.moduleID})
        Application.moduleID += 1

        phase_changing_options_canonical = [element.split("|")[0] for element in Cmdline.phase_changing_options]
        all_possible_options = sorted(list(ctx.build_options["global"].keys()) + phase_changing_options_canonical)

        # Read in each option
        line = self._read_next_logical_line(file_reader)
        while line and not re.search(end_re, line):
            current_file = file_reader.current_filename()

            # Sanity check, make sure the section is correctly terminated
            if re.match(r"^(module\b|options\b)", line):

                if isinstance(module, BuildContext):
                    end_word = "global"
                elif isinstance(module, ModuleSet):
                    end_word = "module-set"
                elif isinstance(module, Module):
                    end_word = "module"
                else:
                    end_word = "options"

                logger_app.error(f"Invalid configuration file {current_file} at line {file_reader.current_filehandle().filelineno()}\nAdd an \"end {end_word}\" before " + "starting a new module.\n")
                raise BuildException("Config", f"Invalid file {current_file}")

            option, value = Application._split_option_and_value_and_substitute_value(ctx, line, file_reader)

            if option.startswith("_"):  # option names starting with underscore are treated as user custom variables
                ctx.set_option({option: value})  # merge the option to the build context right now, so we could already (while parsing global section) use this variable in other global options values.
            elif option not in all_possible_options:
                if option == "git-desired-protocol":  # todo This message is temporary. Remove it after 19.07.2024.
                    logger_app.error("y[Please edit your config. Replace \"r[git-desired-protocol]y[\" with \"g[git-push-protocol]y[\".")
                if option == "install-session-driver":  # todo This message is temporary. Remove it after 24.08.2024.
                    logger_app.error("y[Please edit your config. Replace \"r[install-session-driver]y[\" with \"g[install-login-session]y[\".")
                if option == "install-environment-driver":  # todo This message is temporary. Remove it after 24.08.2024.
                    logger_app.error("y[Please edit your config. Replace \"r[install-environment-driver]y[\" with \"g[install-login-session]y[\".")
                logger_app.error(f"Unrecognized option \"{option}\" found at {current_file}:{file_reader.current_filehandle().filelineno()}")

            # This is addition of python version
            if value == "true":
                value = True
            if value == "false":
                value = False

            try:
                module.set_option({option: value})
            except SetOptionError as err:
                msg = f"{current_file}:{file_reader.current_filehandle().filelineno()}: " + err.message
                explanation = err.option_usage_explanation()
                if explanation:
                    msg = msg + "\n" + explanation
                err.message = msg
                raise  # re-throw

            line = self._read_next_logical_line(file_reader)

        return module

    @staticmethod
    def _mark_module_source(options_base: OptionsBase, config_source: str) -> None:
        """
        Mark the given :class:`OptionsBase` subclass (i.e. :class:`Module` or :class:`ModuleSet`) as being read in from the given string (filename:line).

        An OptionsBase can be tagged under multiple files.
        """
        key = "#defined-at"
        sources = options_base.get_option(key) if options_base.has_option(key) else []

        sources.append(config_source)
        options_base.set_option({key: sources})

    @staticmethod
    def _get_module_sources(options_base: ModuleSet) -> str:
        """
        Return rcfile sources for given OptionsBase (comma-separated).
        """
        key = "#defined-at"
        sources = options_base.get_option(key) or []
        return ", ".join(sources)

    def _parse_module_set_options(self, ctx: BuildContext, file_reader: RecursiveFH, module_set: ModuleSet) -> ModuleSet:
        """
        Read in a "module_set".

        Args:
            ctx: The build context.
            file_reader: The filehandle to the config file to read from.
            module_set: The :class:`ModuleSet` to use.

        Returns:
            The :class:`ModuleSet` passed in with read-in options set, which may need
            to be further expanded (see :meth:`ModuleSet.convert_to_modules`).
        """
        module_set = self._parse_module_options(ctx, file_reader, module_set, re.compile(r"^end\s+module(-?set)?$"))

        # Perl-specific note! re-blessing the module set into the right "class"
        # You'd probably have to construct an entirely new object and copy the
        # members over in other languages.
        if module_set.get_option("repository") == Application.KDE_PROJECT_ID:
            module_set.__class__ = ModuleSetKDEProjects
        elif module_set.get_option("repository") == Application.QT_PROJECT_ID:
            module_set.__class__ = ModuleSetQt5
        return module_set

    def _read_configuration_options(self, ctx: BuildContext, fh: fileinput.FileInput, cmdline_global_options: dict, deferred_options: list) -> list[Module | ModuleSet]:
        """
        Read in the settings from the configuration, passed in as an open filehandle.

        Args:
            ctx: The :class:`BuildContext` to update based on the configuration read and
                any pending command-line options (see global options in BuildContext).
            fh: The I/O filehandle object to read from.
            cmdline_global_options: An input dict mapping command line options to their
                values (if any), so that these may override conflicting entries in the rc-file.
            deferred_options: A list containing dicts mapping module names to options
                set by any "options" blocks read in by this function.
                Each key (identified by the name of the "options" block) will point to a
                dict value holding the options to apply.

        Returns:
            Heterogeneous list of :class:`Module` and :class:`ModuleSet` defined in the
            configuration file. No module sets will have been expanded out (either
            kde-projects or standard sets).

        Raises:
            SetOptionError
        """
        module_list = []
        rcfile = ctx.rc_file

        file_reader = RecursiveFH(rcfile, ctx)
        file_reader.add_file(fh, rcfile)

        # Read in global settings
        while line := file_reader.read_line():
            line = re.sub(r"#.*$", "", line)  # Remove comments
            line = re.sub(r"^\s+", "", line)  # Remove leading whitespace
            if not line:
                continue  # Skip blank lines

            # First command in .kdesrc-buildrc should be a global
            # options declaration, even if none are defined.
            if not re.match(r"^global\s*$", line):
                logger_app.error(f"Invalid configuration file: {rcfile}.")
                logger_app.error(f"Expecting global settings section at b[r[line {fh.filelineno()}]!")
                raise BuildException("Config", "Missing global section")

            # Now read in each global option.
            global_opts = self._parse_module_options(ctx, file_reader, OptionsBase())

            # For those options that user passed in cmdline, we do not want their corresponding config options to overwrite build context, so we forget them.
            for key in cmdline_global_options.keys():
                global_opts.options.pop(key, None)
            ctx.merge_options_from(global_opts)
            break

        using_default = True
        creation_order = False
        seen_modules = {}  # NOTE! *not* module-sets, *just* modules.
        seen_module_sets = {}  # and vice versa -- named sets only though!
        # seen_module_set_items = {}  # To track option override modules.

        # Now read in module settings
        while line := file_reader.read_line():
            line = re.sub(r"#.*$", "", line)  # Remove comments
            line = re.sub(r"^\s*", "", line)  # Remove leading whitespace
            if line.strip() == "":
                continue  # Skip blank lines

            # Get modulename (has dash, dots, slashes, or letters/numbers)
            match = re.match(r"^(options|module)\s+([-/.\w]+)\s*$", line)
            option_type, modulename = None, None
            if match:
                option_type, modulename = match.group(1), match.group(2)

            new_module = None

            # "include" directives can change the current file, so check where we're at
            rcfile = file_reader.current_filename()

            # Module-set?
            if not modulename:
                module_set_re = re.compile(r"^module-set\s*([-/.\w]+)?\s*$")
                match = module_set_re.match(line)
                if match:
                    modulename = match.group(1)

                # modulename may be blank -- use the regex directly to match
                if not module_set_re.match(line):
                    logger_app.error(f"Invalid configuration file {rcfile}!")
                    logger_app.error(f"Expecting a start of module section at r[b[line {file_reader.current_filehandle().filelineno()}].")
                    raise BuildException("Config", "Ungrouped/Unknown option")

                if modulename and modulename in seen_module_sets.keys():
                    logger_app.error(f"Duplicate module-set {modulename} at {rcfile}:{file_reader.current_filehandle().filelineno()}")
                    raise BuildException("Config", f"Duplicate module-set {modulename} defined at {rcfile}:{file_reader.current_filehandle().filelineno()}")

                if modulename and modulename in seen_modules.keys():
                    logger_app.error(f"Name {modulename} for module-set at {rcfile}:{file_reader.current_filehandle().filelineno()} is already in use on a module")
                    raise BuildException("Config", f"Can't re-use name {modulename} for module-set defined at {rcfile}:{file_reader.current_filehandle().filelineno()}")

                # A module_set can give us more than one module to add.
                new_module = self._parse_module_set_options(ctx, file_reader, ModuleSet(ctx, modulename or f"Unnamed module-set at {rcfile}:{file_reader.current_filehandle().filelineno()}"))
                creation_order += 1
                new_module.create_id = creation_order

                # Save "use-modules" entries, so we can see if later module decls
                # are overriding/overlaying their options.
                module_set_items = new_module.module_names_to_find()
                # seen_module_set_items = {item: new_module for item in module_set_items}

                # Reserve enough "create IDs" for all named modules to use
                creation_order += len(module_set_items)
                if modulename:
                    seen_module_sets[modulename] = new_module

            # Duplicate module entry? (Note, this must be checked before the check
            # below for "options" sets)
            elif modulename in seen_modules and option_type != "options":
                logger_app.error(f"Duplicate module declaration b[r[{modulename}] on line {file_reader.current_filehandle().filelineno()} of {rcfile}")
                raise BuildException("Config", f"Duplicate module {modulename} declared at {rcfile}:{file_reader.current_filehandle().filelineno()}")

            # Module/module-set options overrides
            elif option_type == "options":
                options = self._parse_module_options(ctx, file_reader, OptionsBase())

                deferred_options.append({
                    "name": modulename,
                    "opts": options.options
                })

                # NOTE: There is no duplicate options block checking here, and we
                # now currently rely on there being no duplicate checks to allow
                # for things like kf5-common-options.ksb to be included
                # multiple times.

                continue  # Don't add to module list

            # Must follow "options" handling
            elif modulename in seen_module_sets:
                logger_app.error(f"Name {modulename} for module at {rcfile}:{file_reader.current_filehandle().filelineno()} is already in use on a module-set")
                raise BuildException("Config", f"Can't re-use name {modulename} for module defined at {rcfile}:{file_reader.current_filehandle().filelineno()}")
            else:
                new_module = self._parse_module_options(ctx, file_reader, Module(ctx, modulename))
                new_module.create_id = creation_order + 1
                creation_order += 1
                seen_modules[modulename] = new_module

            module_list.append(new_module)

            using_default = False

        for name, module_set in seen_module_sets.items():
            Application._validate_module_set(ctx, module_set)

        # If the user doesn't ask to build any modules, build a default set.
        # The good question is what exactly should be built, but oh well.
        if using_default:
            logger_app.warning(" b[y[*] There do not seem to be any modules to build in your configuration.")
            return []

        return module_list

    @staticmethod
    def _handle_install(ctx: BuildContext) -> bool:
        """
        Handle the installation process.

        Simply calls "make install" in the build
        directory, though there is also provision for cleaning the build directory
        afterwards, or stopping immediately if there is a build failure (normally
        every built module is attempted to be installed).

        Args:
            ctx: BuildContext from which the install list is generated.

        Returns:
             Shell-style success code (0 == success)
        """
        Util.assert_isa(ctx, BuildContext)
        modules = ctx.modules_in_phase("install")

        modules = [module for module in modules if module.build_system().needs_installed()]
        failed = False

        for module in modules:
            module.reset_environment()
            failed = not module.install() or failed

            if failed and module.get_option("stop-on-failure"):
                logger_app.warning("y[Stopping here].")
                return True  # Error
        return failed

    @staticmethod
    def _handle_uninstall(ctx: BuildContext) -> bool:
        """
        Handle the uninstall process.

        Simply calls "make uninstall" in the build
        directory, while assuming that Qt or CMake actually handles it.

        The order of the modules is often significant, and it may work better to
        uninstall modules in reverse order from how they were installed. However, this
        code does not automatically reverse the order; modules are uninstalled in the
        order determined by the build context.

        This function obeys the "stop-on-failure" option supported by _handle_install.

        Args:
            ctx: Build Context from which the uninstall list is generated.

        Returns:
             Shell-style success code (0 == success)
        """
        Util.assert_isa(ctx, BuildContext)
        modules = ctx.modules_in_phase("uninstall")

        modules = [module for module in modules if module.build_system().needs_installed()]
        failed = False

        for module in modules:
            module.reset_environment()
            failed = not module.uninstall() or failed

            if failed and module.get_option("stop-on-failure"):
                logger_app.warning("y[Stopping here].")
                return True  # Error
        return failed

    @staticmethod
    def _apply_module_filters(ctx: BuildContext, module_list: list[Module]) -> list[Module]:
        """
        Apply any module-specific filtering that is necessary after reading command line and rc-file options.

        (This is as opposed to phase filters, which leave
        each module as-is but change the phases they operate as part of, this
        function could remove a module entirely from the build).

        Used for --resume-{from,after} and --stop-{before,after}, but more could be
        added in theory.
        This function supports --{resume,stop}-* for both modules and module-sets.

        Args:
            ctx: :class:`BuildContext` in use.
            module_list: List of :class:`Module` or :class:`ModuleSet` to apply filters on.

        Returns:
            List of :class:`Modules` or :class:`ModuleSet` with any inclusion/exclusion filters
            applied. Do not assume this list will be a strict subset of the input list,
            however the order will not change amongst the input modules.
        """
        Util.assert_isa(ctx, BuildContext)

        if not ctx.get_option("resume-from") and not ctx.get_option("resume-after") and not ctx.get_option("stop-before") and not ctx.get_option("stop-after"):
            logger_app.debug("No command-line filter seems to be present.")
            return module_list

        if ctx.get_option("resume-from") and ctx.get_option("resume-after"):
            # This one's an error.
            logger_app.error(textwrap.dedent("""\
            You specified both r[b[--resume-from] and r[b[--resume-after] but you can only
            use one.
            """))
            BuildException.croak_runtime("Both --resume-after and --resume-from specified.")

        if ctx.get_option("stop-before") and ctx.get_option("stop-after"):
            # This one's an error.
            logger_app.error(textwrap.dedent("""\
            You specified both r[b[--stop-before] and r[b[--stop-after] but you can only
            use one.
            """))
            BuildException.croak_runtime("Both --stop-before and --stop-from specified.")

        if not module_list:  # Empty input?
            return []

        resume_point = ctx.get_option("resume-from") or ctx.get_option("resume-after")
        start_index = len(module_list)

        if resume_point:
            logger_app.debug(f"Looking for {resume_point} for --resume-* option")

            filter_inclusive = ctx.get_option("resume-from") or 0
            found = 0

            for i in range(len(module_list)):
                module = module_list[i]

                found = module.name == resume_point
                if found:
                    start_index = i if filter_inclusive else i + 1
                    start_index = min(start_index, len(module_list) - 1)
                    break
        else:
            start_index = 0

        stop_point = ctx.get_option("stop-before") or ctx.get_option("stop-after")
        stop_index = 0

        if stop_point:
            logger_app.debug(f"Looking for {stop_point} for --stop-* option")

            filter_inclusive = ctx.get_option("stop-before") or 0
            found = 0

            for i in range(start_index, len(module_list)):
                module = module_list[i]

                found = module.name == stop_point
                if found:
                    stop_index = i - (1 if filter_inclusive else 0)
                    break
        else:
            stop_index = len(module_list) - 1

        if start_index > stop_index or len(module_list) == 0:
            # Lost all modules somehow.
            BuildException.croak_runtime(f"Unknown resume -> stop point {resume_point} -> {stop_point}.")

        return module_list[start_index:stop_index + 1]  # pl2py: in python the stop index is not included, so we add +1

    def _define_new_module_factory(self, resolver: ModuleResolver) -> None:
        """
        Define the module factory function.

        The factory function is needed for lower-level code to properly be able to create :class:`Module` objects from just the module name, while still
        having the options be properly set and having the module properly tied into a context.
        """
        def module_factory(module_name: str) -> Module | None:
            ret = resolver.resolve_module_if_present(module_name)
            return ret

        self.module_factory = module_factory
        # We used to need a special module-set to ignore virtual deps (they
        # would throw errors if the name did not exist). But, the resolver
        # handles that fine as well.

    @staticmethod
    def _update_module_phases(modules: list[Module]) -> list[Module]:
        """
        Update the built-in phase list for all Modules passed into this function in accordance with the options set by the user.
        """
        logger_app.debug("Filtering out module phases.")
        for module in modules:
            if module.get_option("manual-update") or module.get_option("no-src"):
                module.phases.clear()
                continue

            if module.get_option("manual-build"):
                module.phases.filter_out_phase("build")
                module.phases.filter_out_phase("test")
                module.phases.filter_out_phase("install")

            if not module.get_option("install-after-build"):
                module.phases.filter_out_phase("install")
            if module.get_option("run-tests"):
                module.phases.add_phase("test")
        return modules

    def _cleanup_log_directory(self, ctx: BuildContext) -> None:
        """
        Remove log directories from previous kde-builder runs.

        All log directories that are not referenced by log_dir/latest somehow are made to go away.
        """
        Util.assert_isa(ctx, BuildContext)
        logdir = ctx.get_subdir_path("log-dir")

        if not os.path.exists(f"{logdir}/latest"):  # Could happen for error on first run...
            return

        found_dirs = [f for f in os.listdir(logdir) if re.search(r"(\d{4}-\d{2}-\d{2}[-_]\d+)", f)]

        keep_dirs = []
        for tracked_log_dir in [f"{logdir}/latest", f"{logdir}/latest-by-phase"]:
            if not os.path.isdir(tracked_log_dir):
                continue
            keep_dirs = self._symlinked_log_dirs(tracked_log_dir)

        length = len(found_dirs) - len(keep_dirs)
        logger_app.debug(f"Removing g[b[{length}] out of g[b[{len(found_dirs) - 1}] old log directories...")

        for dir_id in found_dirs:
            if dir_id not in keep_dirs:
                Util.safe_rmtree(logdir + "/" + dir_id)

    @staticmethod
    def _output_possible_solution(ctx: BuildContext, fail_list: list[Module]) -> None:
        """
        Print out a "possible solution" message.

        It will display a list of command lines to run.

        No message is printed out if the list of failed modules is empty, so this
        function can be called unconditionally.

        Args:
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

        module_names = []

        for module in fail_list:
            logfile = module.get_option("#error-log-file")

            if re.match(r"/cmake\.log$", logfile) or re.match(r"/meson-setup\.log$", logfile):
                module_names.append(module.name)

        if len(module_names) > 0:
            names = ", ".join(fail_list)
            logger_app.warning(textwrap.dedent(f"""
            Possible solution: Install the build dependencies for the modules:
            {names}
            You can use "sudo apt build-dep <source_package>", "sudo dnf builddep <package>", "sudo zypper --plus-content repo-source source-install --build-deps-only <source_package>" or a similar command for your distro of choice.
            See https://community.kde.org/Get_Involved/development/Install_the_dependencies"""))

    @staticmethod
    def _output_failed_module_list(ctx: BuildContext, message: str, fail_list: list[Module]) -> None:
        """
        Print out an error message, and a list of modules that match that error message.

        It will also display the log file name if one can be determined.
        The message will be displayed all in uppercase, with PACKAGES prepended, so
        all you have to do is give a descriptive message of what this list of
        packages failed at doing.

        No message is printed out if the list of failed modules is empty, so this
        function can be called unconditionally.

        Args:
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

        logger_app.warning(f"\nr[b[<<<  PACKAGES {message}  >>>]")

        for module in fail_list:
            logfile = module.get_option("#error-log-file")

            # async updates may cause us not to have a error log file stored.  There's only
            # one place it should be though, take advantage of side-effect of log_command()
            # to find it.
            if not logfile:
                logdir = module.get_log_dir() + "/error.log"
                if os.path.exists(logdir):
                    logfile = logdir

            if not logfile:
                logfile = "No log file"

            if Debug().pretending():
                logger_app.warning(f"r[{module}]")
            if not Debug().pretending():
                logger_app.warning(f"r[{module}] - g[{logfile}]")

    @staticmethod
    def _output_failed_module_lists(ctx: BuildContext, module_graph: dict) -> None:
        """
        Read the list of failed modules for each phase in the build context and call _output_failed_module_list for all the module failures.

        Args:
            ctx: Build context
            module_graph: The module graph.

        Return value:
            None
        """
        Util.assert_isa(ctx, BuildContext)

        extra_debug_info = {
            "phases": {},
            "failCount": {}
        }
        actual_failures: list[Module] = []

        # This list should correspond to the possible phase names (although
        # it doesn't yet since the old code didn't, TODO)
        for phase in ctx.phases.phaselist:
            failures: list[Module] = ctx.failed_modules_in_phase(phase)
            for failure in failures:
                # we already tagged the failure before, should not happen but
                # make sure to check to avoid spurious duplicate output
                if extra_debug_info["phases"].get(failure, None):
                    continue

                extra_debug_info["phases"][failure] = phase
                actual_failures.append(failure)
            Application._output_failed_module_list(ctx, f"failed to {phase}", failures)

        # See if any modules fail continuously and warn specifically for them.
        super_fail = [module for module in ctx.modules if (module.get_persistent_option("failure-count") or 0) > 3]

        for m in super_fail:
            # These messages will print immediately after this function completes.
            num_failures = m.get_persistent_option("failure-count")
            m.add_post_build_message(f"y[{m}] has failed to build b[{num_failures}] times.")

        top = 5
        num_suggested_modules = len(actual_failures)

        # Omit listing $top modules if there are that many or fewer anyway.
        # Not much point ranking 4 out of 4 failures,
        # this feature is meant for 5 out of 65

        if num_suggested_modules > top:
            sorted_for_debug = DebugOrderHints.sort_failures_in_debug_order(module_graph, extra_debug_info, actual_failures)

            logger_app.info(f"\nThe following top {top} may be the most important to fix to " +
                            "get the build to work, listed in order of 'probably most " +
                            "interesting' to 'probably least interesting' failure:\n")
            for item in sorted_for_debug[:top]:  # pl2py: in python the stop point is not included, so we add +1
                logger_app.info(f"\tr[b[{item}]")

        Application._output_possible_solution(ctx, actual_failures)

    @staticmethod
    def _install_templated_file(source_path: str, destination_path: str, ctx: BuildContext) -> None:
        """
        Take a given file and a build context, and install it to a given location while expanding out template entries within the source file.

        The template language is *extremely* simple: <% foo %> is replaced entirely
        with the result of `ctx.get_option(foo)`. If the result
        evaluates false for any reason than an exception is thrown. No quoting of
        any sort is used in the result, and there is no way to prevent expansion of
        something that resembles the template format.

        Multiple template entries on a line will be replaced.

        The destination file will be created if it does not exist. If the file
        already exists then an exception will be thrown.

        Error handling: Any errors will result in an exception being thrown.

        Args:
            source_path: Pathname to the source file (use absolute paths)
            destination_path: Pathname to the destination file (use absolute paths)
            ctx: Build context to use for looking up template values

        Returns:
             None
        """
        Util.assert_isa(ctx, BuildContext)

        try:
            input_file = fileinput.FileInput(files=source_path, mode="r")
        except OSError as e:
            BuildException.croak_runtime(f"Unable to open template source {source_path}: {e}")

        try:
            output_file = open(destination_path, "w")
        except OSError as e:
            BuildException.croak_runtime(f"Unable to open template output {destination_path}: {e}")

        for line in input_file:
            if line is None:
                os.unlink(destination_path)
                BuildException.croak_runtime(f"Failed to read from {source_path} at line {input_file.filelineno()}")

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
                    optval = ctx.get_option(match.group(1))
                    if optval is None:  # pl2py: perl // "logical defined-or" operator checks the definedness, not truth. So empty string is considered as normal value.
                        BuildException.croak_runtime(f"Invalid variable {match.group(1)}")
                    return optval

                line = re.sub(pattern, repl(), line)  # Replace all matching expressions, use extended regexp with comments, and replacement is Python code to execute.

            try:
                output_file.write(line)
            except Exception as e:
                BuildException.croak_runtime(f"Unable to write line to {destination_path}: {e}")

    @staticmethod
    def _install_custom_file(ctx: BuildContext, source_file_path: str, dest_file_path: str, md5_key_name: str) -> None:
        """
        Installs a source file to a destination path.

        Assuming the source file is a "templated" source file (see also _install_templated_file), and
        records a digest of the file actually installed. This function will overwrite
        a destination if the destination is identical to the last-installed file.

        Error handling: Any errors will result in an exception being thrown.

        Args:
            ctx: Build context to use for looking up template values.
            source_file_path: The full path to the source file.
            dest_file_path: The full path to the destination file (incl. name).
            md5_key_name: The key name to use for searching/recording installed MD5 digest.

        Returns:
             None
        """
        Util.assert_isa(ctx, BuildContext)
        base_name = os.path.basename(source_file_path)

        if os.path.exists(dest_file_path):
            existing_md5 = ctx.get_persistent_option("/digests", md5_key_name) or ""

            if hashlib.md5(open(dest_file_path, "rb").read()).hexdigest() != existing_md5:
                if not ctx.get_option("#delete-my-settings"):
                    logger_app.error(textwrap.dedent(f"""\
                        \tr[*] Installing \"b[{base_name}]\" would overwrite an existing file:
                        \tr[*]  y[b[{dest_file_path}]
                        \tr[*] If this is acceptable, please delete the existing file and re-run,
                        \tr[*] or pass b[--delete-my-settings] and re-run.
                        """))

                    return
                elif not Debug().pretending():
                    shutil.copy(dest_file_path, f"{dest_file_path}.kde-builder-backup")

        if not Debug().pretending():
            Application._install_templated_file(source_file_path, dest_file_path, ctx)
            ctx.set_persistent_option("/digests", md5_key_name, hashlib.md5(open(dest_file_path, "rb").read()).hexdigest())

    def install_login_session(self) -> None:
        """
        Make an entire built-from-source Plasma session accessible from the SDDM login screen.

        It copies the needed files to the specific locations. After this, you can log out and select your new
        Plasma session in SDDM's session chooser menu.

        Before invoking the installation script (install-sessions.sh), this function checks if the invocation is
        actually needed. The check is made for each file that is going to be installed by the script. If at least one
        file is not presented in the destination location, or its md5 hash sum differs from the file to be installed,
        then the installation script is invoked. Otherwise, invocation is skipped, so user is not asked to enter sudo
        password.
        """
        real_bin_dir = os.path.dirname(os.path.realpath(sys.modules["__main__"].__file__))

        ctx = self.context
        pws_builddir = ctx.get_option("build-dir") + "/plasma-workspace"
        install_sessions_script = pws_builddir + "/login-sessions/install-sessions.sh"
        startplasma_dev_script = pws_builddir + "/login-sessions/startplasma-dev.sh"
        libexecdir = f"""{ctx.get_option("install-dir")}/{ctx.get_option("libname")}/libexec"""

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
            if "6" in ctx.get_option("branch-group"):
                plasmaver = "6"

            check_match(pws_builddir + f"/login-sessions/plasmax11-dev{plasmaver}.desktop",
                        f"/usr/local/share/xsessions/plasmax11-dev{plasmaver}.desktop")
            check_match(pws_builddir + f"/login-sessions/plasmawayland-dev{plasmaver}.desktop",
                        f"/usr/local/share/wayland-sessions/plasmawayland-dev{plasmaver}.desktop")
            check_match(pws_builddir + "/prefix.sh",
                        libexecdir + "/plasma-dev-prefix.sh")
            check_match(startplasma_dev_script,
                        libexecdir + "/startplasma-dev.sh")
            check_match(real_bin_dir + "/data/00-plasma.conf.in",
                        "/etc/dbus-1/session.d/00-plasma.conf")

            dbus1_files_dir = ctx.get_option("install-dir") + "/share/dbus-1"

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
        Check if programs which are absolutely essential to the *build* process are available. The check is made for modules that are actually present in the build context.

        Returns:
            False if not all required programs are present. True otherwise.
        """
        ctx = self.context
        installdir = ctx.get_option("install-dir")
        qt_installdir = ctx.get_option("qt-install-dir")
        preferred_paths = [f"{installdir}/bin", f"{qt_installdir}/bin"]

        if Debug().pretending():
            return True

        build_modules = ctx.modules_in_phase("build")
        required_programs = {}
        modules_requiring_program = {}

        for module in ctx.modules_in_phase("build"):
            progs = module.build_system().required_programs()

            required_programs = {prog: 1 for prog in progs}

            for prog in progs:
                if not modules_requiring_program.get(prog, None):
                    modules_requiring_program[prog] = {}
                modules_requiring_program[prog][module.name] = 1

        was_error = False
        for prog in required_programs.keys():
            required_packages = {
                "qmake": "Qt",
                "cmake": "CMake",
                "meson": "Meson",
                "ninja": "Ninja",
            }

            preferred_path = Util.locate_exe(prog, preferred_paths)
            program_path = preferred_path or Util.locate_exe(prog)

            # qmake is not necessarily named "qmake"
            if not program_path and prog == "qmake":
                program_path = BuildSystemQMake5.abs_path_to_qmake()

            if not program_path:
                # Don't complain about Qt if we're building it...
                if prog == "qmake" and [x for x in build_modules if x.build_system_type() == "Qt" or x.build_system_type() == "Qt5"] or Debug().pretending():
                    continue

                was_error = True
                req_package = required_packages.get(prog) or prog

                modules_needing = modules_requiring_program[prog].keys()

                logger_app.error(textwrap.dedent(f"""\

                Unable to find r[b[{prog}]. This program is absolutely essential for building
                the modules: y[{", ".join(modules_needing)}].

                Please ensure the development packages for
                {req_package} are installed by using your distribution's package manager.
                """))
        return not was_error

    def _symlinked_log_dirs(self, logdir: str) -> list[str]:
        """
        Return a list of module directories IDs that are still referenced by symlinks.

        Can be used to get the list of directories that must be kept when removing old log directories.
        References are checked from the "<log-dir>/latest/<module_name>" symlink and from the "<log-dir>/latest-by-phase/<module_name>/*.log" symlinks.
        The directories IDs are based on YYYY-MM-DD_XX format.

        This function may call itself recursively if needed.

        Args:
            logdir: The log directory under which to search for symlinks, including the "/latest" or "/latest-by-phase" part of the path.
        """
        links = []

        try:
            with os.scandir(logdir) as entries:
                for entry in entries:
                    if entry.is_symlink():  # symlinks to files/folders
                        link = os.readlink(entry.path)
                        links.append(link)
                    elif entry.name != "." and entry.name != ".." and not entry.is_file():  # regular (not symlinks) files/folders
                        # Skip regular files (note that it is not a symlink to file, because of previous is_symlink check), because there may be files in logdir, for example ".directory" file.
                        links.extend(self._symlinked_log_dirs(os.path.join(logdir, entry.name)))  # for regular directories, get links from it
        except OSError as e:
            BuildException.croak_runtime(f"Can't opendir {logdir}: {e}")

        # Extract numeric directories IDs from directories/files paths in links list.
        dirs = [re.search(r"(\d{4}-\d\d-\d\d[-_]\d+)", d).group(1) for d in links if re.search(r"(\d{4}-\d\d-\d\d[-_]\d+)", d)]  # if we use pretending, then symlink will point to /dev/null, so check if found matching group first
        uniq_dirs = list(set(dirs))
        return uniq_dirs

    @staticmethod
    def _install_signal_handlers(handler_func: Callable) -> None:
        """
        Installs the given function as a signal handler for a set of signals which could kill the program.

        Args:
            handler_func: A function to act as the handler.
        """
        signals = [signal.SIGHUP, signal.SIGINT, signal.SIGQUIT, signal.SIGABRT, signal.SIGTERM, signal.SIGPIPE]
        for sig in signals:
            signal.signal(sig, handler_func)

    def _hold_performance_power_profile_if_possible(self) -> None:
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
                ppd.HoldProfile("performance", f"building modules (pid: {self._base_pid})", "kde-builder")

                session_bus = dbus.SessionBus()
                proxy = session_bus.get_object("org.freedesktop.PowerManagement", "/org/freedesktop/PowerManagement/Inhibit")
                iface = dbus.Interface(proxy, "org.freedesktop.PowerManagement.Inhibit")

                # The inhibition will be automatically released once kde-builder exits
                iface.Inhibit("kde-builder", "Building modules")

            except dbus.DBusException as e:
                logger_app.warning(f"Error accessing dbus: {e}")
        except ImportError:  # even though the import is going ok even in case python-dbus is not installed, just to be safe, will catch import error
            logger_app.warning("Could not import dbus module. Skipping dbus calls.")
            return
