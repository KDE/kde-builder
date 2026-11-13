#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2010, 2011, 2012, 2013, 2017, 2018, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import logging
import logging.config
import os
import sys

from kde_builder import KB_PACKAGE_DIR
from kde_builder.console import use_as_output
from kde_builder.kb_exception import ProgramError
from kde_builder.kb_exception import UnknownKdeProjectException
from kde_builder.kb_logging import main_handler
from kde_builder.util.textwrap_mod import dedent

ISSUE_TRACKER_URL = "https://invent.kde.org/sdk/kde-builder/-/issues"


def main():

    unhandled_argv = sys.argv[1:]

    # Ensure that the output stream for the console package is properly initialized.
    use_as_output(sys.stdout)

    bootstrap_parser = argparse.ArgumentParser(add_help=False)
    from kde_builder.options_spec import add_bootstrap_arguments

    add_bootstrap_arguments(bootstrap_parser)

    args, unhandled_argv = bootstrap_parser.parse_known_args(unhandled_argv)

    # ---

    import yaml  # noqa: E402

    # <editor-fold desc="Applying loggers configuration">
    with open(f"{KB_PACKAGE_DIR}/resources/kde-builder-logging.yaml", "r") as f:
        config = yaml.safe_load(f.read())

    override_config = {}
    if os.path.exists(os.getcwd() + "/kde-builder-logging.yaml"):
        with open(os.getcwd() + "/kde-builder-logging.yaml", "r") as f:
            override_config = yaml.safe_load(f.read())
    elif os.path.exists(os.path.expanduser("~/.config/kde-builder-logging.yaml")):
        with open(os.path.expanduser("~/.config/kde-builder-logging.yaml"), "r") as f:
            override_config = yaml.safe_load(f.read())

    # Overriding logger levels by cmdline
    if args.log_level:
        if override_config.get("loggers", None) is None:
            override_config["loggers"] = {}
        for logger_name, level_name in args.log_level:
            if override_config["loggers"].get(logger_name, None) is None:
                override_config["loggers"][logger_name] = {}
            override_config["loggers"][logger_name]["level"] = level_name

    # Merges dict "b" into dict "a", overwriting existing entries. Mutates dict "a". Also, returns "a".
    def merge_dicts(a: dict, b: dict, path=None):
        if path is None:
            path = []

        for key in b:
            if key in a:
                if isinstance(a[key], dict) and isinstance(b[key], dict):
                    merge_dicts(a[key], b[key], path + [str(key)])
                elif a[key] != b[key]:
                    a[key] = b[key]
            else:
                a[key] = b[key]
        return a

    config = merge_dicts(config, override_config)
    logging.config.dictConfig(config)  # instantiates configured loggers, handlers, and formatters

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # Default level
    root_logger.addHandler(main_handler)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        for logger_name in config.get("loggers", {}):
            if logger_name == "asyncio":
                continue
            logging.getLogger(logger_name).setLevel(logging.NOTSET)
    # </editor-fold>

    # ---

    setup_steps = []
    if args.initial_setup:
        setup_steps = ["install-distro-packages", "generate-config"]
    else:
        if args.install_distro_packages:
            setup_steps.append("install-distro-packages")
        if args.generate_config:
            setup_steps.append("generate-config")

    if setup_steps:
        from kde_builder.first_run import FirstRun

        prompt_answer = args.prompt_answer[0] if args.prompt_answer is not None else None
        fr = FirstRun(prompt_answer)
        exit(fr.setup_user_system(setup_steps))

    from kde_builder.application import Application  # noqa: E402
    from kde_builder.kb_exception import KBException  # noqa: E402

    # Script starts.

    app = None
    try:
        app = Application(unhandled_argv)
        app.generate_module_list()
        result = app.run_all_module_phases()
        app.finish(result)
    except UnknownKdeProjectException as err:
        logger_app = logging.getLogger("application")
        unrecognized_name = err.unknown_project_name
        ctx = app.context
        repo_data = ctx.projects_db.repositories.get(unrecognized_name, None)
        msg = ""
        if repo_data and not repo_data["active"]:
            msg = f" r[*] y[{unrecognized_name}] is archived KDE project."
        else:
            msg = dedent(
                f"""
                 r[*] KDE Builder cannot build y["{unrecognized_name}"].

                   If you didn't make a typo, and you're trying to build a KDE project,
                   note that KDE Builder can only build y["software"] projects. Other
                   kinds of projects, such as "website", "infrastructure", or "packaging"
                   are not supported.
                """,
                preserve_len=1,
            )

        logger_app.error(msg)
        exit(99)
    except ProgramError as err:
        print(
            dedent(f"""

            kde-builder encountered an exceptional error condition:
            ========
            {err}
            ========
            Can't continue, so stopping now.


            """),
        )

        print(f"Please submit a bug against kde-builder on {ISSUE_TRACKER_URL}")

        sys.excepthook(err.__class__, err, err.__traceback__)
        if app:
            app.finish(99)  # noreturn
        exit(99)  # if app couldn't be created

    except KBException as err:
        logger_app = logging.getLogger("application")
        logger_app.error(str(err))

        notes: list[str] = getattr(err, "__notes__", [])
        for note in notes:
            logger_app.error("\n%s", note)

        if app:
            app.finish(99)  # noreturn
        exit(99)  # if app couldn't be created

    except Exception as err:
        # We encountered some other kind of error that didn't raise a `KBException`
        print(
            dedent(f"""
            Encountered an error in the execution of the script.
            --> {err}
            Please submit a bug against kde-builder on {ISSUE_TRACKER_URL}

            """),
        )

        sys.excepthook(err.__class__, err, err.__traceback__)
        if app:
            app.finish(99)  # noreturn
        exit(99)  # if app couldn't be created


if __name__ == "__main__":
    main()
