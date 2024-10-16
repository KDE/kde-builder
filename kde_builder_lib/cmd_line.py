# SPDX-FileCopyrightText: 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import re
import textwrap
from typing import NoReturn

from .build_context import BuildContext
from .debug import KBLogger
from .os_support import OSSupport
from .phase_list import PhaseList
from .version import Version

logger_app = KBLogger.getLogger("application")


class Cmdline:
    """
    Centralizes handling of command line options.

    Needed to simplify handling of user command input, for automated testing using mock command lines, and to
    speed up simple operations by separating command line argument parsing from the
    heavyweight module list generation process.

    Since kde-builder is intended to be non-interactive once it starts, the
    command-line is the primary interface to change program execution and has some
    complications as a result.

    Example:
    ::

        # may exit! for things like --help, --version
        opts = Cmdline.read_command_line_options_and_selectors()

        ctx.set_option(**opts["opts"]["global"])

        module_list = lookForModSelectors(*opts["selectors"])

        if opts["run_mode"] == "query":
        # handle query option
        exit(0)

        # ... let's build
        for module in module_list:
        # override module options from rc-file
        module.set_option(**opts["opts"][module.name])

    At the command line, the user can specify things like:
        * Modules or module-sets to build (by name)
        * Command line options (such as ``--pretend`` or ``--no-src``), which normally apply globally (i.e. overriding module-specific options in the config file)
        * Command line options that apply to specific modules (using ``--set-module-option-value``)
        * Build modes (install, build only, query)
        * Modules to *ignore* building, using ``--ignore-modules``, which gobbles up all remaining options.
    """

    def __init__(self):
        pass

    def read_command_line_options_and_selectors(self, options: list[str]) -> dict:
        """
        Decode the command line options passed into it and return a dictionary describing what actions to take.

        The resulting object will be shaped as follows:
        ::

            returned_dict = {
                "opts": { # see BuildContext's "internalGlobalOptions"
                    "global": {
                        # Always present even if no options read in
                        "opt-name": "opt-value",
                        ...
                    },
                    "modulename": {
                        "opt-name": "opt-value",
                        ...
                    },
                    ...
                },
                "phases": ["update", "build", ..., "install"],
                "run_mode": "build", # or "install", "uninstall", or "query"
                "selectors": [
                    "juk",
                    "frameworks-set",
                    # etc.  MAY BE EMPTY in which case the command should build everything known
                ],
                "ignore-modules": [
                    "plasma-nm",
                    "plasma-mobile",
                    # etc.  MAY BE EMPTY in which case no modules should be stripped from a module-set
                ],
                "start-program": [
                    "cmd",
                    "--opt1",
                    "value",
                    # etc.  USUALLY EMPTY
                ],
            }

        Note this function may throw an exception in the event of an error, or exit the
        program entirely.
        """
        phases = PhaseList()
        opts = {
            "opts": {"global": {}},
            "phases": [],
            "run_mode": "build",
            "selectors": [],
            "ignore-modules": [],
            "start-program": [],
        }
        found_options = {}

        parser = argparse.ArgumentParser(add_help=False)

        # If we have --run option, grab all the rest arguments to pass to the corresponding parser.
        # This way the arguments after --run could start with "-" or "--".
        run_index = -1
        for i in list(range(0, len(options))):
            if options[i] == "--run" or options[i] == "--start-program":
                run_index = i
                break

        if run_index != -1:
            found_options["no-metadata"] = True  # Implied --no-metadata
            opts["start-program"] = options[run_index + 1:len(options)]
            options = options[0:run_index]  # remove all after --run, and the --run itself # pl2py: in python the stop index is not included, so we add +1

            if not opts["start-program"]:  # check this here, because later the empty list will be treated as not wanting to start program
                logger_app.error("You need to specify a module with the --run option")
                exit(1)  # Do not continue

        # <editor-fold desc="Adding parser arguments">
        parser.add_argument("--set-module-option-value", type=lambda x: x.split(",", 2), action="append")  # allowing it to be repeated in cmdline
        parser.add_argument("--dependency-tree", action="store_true")
        parser.add_argument("--dependency-tree-fullpath", action="store_true")
        parser.add_argument("--help", "-h", action="store_true")
        parser.add_argument("--list-installed", action="store_true")
        parser.add_argument("--no-metadata", "-M", action="store_true")
        parser.add_argument("--query", nargs=1)
        parser.add_argument("--rc-file", nargs=1)
        parser.add_argument("--rebuild-failures", action="store_true")
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--resume-after", "--after", "-a", nargs=1)
        parser.add_argument("--resume-from", "--from", "-f", nargs=1)
        parser.add_argument("--resume-refresh-build-first", "-R", action="store_true")
        parser.add_argument("--show-info", action="store_true")
        parser.add_argument("--show-options-specifiers", action="store_true")
        parser.add_argument("--stop-after", "--to", nargs=1)
        parser.add_argument("--stop-before", "--until", nargs=1)
        parser.add_argument("--version", "-v", action="store_true")
        parser.add_argument("--build-only", action="store_true")
        parser.add_argument("--install-only", action="store_true")
        parser.add_argument("--no-build", action="store_true")
        parser.add_argument("--no-install", action="store_true")
        parser.add_argument("--no-src", "-S", action="store_true")
        parser.add_argument("--src-only", "-s", action="store_true")
        parser.add_argument("--uninstall", action="store_true")
        parser.add_argument("--build-when-unchanged", "--force-build", action=argparse.BooleanOptionalAction)
        parser.add_argument("--colorful-output", "--color", action=argparse.BooleanOptionalAction)
        parser.add_argument("--ignore-modules", "-!", nargs="+")
        parser.add_argument("--niceness", "--nice", nargs="?", default=10)
        parser.add_argument("--pretend", "--dry-run", "-p", action="store_true")
        parser.add_argument("--refresh-build", "-r", action="store_true")
        parser.add_argument("-d", action="store_true")
        parser.add_argument("-D", action="store_true")
        parser.add_argument("--async", action=argparse.BooleanOptionalAction)
        parser.add_argument("--compile-commands-export", action=argparse.BooleanOptionalAction)
        parser.add_argument("--compile-commands-linking", action=argparse.BooleanOptionalAction)
        parser.add_argument("--delete-my-patches", action=argparse.BooleanOptionalAction)
        parser.add_argument("--delete-my-settings", action=argparse.BooleanOptionalAction)
        parser.add_argument("--disable-agent-check", action=argparse.BooleanOptionalAction)
        parser.add_argument("--generate-clion-project-config", action=argparse.BooleanOptionalAction)
        parser.add_argument("--generate-vscode-project-config", action=argparse.BooleanOptionalAction)
        parser.add_argument("--generate-qtcreator-project-config", action=argparse.BooleanOptionalAction)
        parser.add_argument("--include-dependencies", action=argparse.BooleanOptionalAction)
        parser.add_argument("--install-login-session", action=argparse.BooleanOptionalAction)
        parser.add_argument("--purge-old-logs", action=argparse.BooleanOptionalAction)
        parser.add_argument("--run-tests", action=argparse.BooleanOptionalAction)
        parser.add_argument("--stop-on-failure", action=argparse.BooleanOptionalAction)
        parser.add_argument("--use-clean-install", action=argparse.BooleanOptionalAction)
        parser.add_argument("--use-idle-io-priority", action=argparse.BooleanOptionalAction)
        parser.add_argument("--use-inactive-modules", action=argparse.BooleanOptionalAction)
        parser.add_argument("--binpath", nargs=1)
        parser.add_argument("--branch", nargs=1)
        parser.add_argument("--branch-group", nargs=1)
        parser.add_argument("--build-dir", nargs=1)
        parser.add_argument("--cmake-generator", nargs=1)
        parser.add_argument("--cmake-options", nargs=1)
        parser.add_argument("--cmake-toolchain", nargs=1)
        parser.add_argument("--configure-flags", nargs=1)
        parser.add_argument("--custom-build-command", nargs=1)
        parser.add_argument("--cxxflags", nargs=1)
        parser.add_argument("--directory-layout", nargs=1)
        parser.add_argument("--dest-dir", nargs=1)
        parser.add_argument("--do-not-compile", nargs=1)
        parser.add_argument("--install-dir", nargs=1)
        parser.add_argument("--libname", nargs=1)
        parser.add_argument("--libpath", nargs=1)
        parser.add_argument("--log-dir", nargs=1)
        parser.add_argument("--make-install-prefix", nargs=1)
        parser.add_argument("--make-options", nargs=1)
        parser.add_argument("--ninja-options", nargs=1)
        parser.add_argument("--num-cores", nargs=1)
        parser.add_argument("--num-cores-low-mem", nargs=1)
        parser.add_argument("--override-build-system", nargs=1)
        parser.add_argument("--persistent-data-file", nargs=1)
        parser.add_argument("--qmake-options", nargs=1)
        parser.add_argument("--qt-install-dir", nargs=1)
        parser.add_argument("--remove-after-install", nargs=1)
        parser.add_argument("--revision", nargs=1)
        parser.add_argument("--source-dir", nargs=1)
        parser.add_argument("--source-when-start-program", nargs=1)
        parser.add_argument("--tag", nargs=1)
        parser.add_argument("--build-system-only", action="store_true")
        parser.add_argument("--reconfigure", action="store_true")
        parser.add_argument("--refresh-build-first", action="store_true")
        parser.add_argument("--metadata-only", action="store_true")
        # </editor-fold desc="Adding parser arguments">

        # Actually read the options.
        args, unknown_args = parser.parse_known_args(options)  # unknown_args - Required to read non-option args

        # <editor-fold desc="arg functions">
        if args.show_info:
            self._show_info_and_exit()
        if args.version:
            self._show_version_and_exit()
        if args.show_options_specifiers:
            self._show_options_specifiers_and_exit()
        if args.help:
            self._show_help_and_exit()
        if args.d:
            found_options["include-dependencies"] = True
        if args.D:
            found_options["include-dependencies"] = False
        if args.uninstall:
            opts["run_mode"] = "uninstall"
            phases.reset_to(["uninstall"])
        if args.no_src:
            phases.filter_out_phase("update")
        if args.no_install:
            phases.filter_out_phase("install")
        if args.no_build:
            phases.filter_out_phase("build")
        # Mostly equivalent to the above
        if args.src_only:
            phases.reset_to(["update"])
        if args.build_only:
            phases.reset_to(["build"])
        if args.install_only:
            opts["run_mode"] = "install"
            phases.reset_to(["install"])
        if args.install_dir:
            found_options["install-dir"] = args.install_dir[0]
            found_options["reconfigure"] = True
        if args.query:
            arg = args.query[0]

            valid_mode = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_-]*$")
            if not valid_mode.match(arg):
                raise ValueError(f"Invalid query mode {arg}")

            opts["run_mode"] = "query"
            found_options["query"] = arg
            found_options["pretend"] = True  # Implied pretend mode
        if args.pretend:
            # Set pretend mode but also force the build process to run.
            found_options["pretend"] = True
            found_options["build-when-unchanged"] = True
        if args.resume or args.resume_refresh_build_first:
            found_options["resume"] = True
            phases.filter_out_phase("update")  # Implied --no-src
            found_options["no-metadata"] = True  # Implied --no-metadata
            # Imply --no-include-dependencies, because when resuming, user wants to continue from exact same modules list
            # as saved in global persistent option "resume-list". Otherwise, some dependencies that have already passed the build successfully,
            # (i.e. those that were before the first item of resume list) may appear in modules list again (if some module from the
            # resume list requires such modules).
            found_options["include-dependencies"] = False

        # Hack to set module options
        if args.set_module_option_value:
            for module, option, value in args.set_module_option_value:
                if module and option:
                    if module not in opts["opts"]:
                        opts["opts"][module] = {}
                    opts["opts"][module][option] = value
        if args.ignore_modules:
            found_options["ignore-modules"] = args.ignore_modules
        # </editor-fold desc="arg functions">

        # <editor-fold desc="global options with negatable form">
        if vars(args)["async"] is not None:
            found_options["async"] = vars(args)["async"]
        if args.compile_commands_export is not None:
            found_options["compile-commands-export"] = args.compile_commands_export
        if args.compile_commands_linking is not None:
            found_options["compile-commands-linking"] = args.compile_commands_linking
        if args.delete_my_patches is not None:
            found_options["delete-my-patches"] = args.delete_my_patches
        if args.delete_my_settings is not None:
            found_options["delete-my-settings"] = args.delete_my_settings
        if args.disable_agent_check is not None:
            found_options["disable-agent-check"] = args.disable_agent_check
        if args.generate_clion_project_config is not None:
            found_options["generate-clion-project-config"] = args.generate_clion_project_config
        if args.generate_vscode_project_config is not None:
            found_options["generate-vscode-project-config"] = args.generate_vscode_project_config
        if args.generate_qtcreator_project_config is not None:
            found_options["generate-qtcreator-project-config"] = args.generate_qtcreator_project_config
        if args.include_dependencies is not None:
            found_options["include-dependencies"] = args.include_dependencies
        if args.install_login_session is not None:
            found_options["install-login-session"] = args.install_login_session
        if args.purge_old_logs is not None:
            found_options["purge-old-logs"] = args.purge_old_logs
        if args.run_tests is not None:
            found_options["run-tests"] = args.run_tests
        if args.stop_on_failure is not None:
            found_options["stop-on-failure"] = args.stop_on_failure
        if args.use_clean_install is not None:
            found_options["use-clean-install"] = args.use_clean_install
        if args.use_idle_io_priority is not None:
            found_options["use-idle-io-priority"] = args.use_idle_io_priority
        if args.use_inactive_modules is not None:
            found_options["use-inactive-modules"] = args.use_inactive_modules
        # </editor-fold desc="global options with negatable form">

        # <editor-fold desc="global options with parameter">
        if args.binpath:
            found_options["binpath"] = args.binpath[0]
        if args.branch:
            found_options["branch"] = args.branch[0]
        if args.branch_group:
            found_options["branch-group"] = args.branch_group[0]
        if args.build_dir:
            found_options["build-dir"] = args.build_dir[0]
        if args.cmake_generator:
            found_options["cmake-generator"] = args.cmake_generator[0]
        if args.cmake_options:
            found_options["cmake-options"] = args.cmake_options[0]
        if args.cmake_toolchain:
            found_options["cmake-toolchain"] = args.cmake_toolchain[0]
        if args.configure_flags:
            found_options["configure-flags"] = args.configure_flags[0]
        if args.custom_build_command:
            found_options["custom-build-command"] = args.custom_build_command[0]
        if args.cxxflags:
            found_options["cxxflags"] = args.cxxflags[0]
        if args.directory_layout:
            found_options["directory-layout"] = args.directory_layout[0]
        if args.dest_dir:
            found_options["dest-dir"] = args.dest_dir[0]
        if args.do_not_compile:
            found_options["do-not-compile"] = args.do_not_compile[0]
        if args.install_dir:
            found_options["install-dir"] = args.install_dir[0]
        if args.libname:
            found_options["libname"] = args.libname[0]
        if args.libpath:
            found_options["libpath"] = args.libpath[0]
        if args.log_dir:
            found_options["log-dir"] = args.log_dir[0]
        if args.make_install_prefix:
            found_options["make-install-prefix"] = args.make_install_prefix[0]
        if args.make_options:
            found_options["make-options"] = args.make_options[0]
        if args.ninja_options:
            found_options["ninja-options"] = args.ninja_options[0]
        if args.num_cores:
            found_options["num-cores"] = args.num_cores[0]
        if args.num_cores_low_mem:
            found_options["num-cores-low-mem"] = args.num_cores_low_mem[0]
        if args.override_build_system:
            found_options["override-build-system"] = args.override_build_system[0]
        if args.persistent_data_file:
            found_options["persistent-data-file"] = args.persistent_data_file[0]
        if args.qmake_options:
            found_options["qmake-options"] = args.qmake_options[0]
        if args.qt_install_dir:
            found_options["qt-install-dir"] = args.qt_install_dir[0]
        if args.remove_after_install:
            found_options["remove-after-install"] = args.remove_after_install[0]
        if args.revision:
            found_options["revision"] = args.revision[0]
        if args.source_dir:
            found_options["source-dir"] = args.source_dir[0]
        if args.source_when_start_program:
            found_options["source-when-start-program"] = args.source_when_start_program[0]
        if args.tag:
            found_options["tag"] = args.tag[0]
        # </editor-fold desc="global options with parameter">

        # Module selectors (i.e. an actual argument)
        for unknown_arg in unknown_args:
            opts["selectors"].append(unknown_arg)

        # Don't get ignore-modules confused with global options
        protected_keys = ["ignore-modules"]
        for key in protected_keys:
            if key in found_options:
                opts[key] = found_options[key]
                del found_options[key]

        # <editor-fold desc="all other args handlers">
        if args.build_system_only:
            found_options["build-system-only"] = True

        if args.build_when_unchanged is not None:
            found_options["build-when-unchanged"] = args.build_when_unchanged

        if args.colorful_output is not None:
            found_options["colorful-output"] = args.colorful_output

        if args.dependency_tree:
            found_options["dependency-tree"] = True

        if args.dependency_tree_fullpath:
            found_options["dependency-tree-fullpath"] = True

        if args.directory_layout is not None:
            found_options["directory-layout"] = args.directory_layout[0]

        if args.include_dependencies is not None:
            found_options["include-dependencies"] = args.include_dependencies

        if args.list_installed:
            found_options["list-installed"] = True

        if args.metadata_only:
            found_options["metadata-only"] = True

        if args.niceness != "10":
            found_options["niceness"] = args.niceness

        if args.no_metadata:
            found_options["no-metadata"] = True

        if args.rc_file is not None:
            found_options["rc-file"] = args.rc_file[0]

        if args.rebuild_failures:
            found_options["rebuild-failures"] = True

        if args.reconfigure:
            found_options["reconfigure"] = True

        if args.refresh_build:
            found_options["refresh-build"] = True

        if args.refresh_build_first or args.resume_refresh_build_first:
            found_options["refresh-build-first"] = True

        if args.resume_after is not None:
            found_options["resume-after"] = args.resume_after[0]

        if args.resume_from is not None:
            found_options["resume-from"] = args.resume_from[0]

        if args.revision is not None:
            found_options["revision"] = args.revision[0]

        if args.stop_after is not None:
            found_options["stop-after"] = args.stop_after[0]

        if args.stop_before is not None:
            found_options["stop-before"] = args.stop_before[0]

        if args.binpath is not None:
            found_options["binpath"] = args.binpath[0]

        if args.branch is not None:
            found_options["branch"] = args.branch[0]

        if args.branch_group is not None:
            found_options["branch-group"] = args.branch_group[0]

        if args.build_dir is not None:
            found_options["build-dir"] = args.build_dir[0]

        if args.cmake_generator is not None:
            found_options["cmake-generator"] = args.cmake_generator[0]

        if args.cmake_options is not None:
            found_options["cmake-options"] = args.cmake_options[0]

        if args.cmake_toolchain is not None:
            found_options["cmake-toolchain"] = args.cmake_toolchain[0]

        if args.configure_flags is not None:
            found_options["configure-flags"] = args.configure_flags[0]

        if args.custom_build_command is not None:
            found_options["custom-build-command"] = args.custom_build_command[0]

        if args.cxxflags is not None:
            found_options["cxxflags"] = args.cxxflags[0]

        if args.dest_dir is not None:
            found_options["dest-dir"] = args.dest_dir[0]

        if args.do_not_compile is not None:
            found_options["do-not-compile"] = args.do_not_compile[0]

        if args.libname is not None:
            found_options["libname"] = args.libname[0]

        if args.libpath is not None:
            found_options["libpath"] = args.libpath[0]

        if args.log_dir is not None:
            found_options["log-dir"] = args.log_dir[0]

        if args.make_install_prefix is not None:
            found_options["make-install-prefix"] = args.make_install_prefix[0]

        if args.make_options is not None:
            found_options["make-options"] = args.make_options[0]

        if args.ninja_options is not None:
            found_options["ninja-options"] = args.ninja_options[0]

        if args.num_cores is not None:
            found_options["num-cores"] = args.num_cores[0]

        if args.num_cores_low_mem is not None:
            found_options["num-cores-low-mem"] = args.num_cores_low_mem[0]

        if args.override_build_system is not None:
            found_options["override-build-system"] = args.override_build_system[0]

        if args.persistent_data_file is not None:
            found_options["persistent-data-file"] = args.persistent_data_file[0]

        if args.qmake_options is not None:
            found_options["qmake-options"] = args.qmake_options[0]

        if args.qt_install_dir is not None:
            found_options["qt-install-dir"] = args.qt_install_dir[0]

        if args.remove_after_install is not None:
            found_options["remove-after-install"] = args.remove_after_install[0]

        if args.source_dir is not None:
            found_options["source-dir"] = args.source_dir[0]

        if args.tag is not None:
            found_options["tag"] = args.tag[0]

        # </editor-fold desc="all other args handlers">

        opts["opts"]["global"].update(found_options)
        opts["phases"] = phases.phaselist
        return opts

    @staticmethod
    def _show_version_and_exit() -> NoReturn:
        version = "kde-builder " + Version.script_version()
        print(version)
        exit()

    @staticmethod
    def _show_help_and_exit() -> NoReturn:
        print(textwrap.dedent("""\
        KDE Builder tool automates the download, build, and install process for KDE software using the latest available source code.

        Documentation: https://kde-builder.kde.org
            Supported command-line parameters:              https://kde-builder.kde.org/en/cmdline/supported-cmdline-params.html
            Table of available configuration options:       https://kde-builder.kde.org/en/kdesrc-buildrc/conf-options-table.html
        """))
        exit()

    @staticmethod
    def _show_info_and_exit() -> NoReturn:
        os_vendor = OSSupport().vendor_id()
        version = "kde-builder " + Version.script_version()
        print(textwrap.dedent(f"""\
            {version}
            OS: {os_vendor}"""))
        exit()

    @staticmethod
    def _show_options_specifiers_and_exit() -> NoReturn:
        supported_options = Cmdline._supported_options()

        # The initial setup options are handled outside the Cmdline (in the starting script).
        initial_options = ["initial-setup", "install-distro-packages", "generate-config"]

        for option in [*supported_options, *initial_options, "debug"]:
            print(option)

        exit()

    phase_changing_options = [
        "build-only",
        "install-only",
        "no-build",
        "no-install",
        "no-src|S",
        "src-only|s",
        "uninstall",
    ]

    @staticmethod
    def _supported_options() -> list[str]:
        """
        Return option names ready to be fed into GetOptionsFromArray.
        """
        # See https://perldoc.perl.org/5.005/Getopt::Long for options specification format

        non_context_options = [
            "dependency-tree",
            "dependency-tree-fullpath",
            "help|h",
            "list-installed",
            "no-metadata|M",
            "query=s",
            "rc-file=s",
            "rebuild-failures",
            "resume",
            "resume-after|after|a=s",
            "resume-from|from|f=s",
            "resume-refresh-build-first|R",
            "set-module-option-value=s",
            "show-info",
            "show-options-specifiers",
            "stop-after|to=s",
            "stop-before|until=s",
            "version|v",
        ]

        context_options_with_extra_specifier = [
            "build-when-unchanged|force-build!",
            "colorful-output|color!",
            "ignore-modules|!=s{,}",
            "niceness|nice:10",
            "pretend|dry-run|p",
            "refresh-build|r",
        ]

        options_converted_to_canonical = [
            "d",  # --include-dependencies, which is already pulled in via `BuildContext` default Global Flags
            "D",  # --no-include-dependencies, which is already pulled in via `BuildContext` default Global Flags
        ]

        # For now, place the options we specified above
        options = [*non_context_options, *Cmdline.phase_changing_options, *context_options_with_extra_specifier, *options_converted_to_canonical]

        # Remove stuff like ! and =s from list above;
        opt_names = [re.search(r"([a-zA-Z-]+)", option).group(1) for option in options]

        # Make sure this doesn't overlap with BuildContext default flags and options
        opts_seen = {optName: 1 for optName in opt_names}

        for key in BuildContext().global_options_with_negatable_form:
            opts_seen[key] = opts_seen.get(key, 0) + 1

        for key in BuildContext().global_options_with_parameter:
            opts_seen[key] = opts_seen.get(key, 0) + 1

        for key in BuildContext().global_options_without_parameter:
            opts_seen[key] = opts_seen.get(key, 0) + 1

        violators = [key for key, value in opts_seen.items() if value > 1]
        if violators:
            errmsg = "The following options overlap in Cmdline: [" + ", ".join(violators) + "]!"
            raise Exception(errmsg)

        # Now, place the rest of the options, that have specifier dependent on group
        options.extend([
            *[f"{key}!" for key in BuildContext().global_options_with_negatable_form],
            *[f"{key}=s" for key in BuildContext().global_options_with_parameter],
            *[f"{key}" for key in BuildContext().global_options_without_parameter]
        ])

        return options
