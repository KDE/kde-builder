# SPDX-FileCopyrightText: 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import re
from typing import NoReturn

from kde_builder.build_context import BuildContext
from kde_builder.debug import KBLogger
from kde_builder.options_spec import OptionsSpec
from kde_builder.os_support import OSSupport
from kde_builder.phase_list import PhaseList
from kde_builder.util.textwrap_mod import dedent
from kde_builder.version import Version

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

    At the command line, the user can specify things like:
        * Modules or module-sets to build (by name)
        * Command line options (such as ``--pretend`` or ``--no-src``), which normally apply globally (i.e. overriding module-specific options in the config file)
        * Command line options that apply to specific projects (using ``--set-project-option-value``)
        * Build modes (install, build only, query)
        * Modules to *ignore* building, using ``--ignore-projects``, which gobbles up all remaining options.
    """

    def __init__(self):
        pass

    def read_command_line_options_and_selectors(self, options: list[str]) -> dict:
        """
        Decode the command line options passed into it and return a dictionary describing what actions to take.

        The resulting object will be shaped as follows:
        ::

            returned_dict = {
                "global": {
                    "opt-name": "opt-value",
                    ...
                },
                "per_project": {
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
                "ignore-projects": [
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
            "global": {},
            "per_project": {},
            "phases": [],
            "run_mode": "build",
            "selectors": [],
            "special-selectors": [],
            "ignore-projects": [],
            "start-program": [],
        }
        found_options = {}

        parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)

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
                logger_app.error("You need to specify a project binary with the --run option")
                exit(1)  # Do not continue

        def validate_set_project_option_value(inp_str: str):
            try:
                project_name, option_name, option_value = inp_str.split(",", 2)
                return project_name, option_name, option_value
            except ValueError:
                logger_app.error(f" r[*] Invalid value in --set-project-option-value option. See https://kde-builder.kde.org/en/cmdline/supported-cmdline-params.html#cmdline-set-project-option-value.")
                exit(1)  # Do not continue

        parser.add_argument("--set-project-option-value", type=validate_set_project_option_value, action="append")

        parser.add_argument("--target", action="append")

        parser.add_argument("--ignore-projects", "-!", nargs="+")
        parser.add_argument("-d", action="store_true")
        parser.add_argument("-D", action="store_true")

        for opt in OptionsSpec.global_options_without_parameter:
            parser.add_argument(*opt.dashed(), action="store_true")

        for opt in OptionsSpec.global_options_with_parameter:
            parser.add_argument(*opt.dashed(), nargs=1)

        for opt in OptionsSpec.global_options_with_negatable_form:
            parser.add_argument(*opt.dashed(), action=argparse.BooleanOptionalAction)

        for opt in OptionsSpec.phase_changing_options:
            parser.add_argument(*opt.dashed(), action="store_true")

        for opt in OptionsSpec.non_context_options_without_parameter:
            parser.add_argument(*opt.dashed(), action="store_true")

        for opt in OptionsSpec.non_context_options_without_parameter_manually_handled:
            parser.add_argument(*opt.dashed(), action="store_true")

        for opt in OptionsSpec.non_context_options_with_parameter:
            parser.add_argument(*opt.dashed(), nargs=1)

        for opt in OptionsSpec.non_context_options_with_parameter_manually_handled:
            parser.add_argument(*opt.dashed(), nargs=1)

        # Actually read the options.
        args, unknown_args = parser.parse_known_args(options)  # unknown_args - Required to read non-option args

        # <editor-fold desc="arg functions">
        if args.show_info:
            self._show_info_and_exit()
        if args.version:
            self._show_version_and_exit()
        if args.help:
            self._show_help_and_exit()
        if args.self_update:
            found_options["self-update"] = True
            found_options["no-metadata"] = True  # Implied --no-metadata
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
            found_options["reconfigure"] = True
        if args.query is not None:
            arg = args.query[0]

            valid_mode = re.compile(r"^[a-zA-Z0-9_#][a-zA-Z0-9_-]*$")
            if not valid_mode.match(arg):
                raise ValueError(f"Invalid query mode {arg}")

            opts["run_mode"] = "query"
            found_options["query"] = arg
            found_options["pretend"] = True  # Implied pretend mode
            found_options["no-metadata"] = True  # Implied --no-metadata
        if args.resume or args.resume_refresh_build_first:
            found_options["resume"] = True
            phases.filter_out_phase("update")  # Implied --no-src
            found_options["no-metadata"] = True  # Implied --no-metadata
            # Imply --no-include-dependencies, because when resuming, user wants to continue from exact same modules list
            # as saved in global persistent option "resume-list". Otherwise, some dependencies that have already passed the build successfully,
            # (i.e. those that were before the first item of resume list) may appear in modules list again (if some module from the
            # resume list requires such modules).
            found_options["include-dependencies"] = False

        if args.set_project_option_value:
            for module, option, value in args.set_project_option_value:
                if module and option:
                    if module not in opts["per_project"]:
                        opts["per_project"][module] = {}
                    opts["per_project"][module][option] = value

        if args.target:
            found_options["targets"] = args.target

        if args.ignore_projects:
            opts["ignore-projects"] = args.ignore_projects
        # </editor-fold desc="arg functions">

        # handling flag options
        for optspec in OptionsSpec.global_options_with_negatable_form:
            ns_name = optspec.name.replace("-", "_")
            val = getattr(args, ns_name)
            if val is not None:
                found_options[optspec.name] = val

        # handling options with one argument
        for optspec in OptionsSpec.global_options_with_parameter:
            ns_name = optspec.name.replace("-", "_")
            val = getattr(args, ns_name)
            if val is not None:
                found_options[optspec.name] = val[0]

        for optspec in OptionsSpec.non_context_options_with_parameter:
            ns_name = optspec.name.replace("-", "_")
            val = getattr(args, ns_name)
            if val is not None:
                found_options[optspec.name] = val[0]

        # handling options without arguments
        for optspec in OptionsSpec.global_options_without_parameter:
            ns_name = optspec.name.replace("-", "_")
            val = getattr(args, ns_name)
            if val:
                found_options[optspec.name] = True

        for optspec in OptionsSpec.non_context_options_without_parameter:
            ns_name = optspec.name.replace("-", "_")
            val = getattr(args, ns_name)
            if val:
                found_options[optspec.name] = True

        # Module selectors (i.e. an actual argument)
        for unknown_arg in unknown_args:
            opts["selectors"].append(unknown_arg)

        # <editor-fold desc="all other args handlers">
        if args.all_config_projects:
            opts["special-selectors"].append("all-config-projects")

        if args.all_kde_projects:
            opts["special-selectors"].append("all-kde-projects")

        if args.rc_file is not None:
            found_options["rc-file"] = args.rc_file[0]

        if args.resume_refresh_build_first:
            found_options["refresh-build-first"] = True

        if args.install_login_session_only:
            opts["run_mode"] = "install-login-session-only"
            phases.clear()

        # </editor-fold desc="all other args handlers">

        opts["global"] = found_options
        opts["phases"] = phases.phaselist
        return opts

    @staticmethod
    def _show_version_and_exit() -> NoReturn:
        version = "kde-builder " + Version.script_version()
        print(version)
        exit()

    @staticmethod
    def _show_help_and_exit() -> NoReturn:
        print(dedent("""
            KDE Builder tool automates the download, build, and install process for KDE software using the latest available source code.

            Documentation: https://kde-builder.kde.org
                Supported command-line parameters:              https://kde-builder.kde.org/en/cmdline/supported-cmdline-params.html
                Table of available configuration options:       https://kde-builder.kde.org/en/configuration/conf-options-table.html

            """))
        exit()

    @staticmethod
    def _show_info_and_exit() -> NoReturn:
        os_vendor = OSSupport().ID
        version = "kde-builder " + Version.script_version()
        print(dedent(f"""
            {version}
            OS: {os_vendor}
            """))
        exit()
