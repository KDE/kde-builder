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
from time import sleep
from time import time
import traceback
from typing import Callable
from typing import NoReturn
import yaml

from kde_builder_lib.kb_exception import ConfigError
from kde_builder_lib.kb_exception import KBRuntimeError
from .build_context import BuildContext
from .build_system.qmake5 import BuildSystemQMake5
from .cmd_line import Cmdline
from .debug import Debug
from .debug import KBLogger
from .debug_order_hints import DebugOrderHints
from .dependency_resolver import DependencyResolver
from .log_dir import LogDir
from .module.module import Module
from .module_resolver import ModuleResolver
from .module_set.kde_projects import ModuleSetKDEProjects
from .module_set.module_set import ModuleSet
from .module_set.qt5 import ModuleSetQt5
from .options_base import OptionsBase
from .recursive_config_nodes_iterator import RecursiveConfigNodesIterator
from .start_program import StartProgram
from .task_manager import TaskManager
from .updater.updater import Updater
from .util.util import Util
from .util.textwrap_mod import textwrap
from .version import Version

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
            print("No projects to build, exiting.\n")
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
        Generate the build context and module list based on the command line options and module command line selectors provided.

        Resolves dependencies on those modules if needed,
        filters out ignored or skipped modules, and sets up the module factory.

        After this function is called all module set command line selectors will have been
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

        # Process --help, etc. first.
        c = Cmdline()
        opts: dict = c.read_command_line_options_and_selectors(argv)

        cmdline_selectors: list[str] = opts["selectors"]
        cmdline_options: dict = opts["opts"]
        cmdline_global_options: dict = cmdline_options["global"]
        ctx.phases.reset_to(opts["phases"])
        self.run_mode: str = opts["run_mode"]

        # Convert list to dict for lookup
        ignored_in_cmdline = {selector: True for selector in opts["ignore-projects"]}
        start_program_and_args: list[str] = opts["start-program"]

        # Self-update should be done early. At least before we read config.
        # This is to minimize situations of trying to read a not yet supported version of repo-metadata by outdated kde-builder installation.
        # Otherwise, manual intervention would be required to update kde-builder.
        if "self-update" in cmdline_global_options.keys():
            Version.self_update()

        # rc-file needs special handling.
        rc_file = cmdline_global_options["rc-file"] if "rc-file" in cmdline_global_options.keys() else ""
        rc_file = re.sub(r"^~", os.environ.get("HOME"), rc_file)
        if rc_file:
            ctx.set_rc_file(rc_file)

        # pl2py: this was commented there in perl.
        # disable async if only running a single phase.
        #   if len(ctx.phases.phaselist) == 1:
        #     cmdline_global_options["async"] = 0

        for opt_name, opt_val in cmdline_global_options.items():
            ctx.set_option(opt_name, opt_val)

        # We download repo-metadata before reading config, because config already includes the build-configs from it.
        self._download_kde_project_metadata()  # Skipped automatically in testing mode

        # The user might only want metadata to update to allow for a later --pretend run, check for that here.
        # We do this "metadata-only" check here (before _check_metadata_format_version()), to not disturb with repo-metadata-format check in case the user just wanted to download metadata.
        if "metadata-only" in cmdline_global_options:
            return {}

        # We do check the repo-metadata-format before reading config, because build-configs may become incompatible (indicated by increased number of "kde-builder-format").
        self._check_metadata_format_version()  # Skipped automatically in testing mode

        # _process_configs_content() will add pending global opts to ctx while ensuring
        # returned modules/sets have any such options stripped out. It will also add
        # module-specific options to any returned modules/sets.
        ctx.detect_config_file()
        modules_and_sets_from_userconfig: list[Module | ModuleSet]
        overrides_from_userconfig: list[dict[str, str | dict]]  # "override" nodes.
        modules_and_sets_from_userconfig, overrides_from_userconfig = self._process_configs_content(ctx, ctx.rc_file, cmdline_global_options)

        ctx.load_persistent_options()

        # After we have read config, we know owr persistent options, and can read/overwrite them.
        if ctx.get_option("metadata-update-skipped"):
            last_update = ctx.get_persistent_option("global", "last-metadata-update") or 0
            if (int(time()) - last_update) >= 7200:
                # Do not increase the level of this message, keep it at "debug" level.
                # By default, metadata is updated automatically anyway. And if it is not, user knows what they are doing.
                # Having this message shown with a higher logger level is problematic, because
                # this message is unwanted in many cases, for example, when querying project options.
                logger_app.debug(" r[b[*] Skipped metadata update, but it hasn't been updated recently!")
            ctx.set_persistent_option("global", "last-metadata-update", int(time()))
        else:
            ctx.set_persistent_option("global", "last-metadata-update", int(time()))  # do not care of previous value, just overwrite if it was there

        if "resume" in cmdline_global_options:
            module_list = ctx.get_persistent_option("global", "resume-list")
            if not module_list:
                logger_app.error("b[--resume] specified, but unable to find resume point!")
                logger_app.error("Perhaps try b[--resume-from] or b[--resume-after]?")
                raise KBRuntimeError("Invalid --resume flag")
            if cmdline_selectors:
                logger_app.debug("Some command line selectors were presented alongside with --resume, ignoring them.")
            cmdline_selectors = module_list.split(", ")

        if "rebuild-failures" in cmdline_global_options:
            module_list = ctx.get_persistent_option("global", "last-failed-module-list")
            if not module_list:
                logger_app.error("b[y[--rebuild-failures] was specified, but unable to determine")
                logger_app.error("which projects have previously failed to build.")
                raise KBRuntimeError("Invalid --rebuild-failures flag")
            if cmdline_selectors:
                logger_app.debug("Some command line selectors were presented alongside with --rebuild-failures, ignoring them.")
            cmdline_selectors = re.split(r",\s*", module_list)

        if "list-installed" in cmdline_global_options:
            for key in ctx.persistent_options.keys():
                if "install-dir" in ctx.persistent_options[key]:
                    print(key)
            exit(0)

        ignored_in_global_section = {selector: True for selector in ctx.options["ignore-projects"] if selector != ""}  # do not place empty string key, there is a check with empty string element of module's module_set later (in post-expansion ignored-selectors check).
        ctx.options["ignore-projects"] = []

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

        cmdline_selectors_len = len(cmdline_selectors)

        module_resolver = ModuleResolver(ctx)
        module_resolver.cmdline_options = cmdline_options
        module_resolver.set_deferred_options(overrides_from_userconfig)
        module_resolver.set_input_modules_and_options(modules_and_sets_from_userconfig)
        module_resolver.ignored_selectors = list(ignored_selectors.keys())

        self._define_new_module_factory(module_resolver)

        modules: list[Module] = []
        if not cmdline_selectors_len and not opts["special-selectors"] and self.run_mode != "install-login-session-only":
            logger_app.warning(" y[*] No projects selected in command line!\n"
                               "   b[*] To select all projects mentioned in config, use y[--all-config-projects].\n"
                               "   b[*] To select all kde projects, use y[--all-kde-projects].")

        if opts["special-selectors"]:
            sp_sels = opts["special-selectors"]
            if "all-kde-projects" in sp_sels or "all-config-projects" in sp_sels:
                all_config_projects: list[Module] = []
                all_kde_projects: list[Module] = []

                if "all-config-projects" in sp_sels:
                    # Build everything in the rc-file, in the order specified.
                    all_config_projects: list[Module] = module_resolver.expand_module_sets(modules_and_sets_from_userconfig)

                if "all-kde-projects" in sp_sels:
                    repos = self.context.get_project_data_reader().repositories
                    active_kde_projects: list[str] = []
                    for pr in repos:
                        if repos[pr]["active"] and repos[pr]["kind"] == "software":
                            active_kde_projects.append(repos[pr]["name"])
                    all_kde_projects: list[Module] = module_resolver.resolve_selectors_into_modules(active_kde_projects)

                modules: list[Module] = all_config_projects + all_kde_projects

        if cmdline_selectors_len:
            modules = modules + module_resolver.resolve_selectors_into_modules(cmdline_selectors)

        # TODO: Verify this does anything still
        metadata_module = ctx.get_kde_projects_metadata_module()
        ctx.add_to_ignore_list(metadata_module.scm().ignored_modules())

        # Remove modules that are explicitly blanked out in their branch-group
        # i.e. those modules where they *have* a branch-group, and it's set to
        # be empty ("").
        resolver = ctx.module_branch_group_resolver()
        branch_group = ctx.effective_branch_group()

        explicit_kdeproject_selectors: list[str] = []
        proj_db = self.context.get_project_data_reader().repositories
        for el in cmdline_selectors:
            leaf = el.split("/")[-1]
            if leaf in proj_db:
                explicit_kdeproject_selectors.append(leaf)

        filtered_modules: list[Module] = []
        for module in modules:
            if module.get_module_set().name in ["qt5-set", "qt6-set"]:
                if module.get_option("install-dir") == "":
                    # User may have set their qt-install-dir option to empty string (the default), which means disabling building qt modules.
                    # But still user can accidentally request to build some qt modules (by explicitly specifying such modules in cmdline, or
                    # by building all when not specifying any). We should not allow building qt modules in such case.
                    # Otherwise, as their real "install-dir" is empty, their CMAKE_INSTALL_PREFIX will be incorrect (set to empty), and such
                    # modules could not pass cmake configure.
                    logger_app.warning(f" y[*] Removing y[third-party]/y[{module.name}] due to qt-install-dir")
                    continue

            if module.is_kde_project():
                branch = resolver.find_module_branch(module.full_project_path(), branch_group)
                if branch == "":  # Note that None means it was not mentioned, while "" means it was explicitly disabled
                    printpath = module.get_option("#kde-repo-path")
                    printpath = "y[" + printpath.replace("/", "]/y[") + "]"
                    message = f" y[*] Removing {printpath} due to branch-group"
                    if module.name in explicit_kdeproject_selectors:
                        logger_app.warning(message)
                    else:
                        logger_app.debug(message)
                    continue

            filtered_modules.append(module)

        modules = filtered_modules

        module_graph = self._resolve_module_dependency_graph(modules)

        if not module_graph or "graph" not in module_graph:
            raise KBRuntimeError("Failed to resolve dependency graph")

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

        for module in modules:
            module.set_resolved_repository()

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
                raise KBRuntimeError(f"Could not create {source_dir} directory!")
            Debug().set_pretending(was_pretending)

            module_source = metadata_module.fullpath("source")
            update_desired = not ctx.get_option("no-metadata") and ctx.phases.has("update")
            update_needed = (not os.path.exists(module_source)) or (not os.listdir(module_source))

            if not update_desired and not update_needed:
                ctx.set_option("metadata-update-skipped", 1)

            if update_needed:
                if Debug().pretending():
                    logger_app.warning(" y[b[*] Ignoring y[b[--pretend] option to download required metadata\n" +
                                       " y[b[*] --pretend mode will resume after metadata is available.")
                    Debug().set_pretending(False)

                # This must be not in pretending mode, because we use "kde:" alias in the repository option of repo-metadata module, and so we really need to edit user's git config.
                Updater.verify_git_config(ctx)  # Set "kde:" aliases, that may not yet be configured at first run, causing git 128 exit status.

            if (update_desired and not Debug().pretending()) or update_needed:
                orig_wd = os.getcwd()
                metadata_module.current_phase = "update"
                logger_app.warning(f"Updating g[repo-metadata]")
                metadata_module.scm().update_internal()  # Skipped automatically in testing mode
                logger_app.warning("")  # Prints empty line to space it from next messages
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

    def _check_metadata_format_version(self) -> None:
        """
        Compare the number of "kde-builder-format" in repo-metadata-format.yaml from repo-metadata with the value expected by kde-builder.

        This is used to gracefully exit with a helpful message in case there were incompatible changes.
        """
        if Debug().is_testing():
            return

        real_bin_dir = os.path.dirname(os.path.realpath(sys.modules["__main__"].__file__))
        with open(real_bin_dir + "/data/supported-formats.yaml", "r") as f:
            supported_formats = yaml.safe_load(f)
        current_installation_format = supported_formats["kde-builder-format"]

        metadata_module = self.context.get_kde_projects_metadata_module()
        metadata_dir = metadata_module.fullpath("source")

        try:
            with open(f"{metadata_dir}/config/repo-metadata-format.yaml", "r") as f:
                repo_metadata_format_yaml = yaml.safe_load(f.read())
        except FileNotFoundError:
            msg = textwrap.dedent(f"""\
                ] r[b[*] Cannot check kde-builder-format in repo-metadata, because r[repo-metadata-format.yaml] is missing in repo-metadata.
                  r[*] It is possible that either kde-builder or repo-metadata are out of date.
                  r[*] To update kde-builder, use y[--self-update].
                  r[*] To update repo-metadata, use y[--metadata-only].""")
            logger_app.error(msg)
            exit()

        repo_metadata_format = repo_metadata_format_yaml["kde-builder-format"]

        if repo_metadata_format != current_installation_format:
            msg = textwrap.dedent(f"""\
            ] r[b[*] Repo-metadata format has changed. Please update kde-builder.
              r[*] kde-builder-format currently supported: b[{current_installation_format}]
              r[*] kde-builder-format from repo-metadata: b[{repo_metadata_format}]
              r[*] To update kde-builder, use y[--self-update].
              r[*] To update repo-metadata, use y[--metadata-only].""")
            logger_app.error(msg)
            exit()

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
                    dependencies = Util.open_or_fail(dependency_file)
                except Exception as e:
                    print(f"Unable to open {dependency_file}: {e}")

                logger_app.debug(f" -- Reading dependencies from {dependency_file}")
                dependency_resolver.read_dependency_data(dependencies)

                dependencies.close()

            graph = dependency_resolver.resolve_to_module_graph(modules)

        except Exception as e:
            logger_app.warning(" r[b[*] Problems encountered trying to determine correct project graph:")
            logger_app.warning(f" r[b[*] {e}")
            logger_app.warning(" r[b[*] Will attempt to continue.")

            # traceback.print_exc()

            graph = {
                "graph": {},
                "syntax_errors": 0,
                "cycles": 0,
                "trivial_cycles": 0,
                "path_errors": 0,
                "branch_errors": 0,
                "exception": e
            }

        else:
            if not graph["graph"] and self.run_mode != "install-login-session-only":
                logger_app.warning(" r[b[*] Unable to determine correct project graph")
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

            if query_mode == "project-info":
                dependency_graph = self.work_load["dependency_info"]
                results = {
                    project: {
                        "path": info["path"],
                        "branch": info["branch"],
                        "build": info["build"],
                        "repository": info["module"].options["#resolved-repository"],
                        "options": {
                            key: value
                            for key, value in info["module"].options.items()
                            if key.endswith("-options")
                        },
                        "phases": list(info["module"].phases.phaselist),
                        "dependencies": list(info["deps"].keys()),
                    }
                    for project, info in dependency_graph["graph"].items()
                    if info["module"]
                }
                print(yaml.dump(results, default_flow_style=False, indent=2))
                return 0

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
            elif query_mode == "group":
                def query(x):
                    return x.module_set.name or "undefined_group"
            elif query_mode == "build-system":
                def query(x):
                    return x.build_system().name()
            elif query_mode == "cmake-options":
                def query(x):
                    if x.build_system().name() == "KDE CMake":
                        out_res = x.build_system().get_final_cmake_options()
                        return " ".join(out_res)
                    else:
                        return "<not a cmake build system>"
            else:  # Default to .get_option() as query method.
                def query(x):
                    return x.get_option(query_mode)

            for m in modules:
                res = query(m)
                if not isinstance(res, str):
                    res = str(res)
                print(f"{m}: " + res)

            return 0

        result = None  # shell-style (0 == success)

        # If power-profiles-daemon is in use, request switching to performance mode.
        self._hold_performance_power_profile_if_possible()
        LogDir.cleanup_latest_log_dir(ctx)

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
            LogDir.delete_unreferenced_log_directories(ctx)

        work_load = self.work_load
        dependency_graph = work_load["dependency_info"]["graph"]
        ctx = self.context

        Application._print_failed_modules_in_each_phase(ctx, dependency_graph)

        # Record all failed modules. Unlike the "resume-list" option this doesn't
        # include any successfully-built modules in between failures.
        failed_modules = ",".join(map(str, ctx.list_failed_modules()))
        if failed_modules:
            # We don't clear the list of failed modules on success so that
            # someone can build one or two modules and still use
            # --rebuild-failures
            ctx.set_persistent_option("global", "last-failed-module-list", failed_modules)

        if (ctx.get_option("install-login-session") or run_mode == "install-login-session-only") and not Debug().pretending():
            res = self.install_login_session()
            if res and not result:
                result = res

        if ctx.get_option("check-self-updates"):
            last_self_updates_check = ctx.get_persistent_option("global", "last-self-updates-check") or 0
            try:
                last_self_updates_check = int(last_self_updates_check)
            except ValueError:
                last_self_updates_check = 0

            check_period = 604800  # 604800 - number of seconds in one week
            if last_self_updates_check + check_period <= int(time()) and not Debug().pretending():
                Version.check_for_updates()
                ctx.set_persistent_option("global", "last-self-updates-check", int(time()))

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

        global_log_base = ctx.get_absolute_path("log-dir")
        global_log_dir = ctx.get_log_dir()
        # global first
        logger_app.warning(f"Your logs are saved in y[{global_log_dir}]")

        for base, log in ctx.log_paths.items():
            if base != global_log_base:
                logger_app.warning(f"  (additional logs are saved in y[{log}])")

        exit(exitcode)

    @staticmethod
    def _process_configs_content(ctx: BuildContext, config_path: str, cmdline_global_options: dict) -> tuple[list[Module | ModuleSet], list[dict[str, str | dict]]]:
        """
        Read in the settings from the configuration.

        Args:
            ctx: The :class:`BuildContext` to update based on the configuration read and
                any pending command-line options (see global options in BuildContext).
            config_path: Full path of the config file to read from.
            cmdline_global_options: An input dict mapping command line options to their
                values (if any), so that these may override conflicting entries in the rc-file.

        Returns:
            A tuple consisting of:
            - module_and_module_set_list:
                Heterogeneous list of :class:`Module` and :class:`ModuleSet` defined in the
                configuration file. No module sets will have been expanded out (either
                kde-projects or standard sets).
            - deferred_options:
                A list containing dicts mapping module names to options
                set by any "override" nodes read in by this function.
                Each key (identified by the name of the "override" node) will point to a
                dict value holding the options to apply.

        Raises:
            SetOptionError
        """
        with open(ctx.rc_file, "r") as f:
            try:
                config_content = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                exc_msgs = "\n  " + "\n  ".join(str(x) for x in exc.args)
                raise ConfigError("Error parsing yaml configuration file:" + exc_msgs)
        module_and_module_set_list = []
        rcfile = ctx.rc_file

        first_node = next(iter(config_content))
        first_node_content = config_content.pop(first_node)

        if first_node != "config-version":
            # First key in the kde-builder.yaml should be "config-version".
            logger_app.error(f"Invalid configuration file: {rcfile}\nThe very first element in config should be \"config-version\".")
            raise ConfigError("Unexpected first key instead of \"config-version\".")
        elif first_node_content != 2:
            raise ConfigError(f"Unrecognized config version number. The version 2 was expected, but {first_node_content} was given.")

        first_node = next(iter(config_content))
        first_node_content = config_content.pop(first_node)

        if first_node != "global":
            # First key in kde-builder.yaml should be "global".
            logger_app.error(f"Invalid configuration file: {rcfile}.")
            logger_app.error(f"Expecting global settings node!")
            raise ConfigError("Missing global section")
        else:
            global_opts = OptionsBase()
            global_opts.apply_config_options(ctx, first_node_content, rcfile)
            # For those options that user passed in cmdline, we do not want their corresponding config options to overwrite build context, so we forget them.
            for key in cmdline_global_options.keys():
                global_opts.options.pop(key, None)
            ctx.merge_options_from(global_opts)

        # Now, after global options were resolved and set, we can resolve paths in include lines and read those config files.
        node_reader = RecursiveConfigNodesIterator(config_content, rcfile, ctx)

        config_nodes_list = []
        for node in node_reader:
            config_nodes_list.append(node)

        nothing_defined = True
        creation_order = 0
        seen_modules = {}  # NOTE! *not* module-sets, *just* modules.
        seen_module_sets = {}  # and vice versa
        # seen_module_set_items = {}  # To track option override modules.
        deferred_options: list[dict[str, str | dict]] = []

        for node_name, node, config_filename in config_nodes_list:
            if node_name.startswith("group "):
                module_set_name = node_name.split(" ", maxsplit=1)[1]
                assert module_set_name  # ensure the module-set has some name
                if module_set_name in seen_module_sets.keys():
                    logger_app.error(f"Duplicate group {module_set_name} in {rcfile}.")
                    raise ConfigError(f"Duplicate group {module_set_name} defined in {rcfile}")

                if module_set_name in seen_modules.keys():
                    logger_app.error(f"Name {module_set_name} for group in {rcfile} is already in use on a project")
                    raise ConfigError(f"Can't re-use name {module_set_name} for group defined in {rcfile}")

                # A module_set can give us more than one module to add.
                new_module_set: ModuleSet = ModuleSet(ctx, module_set_name)
                new_module_set.apply_config_options(ctx, node, config_filename)

                # Transforming the new_module_set into the right "class".
                # Possibly it is better to construct an entirely new object and copy the members over.
                # But we will do it this way for now.
                if new_module_set.get_option("repository") == Application.KDE_PROJECT_ID:
                    new_module_set.__class__ = ModuleSetKDEProjects
                elif new_module_set.get_option("repository") == Application.QT_PROJECT_ID:
                    new_module_set.__class__ = ModuleSetQt5

                creation_order += 1
                new_module_set.start_for_create_id = creation_order

                # Save "use-projects" entries, so we can see if later module decls
                # are overriding/overlaying their options.
                module_set_items = new_module_set.module_names_to_find()
                # seen_module_set_items = {item: new_module_set for item in module_set_items}

                # Reserve enough "create IDs" for all named modules to use
                creation_order += len(module_set_items)
                seen_module_sets[module_set_name] = new_module_set

                module_and_module_set_list.append(new_module_set)
                nothing_defined = False

            if node_name.startswith("project "):
                module_name = node_name.split(" ", maxsplit=1)[1]
                assert module_name  # ensure the module has some name
                if module_name in seen_modules:
                    logger_app.error(f"Duplicate project declaration b[r[{module_name}] in {config_filename}")
                    raise ConfigError(f"Duplicate project {module_name} declared in {config_filename}")
                if module_name in seen_module_sets:
                    logger_app.error(f"Name {module_name} for project in {config_filename} is already in use on a group")
                    raise ConfigError(f"Can't re-use name {module_name} for project defined in {config_filename}")

                new_module: Module = Module(ctx, module_name)
                new_module.apply_config_options(ctx, node, config_filename)
                if new_module.get_option("repository") == Application.KDE_PROJECT_ID:
                    new_module.set_scm_type("proj")
                else:
                    new_module.set_scm_type("git")
                new_module.create_id = creation_order + 1
                creation_order += 1
                seen_modules[module_name] = new_module

                module_and_module_set_list.append(new_module)
                nothing_defined = False

            if node_name.startswith("override "):
                options_name = node_name.split(" ", maxsplit=1)[1]
                assert options_name  # ensure the options has some name
                options: OptionsBase = OptionsBase(ctx)
                options.apply_config_options(ctx, node, config_filename)

                deferred_options.append({
                    "name": options_name,
                    "opts": options.options
                })

                # NOTE: There is no duplicate options block checking here, and we now currently rely on there being no duplicate checks to allow
                # for things like kf5-common-options.ksb to be included multiple times.
                continue  # Don't add to module list

        for name, module_set in seen_module_sets.items():
            pass

        # If the user doesn't ask to build any modules, build a default set.
        # The good question is what exactly should be built, but oh well.
        if nothing_defined:
            logger_app.warning(" b[y[*] There do not seem to be any projects to build in your configuration.")

        return module_and_module_set_list, deferred_options

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
            raise KBRuntimeError("Both --resume-after and --resume-from specified.")

        if ctx.get_option("stop-before") and ctx.get_option("stop-after"):
            # This one's an error.
            logger_app.error(textwrap.dedent("""\
            You specified both r[b[--stop-before] and r[b[--stop-after] but you can only
            use one.
            """))
            raise KBRuntimeError("Both --stop-before and --stop-from specified.")

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
            raise KBRuntimeError(f"Unknown resume -> stop point {resume_point} -> {stop_point}.")

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

            if re.search(r"/cmake\.log$", logfile) or re.search(r"/meson-setup\.log$", logfile):
                module_names.append(module.name)

        if len(module_names) > 0:
            names = ", ".join(module_names)
            logger_app.warning(textwrap.dedent(f"""
            Possible solution: Install the build dependencies for the projects:
            {names}
            You can use "sudo apt build-dep <source_package>", "sudo dnf builddep <package>", "sudo zypper --plus-content repo-source source-install --build-deps-only <source_package>" or a similar command for your distro of choice.
            See https://develop.kde.org/docs/getting-started/building/help-dependencies"""))

    @staticmethod
    def _print_failed_modules_in_each_phase(ctx: BuildContext, module_graph: dict) -> None:
        """
        Print the list of failed modules for each phase.

        It will also display the log file name if one can be determined.

        No message is printed out if the list of failed modules for the phase is empty, so this
        function can be called unconditionally.

        Args:
            ctx: Build context
            module_graph: The module graph.
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

            if not failures:
                continue

            logger_app.warning(f"\nr[b[<<<  PROJECTS FAILED TO {phase.upper()}  >>>]")

            for module in failures:
                out_str = f"r[{module}]"
                if not Debug().pretending():
                    logfile = module.get_option("#error-log-file")

                    # async updates may cause us not to have an error log file stored. There is only
                    # one place it should be though, take advantage of side-effect of log_command() to find it.
                    if not logfile:
                        logdir = module.get_log_dir() + "/error.log"
                        if os.path.exists(logdir):
                            logfile = logdir
                        else:
                            logfile = "No log file"
                    out_str += f" - g[{logfile}]"

                logger_app.warning(out_str)

        # See if any modules fail continuously and warn specifically for them.
        recurring_build_fails_modules = [module for module in ctx.modules if (module.get_persistent_option("failure-count") or 0) > 3 and module.phases.has("build")]

        for m in recurring_build_fails_modules:
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
            raise KBRuntimeError(f"Unable to open template source {source_path}: {e}")

        try:
            output_file = open(destination_path, "w")
        except OSError as e:
            raise KBRuntimeError(f"Unable to open template output {destination_path}: {e}")

        for line in input_file:
            if line is None:
                os.unlink(destination_path)
                raise KBRuntimeError(f"Failed to read from {source_path} at line {input_file.filelineno()}")

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
                        raise KBRuntimeError(f"Invalid variable {match.group(1)}")
                    return optval

                line = re.sub(pattern, repl(), line)  # Replace all matching expressions, use extended regexp with comments, and replacement is Python code to execute.

            try:
                output_file.write(line)
            except Exception as e:
                raise KBRuntimeError(f"Unable to write line to {destination_path}: {e}")

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
                if not Debug().pretending():
                    shutil.copy(dest_file_path, f"{dest_file_path}.kde-builder-backup")

        if not Debug().pretending():
            Application._install_templated_file(source_file_path, dest_file_path, ctx)
            ctx.set_persistent_option("/digests", md5_key_name, hashlib.md5(open(dest_file_path, "rb").read()).hexdigest())

    def install_login_session(self) -> int:
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
            p = subprocess.run([install_sessions_script])
            if p.returncode != 0:
                logger_app.error(" r[*] Install login sessions script failed. Please run kde-builder with y[--install-login-session-only] option to rerun it.")
                return p.returncode
            else:
                logger_app.warning(" b[*] Install login sessions script finished.")
                return 0
        else:
            logger_app.debug(" b[*] No need to run install-sessions.sh, all files are already installed and up to date.")
            return 0

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
                the projects: y[{", ".join(modules_needing)}].

                Please ensure the development packages for
                {req_package} are installed by using your distribution's package manager.
                """))
        return not was_error

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
                    logger_app.info("Would hold performance profile")
                    return

                logger_app.info("Holding performance profile")

                service = system_bus.get_object("org.freedesktop.UPower.PowerProfiles", "/org/freedesktop/UPower/PowerProfiles")
                ppd = dbus.Interface(service, "org.freedesktop.UPower.PowerProfiles")

                # The hold will be automatically released once kde-builder exits
                ppd.HoldProfile("performance", f"building projects (pid: {self._base_pid})", "kde-builder")

                session_bus = dbus.SessionBus()
                proxy = session_bus.get_object("org.freedesktop.PowerManagement", "/org/freedesktop/PowerManagement/Inhibit")
                iface = dbus.Interface(proxy, "org.freedesktop.PowerManagement.Inhibit")

                # The inhibition will be automatically released once kde-builder exits
                iface.Inhibit("kde-builder", "Building projects")

            except dbus.DBusException as e:
                logger_app.warning(f"Error accessing dbus: {e}")
        except ImportError:  # even though the import is going ok even in case python-dbus is not installed, just to be safe, will catch import error
            logger_app.warning("Could not import dbus module. Skipping dbus calls.")
            return
