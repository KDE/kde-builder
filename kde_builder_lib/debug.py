# SPDX-FileCopyrightText: 2012, 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import os
import re
import sys


class Debug:
    """
    Debugging routines and constants for use with kde-builder
    """

    # Debugging level constants.
    DEBUG = 0
    WHISPER = 1
    INFO = 2
    NOTE = 3
    WARNING = 4
    ERROR = 5

    __instance = None
    __initialized = False

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:  # This ensures that we have only one instance of Debug class (Singleton)
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __str__(self):
        debugLevelNames = {
            Debug.DEBUG: "DEBUG",
            Debug.WHISPER: "WHISPER",
            Debug.INFO: "INFO",
            Debug.NOTE: "NOTE",
            Debug.WARNING: "WARNING",
            Debug.ERROR: "ERROR"
        }
        return f"debugLevel: {debugLevelNames[self.debugLevel]}, isPretending: {self.isPretending}"

    def __init__(self):
        if not self.__initialized:
            self.__initialized = True
            self.screenLog = None  # Filehandle pointing to the "build log".
            self.isPretending = False
            self.debugLevel = Debug.INFO

            self.ipc = None  # Set only if we should forward log messages over IPC.

            # Colors
            self.RED, self.GREEN, self.YELLOW, self.NORMAL, self.BOLD, self.DIM = [""] * 6

    # Subroutine definitions

    def colorize(self, text: str) -> str:
        text = text.replace("g[", self.GREEN)
        text = text.replace("]", self.NORMAL)
        text = text.replace("y[", self.YELLOW)
        text = text.replace("r[", self.RED)
        text = text.replace("b[", self.BOLD)
        text = text.replace("d[", self.DIM)
        return text

    def pretending(self) -> bool:
        """
        Subroutine which returns true if pretend mode is on.
        """
        return self.isPretending

    def set_pretending(self, val: bool) -> None:
        self.isPretending = val

    @staticmethod
    def is_testing() -> bool:
        # return "HARNESS_ACTIVE" in os.environ
        return "unittest" in sys.modules

    def set_colorful_output(self, useColor: bool) -> None:
        # No colors unless output to a tty.
        if not sys.stdout.isatty():
            return

        if useColor:
            self.RED = "\033[31m"
            self.GREEN = "\033[32m"
            self.YELLOW = "\033[33m"
            self.NORMAL = "\033[0m"
            self.BOLD = "\033[1m"
            self.DIM = "\033[34m"  # Really blue since dim doesn't work on konsole

            # But konsole does support xterm-256color...
            if "TERM" in os.environ and os.getenv("TERM").endswith("-256color"):
                self.DIM = "\033[38;5;8m"
        else:
            self.RED, self.GREEN, self.YELLOW, self.NORMAL, self.BOLD, self.DIM = [""] * 6

    def set_log_file(self, fileName) -> None:
        if self.pretending():
            return
        try:
            self.screenLog = open(fileName, "w")
        except IOError:
            logger_root = logging.getLogger()
            logger_root.error(f"Unable to open log file {fileName}!")

    def set_ipc(self, ipc) -> None:
        """
        Sets an IPC object to use to proxy logged messages over, to avoid having
        multiple procs fighting over the same TTY. Needless to say, you should only
        bother with this if the IPC method is actually concurrent.
        """
        self.ipc = ipc
        from .ipc.ipc import IPC
        if not isinstance(ipc, IPC):
            raise ValueError(f"{ipc} isn't an IPC obj!")


class kbLogger(logging.Logger):
    _loggers = {}
    levelNamesMapping = logging._nameToLevel

    # noinspection PyPep8Naming
    @classmethod
    def getLogger(cls, name, level=logging.NOTSET):
        if name not in cls._loggers:
            logger = cls(name, level)
            cls._loggers[name] = logger
        return cls._loggers[name]

    @staticmethod
    def print_clr(logger_name: str, message_level: str, msg: str) -> None:
        """
        Subroutine used to actually display the data, calls :meth:`Debug.colorize` on each entry first.
        """

        d = Debug()
        # If we have an IPC object that means there's multiple procs trying to
        # share the same TTY. Just forward messages to the one proc that should be
        # managing the TTY.
        if d.ipc:
            d.ipc.send_log_message(logger_name, message_level, msg)
            return

        kblogger = kbLogger.getLogger(logger_name)
        real_level_method = getattr(super(kbLogger, kblogger), message_level)  # the method of logging.Logger for the specific level, for example, the logging.Logger.warning() method
        real_level_method(d.colorize(msg + "]"))

        if d.screenLog is not None:  # todo: This should be just another handler for the logger
            int_message_level = kbLogger.levelNamesMapping[message_level.upper()]
            if kblogger.isEnabledFor(int_message_level):
                savedColors = [d.RED, d.GREEN, d.YELLOW, d.NORMAL, d.BOLD]
                # Remove color but still extract codes
                d.RED, d.GREEN, d.YELLOW, d.NORMAL, d.BOLD = [""] * 5
                print(d.colorize(msg), file=d.screenLog)
                d.RED, d.GREEN, d.YELLOW, d.NORMAL, d.BOLD = savedColors

    # The next few methods are used to print output at different importance
    # levels to allow for e.g. quiet switches, or verbose switches.  The levels are,
    # from least to most important:
    # debug, info, warning, and error.
    #
    # You can also use the pretend output function, which is emitted if, and only
    # if pretend mode is enabled.
    #
    # Debug.colorize() is automatically run on the input for all of those
    # functions. Also, the terminal color is automatically reset to normal as
    # well, so you don't need to manually add the "]" to reset.

    def debug(self, msg: str, *args, **kwargs) -> None:
        kbLogger.print_clr(self.name, "debug", msg)

    def info(self, msg: str, *args, **kwargs) -> None:
        kbLogger.print_clr(self.name, "info", msg)

    def warning(self, msg: str, *args, **kwargs) -> None:
        kbLogger.print_clr(self.name, "warning", msg)

    def error(self, msg: str, *args, **kwargs) -> None:
        kbLogger.print_clr(self.name, "error", msg)

    def pretend(self, msg: str) -> None:
        if Debug().pretending():
            msg = re.sub(r"(\w)", r"d[\1", msg, 1)  # Add dim prefix. Clear suffix is actually implicit
            kbLogger.print_clr(self.name, "debug", msg)
