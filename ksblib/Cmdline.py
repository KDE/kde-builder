# SPDX-FileCopyrightText: 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import re
import argparse
import textwrap
from typing import NoReturn

from .BuildContext import BuildContext
from .Debug import kbLogger
from .PhaseList import PhaseList
from .OSSupport import OSSupport
from .Version import Version

logger_app = kbLogger.getLogger("application")


class Cmdline:
    """
    This class centralizes handling of command line options, to simplify handling
    of user command input, for automated testing using mock command lines, and to
    speed up simple operations by separating command line argument parsing from the
    heavyweight module list generation process.

    Since kde-builder is intended to be non-interactive once it starts, the
    command-line is the primary interface to change program execution and has some
    complications as a result.

    Example:
    ::

        # may exit! for things like --help, --version
        opts = Cmdline.readCommandLineOptionsAndSelectors()

        ctx.setOption(**opts["opts"]["global"])

        module_list = lookForModSelectors(*opts["selectors"])

        if opts["run_mode"] == 'query':
        # handle query option
        exit(0)

        # ... let's build
        for module in module_list:
        # override module options from rc-file
        module.setOption(**opts["opts"][module.name])

    At the command line, the user can specify things like:
        * Modules or module-sets to build (by name)
        * Command line options (such as ``--pretend`` or ``--no-src``), which normally apply globally (i.e. overriding module-specific options in the config file)
        * Command line options that apply to specific modules (using ``--set-module-option-value``)
        * Build modes (install, build only, query)
        * Modules to *ignore* building, using ``--ignore-modules``, which gobbles up all remaining options.
    """

    def __init__(self):
        pass

    def readCommandLineOptionsAndSelectors(self, options: list) -> dict:
        """
        This function decodes the command line options passed into it and returns a
        dictionary describing what actions to take.

        The resulting object will be shaped as follows:
        ::

            returned_dict = {
                "opts": { # see BuildContext's "internalGlobalOptions"
                    'global': {
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
        foundOptions = {}

        parser = argparse.ArgumentParser(add_help=False)

        # Create a code as a string, containing functions to be run for flag options
        flag_handlers = ""
        for key in BuildContext().GlobalOptions_with_negatable_form.keys():
            if key == "async":  # as async is reserved word in python, we use such way to access it
                flag_handlers += textwrap.dedent("""\
                    if vars(args)["async"] is not None:
                        foundOptions["async"] = vars(args)["async"]
                    """)
                continue

            optName = key.replace("-", "_")

            flag_handlers += textwrap.dedent(f"""\
            if args.{optName} is not None:
                foundOptions[\"{key}\"] = args.{optName}
            """)

        # Similar procedure for global options (they require one argument)
        global_opts_handler = ""
        for key in BuildContext().GlobalOptions_with_parameter.keys():
            optName = key.replace("-", "_")

            global_opts_handler += textwrap.dedent(f"""\
            if args.{optName}:
                foundOptions[\"{key}\"] = args.{optName}[0]
            """)

        supportedOptions = Cmdline._supportedOptions()

        # If we have --run option, grab all the rest arguments to pass to the corresponding parser.
        # This way the arguments after --run could start with "-" or "--".
        run_index = -1
        for i in list(range(0, len(options))):
            if options[i] == "--run" or options[i] == "--start-program":
                run_index = i
                break

        if run_index != -1:
            foundOptions["no-metadata"] = True  # Implied --no-metadata
            opts["start-program"] = options[run_index + 1:len(options)]
            options = options[0:run_index]  # remove all after --run, and the --run itself # pl2py: in python the stop index is not included, so we add +1

            if not opts["start-program"]:  # check this here, because later the empty list will be treated as not wanting to start program
                logger_app.error("You need to specify a module with the --run option")
                exit(1)  # Do not continue

        supportedOptions.remove("set-module-option-value=s")  # specify differently, allowing it to be repeated in cmdline
        parser.add_argument("--set-module-option-value", type=lambda x: x.split(",", 2), action="append")

        # Generate the code as a string with `parser.add_argument(...) ...`.
        # This is done by parsing supportedOptions and extracting option variants (long, alias, short ...), parameter numbers and default values.
        string_of_parser_add_arguments = ""
        for key in supportedOptions:
            # global flags and global options are not duplicating options defined in options in _supportedOptions(). That function ensures that.

            line = key
            nargs = None
            action = None
            if line.endswith("=s"):
                nargs = 1
                line = line.removesuffix("=s")
            elif line.endswith("!"):  # negatable boolean
                action = "argparse.BooleanOptionalAction"
                line = line.removesuffix("!")
            elif line.endswith("=s{,}"):  # one or more option values
                nargs = "\"+\""
                line = line.removesuffix("=s{,}")
            elif line.endswith(":s"):  # optional string argument
                nargs = "\"?\""
                line = line.removesuffix(":s")
            elif line.endswith("=i"):
                nargs = 1
                line = line.removesuffix("=i")
            elif line.endswith(":10"):  # for --nice
                nargs = "\"?\""
                nargs += ", default=10"
                line = line.removesuffix(":10")
            else:  # for example, for "-p" to not eat selector.
                action = "\"store_true\""

            parts = line.split("|")
            dashed_parts = []
            for part in parts:
                if len(part) == 1:
                    dashed_parts.append("\"-" + part + "\"")
                else:
                    dashed_parts.append("\"--" + part + "\"")

            specstr = ", ".join(dashed_parts)
            if nargs:
                specstr += f", nargs={nargs}"
            elif action:
                specstr += f", action={action}"

            # example of string: parser.add_argument("--show-info", action='store_true')
            string_of_parser_add_arguments += textwrap.dedent(f"""\
            parser.add_argument({specstr})
            """)
        exec(string_of_parser_add_arguments)

        # Actually read the options.
        args, unknown_args = parser.parse_known_args(options)  # unknown_args - Required to read non-option args

        # <editor-fold desc="arg functions">
        if args.show_info:
            self._showInfoAndExit()
        if args.version:
            self._showVersionAndExit()
        if args.show_options_specifiers:
            self._showOptionsSpecifiersAndExit()
        if args.help:
            self._showHelpAndExit()
        if args.d:
            foundOptions["include-dependencies"] = True
        if args.D:
            foundOptions["include-dependencies"] = False
        if args.uninstall:
            opts["run_mode"] = "uninstall"
            phases.phases(["uninstall"])
        if args.no_src:
            phases.filterOutPhase("update")
        if args.no_install:
            phases.filterOutPhase("install")
        if args.no_tests:
            # The "right thing" to do
            phases.filterOutPhase("test")
            # What actually works at this point.
            foundOptions["run-tests"] = False
        if args.no_build:
            phases.filterOutPhase("build")
        # Mostly equivalent to the above
        if args.src_only:
            phases.phases(["update"])
        if args.build_only:
            phases.phases(["build"])
        if args.install_only:
            opts["run_mode"] = "install"
            phases.phases(["install"])
        if args.install_dir:
            foundOptions["install-dir"] = args.install_dir[0]
            foundOptions["reconfigure"] = True
        if args.query:
            arg = args.query[0]

            validMode = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_-]*$")
            if not validMode.match(arg):
                raise ValueError(f"Invalid query mode {arg}")

            opts["run_mode"] = "query"
            foundOptions["query"] = arg
            foundOptions["pretend"] = True  # Implied pretend mode
        if args.pretend:
            # Set pretend mode but also force the build process to run.
            foundOptions["pretend"] = True
            foundOptions["build-when-unchanged"] = True
        if args.resume or args.resume_refresh_build_first:
            foundOptions["resume"] = True
            phases.filterOutPhase("update")  # Implied --no-src
            foundOptions["no-metadata"] = True  # Implied --no-metadata
            # Imply --no-include-dependencies, because when resuming, user wants to continue from exact same modules list
            # as saved in global persistent option "resume-list". Otherwise, some dependencies that have already passed the build successfully,
            # (i.e. those that were before the first item of resume list) may appear in modules list again (if some module from the
            # resume list requires such modules).
            foundOptions["include-dependencies"] = False

        # Hack to set module options
        if args.set_module_option_value:
            for module, option, value in args.set_module_option_value:
                if module and option:
                    if module not in opts["opts"]:
                        opts["opts"][module] = {}
                    opts["opts"][module][option] = value
        if args.ignore_modules:
            foundOptions["ignore-modules"] = args.ignore_modules
        # </editor-fold desc="arg functions">
        exec(flag_handlers)
        exec(global_opts_handler)

        # Module selectors (i.e. an actual argument)
        for unknown_arg in unknown_args:
            opts["selectors"].append(unknown_arg)

        # Don't get ignore-modules confused with global options
        protectedKeys = ["ignore-modules"]
        for key in protectedKeys:
            if key in foundOptions:
                opts[key] = foundOptions[key]
                del foundOptions[key]

        # <editor-fold desc="all other args handlers">
        if args.build_system_only:
            foundOptions["build-system-only"] = True

        if args.build_when_unchanged is not None:
            foundOptions["build-when-unchanged"] = args.build_when_unchanged

        if args.colorful_output is not None:
            foundOptions["colorful-output"] = args.colorful_output

        if args.dependency_tree:
            foundOptions["dependency-tree"] = True

        if args.dependency_tree_fullpath:
            foundOptions["dependency-tree-fullpath"] = True

        if args.directory_layout is not None:
            foundOptions["directory-layout"] = args.directory_layout[0]

        if args.include_dependencies is not None:
            foundOptions["include-dependencies"] = args.include_dependencies

        if args.list_installed:
            foundOptions["list-installed"] = True

        if args.metadata_only:
            foundOptions["metadata-only"] = True

        if args.niceness != 10:
            foundOptions["niceness"] = args.niceness

        if args.no_metadata:
            foundOptions["no-metadata"] = True

        if args.rc_file is not None:
            foundOptions["rc-file"] = args.rc_file[0]

        if args.rebuild_failures:
            foundOptions["rebuild-failures"] = True

        if args.reconfigure:
            foundOptions["reconfigure"] = True

        if args.refresh_build:
            foundOptions["refresh-build"] = True

        if args.refresh_build_first or args.resume_refresh_build_first:
            foundOptions["refresh-build-first"] = True

        if args.resume_after is not None:
            foundOptions["resume-after"] = args.resume_after[0]

        if args.resume_from is not None:
            foundOptions["resume-from"] = args.resume_from[0]

        if args.revision is not None:
            foundOptions["revision"] = args.revision[0]

        if args.stop_after is not None:
            foundOptions["stop-after"] = args.stop_after[0]

        if args.stop_before is not None:
            foundOptions["stop-before"] = args.stop_before[0]

        if args.binpath is not None:
            foundOptions["binpath"] = args.binpath[0]

        if args.branch is not None:
            foundOptions["branch"] = args.branch[0]

        if args.branch_group is not None:
            foundOptions["branch-group"] = args.branch_group[0]

        if args.build_dir is not None:
            foundOptions["build-dir"] = args.build_dir[0]

        if args.cmake_generator is not None:
            foundOptions["cmake-generator"] = args.cmake_generator[0]

        if args.cmake_options is not None:
            foundOptions["cmake-options"] = args.cmake_options[0]

        if args.cmake_toolchain is not None:
            foundOptions["cmake-toolchain"] = args.cmake_toolchain[0]

        if args.configure_flags is not None:
            foundOptions["configure-flags"] = args.configure_flags[0]

        if args.custom_build_command is not None:
            foundOptions["custom-build-command"] = args.custom_build_command[0]

        if args.cxxflags is not None:
            foundOptions["cxxflags"] = args.cxxflags[0]

        if args.dest_dir is not None:
            foundOptions["dest-dir"] = args.dest_dir[0]

        if args.do_not_compile is not None:
            foundOptions["do-not-compile"] = args.do_not_compile[0]

        if args.http_proxy is not None:
            foundOptions["http-proxy"] = args.http_proxy[0]

        if args.libname is not None:
            foundOptions["libname"] = args.libname[0]

        if args.libpath is not None:
            foundOptions["libpath"] = args.libpath[0]

        if args.log_dir is not None:
            foundOptions["log-dir"] = args.log_dir[0]

        if args.make_install_prefix is not None:
            foundOptions["make-install-prefix"] = args.make_install_prefix[0]

        if args.make_options is not None:
            foundOptions["make-options"] = args.make_options[0]

        if args.ninja_options is not None:
            foundOptions["ninja-options"] = args.ninja_options[0]

        if args.num_cores is not None:
            foundOptions["num-cores"] = args.num_cores[0]

        if args.num_cores_low_mem is not None:
            foundOptions["num-cores-low-mem"] = args.num_cores_low_mem[0]

        if args.override_build_system is not None:
            foundOptions["override-build-system"] = args.override_build_system[0]

        if args.persistent_data_file is not None:
            foundOptions["persistent-data-file"] = args.persistent_data_file[0]

        if args.qmake_options is not None:
            foundOptions["qmake-options"] = args.qmake_options[0]

        if args.qt_install_dir is not None:
            foundOptions["qt-install-dir"] = args.qt_install_dir[0]

        if args.remove_after_install is not None:
            foundOptions["remove-after-install"] = args.remove_after_install[0]

        if args.source_dir is not None:
            foundOptions["source-dir"] = args.source_dir[0]

        if args.tag is not None:
            foundOptions["tag"] = args.tag[0]

        # </editor-fold desc="all other args handlers">

        opts["opts"]["global"].update(foundOptions)
        opts["phases"] = phases.phases()
        return opts

    @staticmethod
    def _showVersionAndExit() -> NoReturn:
        version = "kde-builder " + Version.scriptVersion()
        print(version)
        exit()

    @staticmethod
    def _showHelpAndExit() -> NoReturn:
        print(textwrap.dedent("""\
        KDE Builder tool automates the download, build, and install process for KDE software using the latest available source code.

        Documentation: https://kde-builder.kde.org
            Supported command-line parameters:              https://kde-builder.kde.org/en/cmdline/supported-cmdline-params.html
            Table of available configuration options:       https://kde-builder.kde.org/en/kdesrc-buildrc/conf-options-table.html
        """))
        exit()

    @staticmethod
    def _showInfoAndExit() -> NoReturn:
        os_vendor = OSSupport().vendorID()
        version = "kde-builder " + Version.scriptVersion()
        print(textwrap.dedent(f"""\
            {version}
            OS: {os_vendor}"""))
        exit()

    @staticmethod
    def _showOptionsSpecifiersAndExit() -> NoReturn:
        supportedOptions = Cmdline._supportedOptions()

        # The initial setup options are handled outside the Cmdline (in the starting script).
        initial_options = ["initial-setup", "install-distro-packages", "generate-config"]

        for option in [*supportedOptions, *initial_options, "debug"]:
            print(option)

        exit()

    phase_changing_options = [
        "build-only",
        "install-only",
        "no-build",
        "no-install",
        "no-src|S",
        "no-tests",
        "src-only|s",
        "uninstall",
    ]

    @staticmethod
    def _supportedOptions() -> list:
        """
        Return option names ready to be fed into GetOptionsFromArray
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
        optNames = [re.search(r"([a-zA-Z-]+)", option).group(1) for option in options]

        # Make sure this doesn't overlap with BuildContext default flags and options
        optsSeen = {optName: 1 for optName in optNames}

        for key in BuildContext().GlobalOptions_with_negatable_form:
            optsSeen[key] = optsSeen.get(key, 0) + 1

        for key in BuildContext().GlobalOptions_with_parameter:
            optsSeen[key] = optsSeen.get(key, 0) + 1

        for key in BuildContext().GlobalOptions_without_parameter:
            optsSeen[key] = optsSeen.get(key, 0) + 1

        violators = [key for key, value in optsSeen.items() if value > 1]
        if violators:
            errmsg = "The following options overlap in Cmdline: [" + ", ".join(violators) + "]!"
            raise Exception(errmsg)

        # Now, place the rest of the options, that have specifier dependent on group
        options.extend([
            *[f"{key}!" for key in BuildContext().GlobalOptions_with_negatable_form],
            *[f"{key}=s" for key in BuildContext().GlobalOptions_with_parameter],
            *[f"{key}" for key in BuildContext().GlobalOptions_without_parameter]
        ])

        return options
