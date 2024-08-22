# SPDX-FileCopyrightText: 2013, 2016, 2018 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import textwrap
from typing import NoReturn


class BuildException(Exception):  # noqa: N818
    """
    A class to wrap "exception" messages for the script, allowing them to be dispatch based on type and automatically stringified.
    """

    def __init__(self, exception_type: str, msg: str):
        self.exception_type = exception_type
        self.message = msg

    def __str__(self) -> str:
        return self.exception_type + " Error: " + self.message

    @staticmethod
    def make_exception(exception_type: str, msg: str, levels=None):
        """
        Return an exception object to pass to "raise" function.

        The returned object will be an instance of :class:`BuildException`.

        Args:
            exception_type: Exception type, "Exception" if not defined.
            msg: Message to show to user
            levels: Number of levels to remove from backtrace.
        """
        exception_type = exception_type if exception_type else "Exception"
        message = msg
        levels = levels if levels else 0  # Allow for more levels to be removed from bt

        # # Remove this subroutine from the backtrace
        # local $Carp::CarpLevel = 1 + $levels;

        # if exception_type == "Internal":
        #     message = Carp::cluck(message)  # prints the backtrace
        return BuildException(exception_type, message)

    @staticmethod
    def croak_runtime(msg: str) -> NoReturn:
        """
        Use for "runtime errors" (i.e. unrecoverable runtime problems that don't indicate a bug in the program itself).
        """
        raise BuildException.make_exception("Runtime", msg, 1)

    @staticmethod
    def croak_internal(msg: str) -> NoReturn:
        """
        Use for "logic errors" (i.e. impossibilities in program state, things that shouldn't be possible no matter what input is fed at runtime).
        """
        raise BuildException.make_exception("Internal", msg, 1)


class BuildExceptionConfig(BuildException):
    """
    A small subclass to hold the option name that caused a config exception to be thrown.

    Typically, this will be caught by config-reading code in :class:`Application`,
    which will add filename and line number information to the message.
    """

    def __init__(self, bad_option_name, msg):
        BuildException.__init__(self, "Config", msg)
        self.config_invalid_option_name = bad_option_name

    def problematic_option_name(self):
        return self.config_invalid_option_name

    @staticmethod
    def option_usage_explanation(option_name) -> str | None:
        """
        Return a lengthy explanation of how to use a given option for use in error messages, or None if no explanation is unavailable.
        """
        result = None

        if isinstance(option_name, BuildExceptionConfig):
            # Should only happen if called as method: i.e. option_name == self
            option_name = option_name.problematic_option_name()

        if option_name == "git-repository-base":
            result = textwrap.dedent("""\
            The y[git-repository-base] option requires a repository name and URL.
            
            e.g. git-repository base y[b[kde-sdk] g[b[https://invent.kde.org/sdk/]
            
            Use this in a "module-set" group:
            
            e.g.
            module-set kdesdk-set
                repository y[b[kde-sdk]
                use-modules kde-builder kde-dev-scripts clazy
            end module-set
            """)
        return result


class UnknownKdeProjectException(BuildException):
    """
    Raised when a specific project name is not found in repo-metadata kde projects and is not a defined module in config.
    """

    def __init__(self, message: str, unknown_project_name: str):
        self.message = message
        self.unknown_project_name = unknown_project_name
