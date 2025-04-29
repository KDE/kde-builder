# SPDX-FileCopyrightText: 2013, 2016, 2018 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from .util.textwrap_mod import textwrap
from typing import NoReturn


class KBException(Exception):  # noqa: N818
    """
    A class to wrap "exception" messages for the script, allowing them to be dispatch based on type and automatically stringified.
    """

    def __init__(self, exception_type: str, msg: str):
        self.exception_type = exception_type
        self.message = msg

    def __str__(self) -> str:
        return self.exception_type + " Error: " + self.message


class ConfigError(KBException):
    """
    Use for "config errors".
    """

    def __init__(self, msg: str):
        super().__init__("Config", msg)


class SetOptionError(KBException):
    """
    A small subclass to hold the option name that caused a config exception to be thrown.

    Typically, this will be caught by config-reading code in :class:`Application`,
    which will add filename and line number information to the message.
    """

    def __init__(self, bad_option_name: str, msg: str):
        super().__init__("Config", msg)
        self.config_invalid_option_name = bad_option_name

    def option_usage_explanation(self) -> str:
        """
        Return a lengthy explanation of how to use a given option for use in error messages.
        """
        result = ""
        option_name = self.config_invalid_option_name

        if option_name == "git-repository-base":
            result = textwrap.dedent("""\
            The y[git-repository-base] option requires a repository name and URL.

            e.g. git-repository-base y[b[kde-sdk] g[b[https://invent.kde.org/sdk/]

            Use this in a "group" group:

            e.g.
            group kdesdk-set:
              repository: y[b[kde-sdk]
              use-projects:
                - kde-builder
                - kde-dev-scripts
                - clazy
            """)
        return result


class UnknownKdeProjectException(KBException):
    """
    Raised when a specific project name is not found in repo-metadata kde projects and is not a defined module in config.
    """

    def __init__(self, message: str, unknown_project_name: str):
        self.message = message
        self.unknown_project_name = unknown_project_name


class ProgramError(KBException):
    """
    Use for "logic errors" (i.e. impossibilities in program state, things that shouldn't be possible no matter what input is fed at runtime).

    As this type of exception indicate bug in KDE Builder itself, we will print the traceback in the end of the script.
    """

    def __init__(self, msg: str):
        super().__init__("Internal", msg)


class KBRuntimeError(KBException):
    """
    Use for "runtime errors" (i.e. unrecoverable runtime problems that don't indicate a bug in the program itself).
    """

    def __init__(self, msg: str):
        super().__init__("Runtime", msg)


class SetupError(KBException):
    """
    Use for "setup errors" in FirstRun.
    """

    def __init__(self, msg: str):
        super().__init__("Setup", msg)
