import os
import sys
import re


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

    def setPretending(self, val: bool) -> None:
        self.isPretending = val

    @staticmethod
    def isTesting() -> bool:
        # return "HARNESS_ACTIVE" in os.environ
        return "unittest" in sys.modules

    def setColorfulOutput(self, useColor: bool) -> None:
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

    def isLogLevel(self, level) -> bool:
        level = level if level else Debug.DEBUG
        return self.debugLevel <= level

    def debugging(self, level=None) -> bool:
        """
        Subroutine which returns true if debug mode is on.
        """
        if not level:
            level = Debug.DEBUG
        return self.isLogLevel(level)

    def setDebugLevel(self, level) -> None:
        self.debugLevel = level

    def setLogFile(self, fileName) -> None:
        if self.pretending():
            return
        try:
            self.screenLog = open(fileName, "w")
        except IOError:
            self.error(f"Unable to open log file {fileName}!")

    def setIPC(self, ipc) -> None:
        """
        Sets an IPC object to use to proxy logged messages over, to avoid having
        multiple procs fighting over the same TTY. Needless to say, you should only
        bother with this if the IPC method is actually concurrent.
        """
        self.ipc = ipc
        from .IPC.IPC import IPC
        if not isinstance(ipc, IPC):
            raise ValueError(f"{ipc} isn't an IPC obj!")

    # The next few subroutines are used to print output at different importance
    # levels to allow for e.g. quiet switches, or verbose switches.  The levels are,
    # from least to most important:
    # debug, whisper, info (default), note (quiet), warning (very-quiet), and error.
    #
    # You can also use the pretend output subroutine, which is emitted if, and only
    # if pretend mode is enabled.
    #
    # ksb::Debug::colorize is automatically run on the input for all of those
    # functions.  Also, the terminal color is automatically reset to normal as
    # well so you don't need to manually add the ] to reset.

    def print_clr(self, *args: str) -> None:
        """
        Subroutine used to actually display the data, calls ksb::Debug::colorize on each entry first.
        """
        # If we have an IPC object that means there's multiple procs trying to
        # share the same TTY. Just forward messages to the one proc that should be
        # managing the TTY.
        if self.ipc:
            msg = "".join(args)
            self.ipc.sendLogMessage(msg)
            return

        # Leading + prevents Perl from assuming the plain word "colorize" is actually
        # a filehandle or future reserved word.
        for arg in args:
            print(self.colorize(arg), end="")
        print(self.colorize("]\n"), end="")

        if self.screenLog is not None:
            savedColors = [self.RED, self.GREEN, self.YELLOW, self.NORMAL, self.BOLD]
            # Remove color but still extract codes
            self.RED, self.GREEN, self.YELLOW, self.NORMAL, self.BOLD = [""] * 5

            for arg in args:
                print(self.colorize(arg), end="", file=self.screenLog)
            print("", file=self.screenLog)

            self.RED, self.GREEN, self.YELLOW, self.NORMAL, self.BOLD = savedColors

    def debug(self, *args) -> None:
        if self.isLogLevel(self.DEBUG):
            self.print_clr(*args)

    def whisper(self, *args):
        if self.isLogLevel(self.WHISPER):
            self.print_clr(*args)

    def info(self, *args) -> None:
        if self.isLogLevel(self.INFO):
            self.print_clr(*args)

    def note(self, *args) -> None:
        if self.isLogLevel(self.NOTE):
            self.print_clr(*args)

    def warning(self, *args) -> None:
        if self.isLogLevel(self.WARNING):
            self.print_clr(*args)

    def error(self, *args) -> None:
        for arg in args:
            print(self.colorize(arg), file=sys.stderr, end="")
        print(self.colorize("]"), file=sys.stderr)

    def pretend(self, *args) -> None:
        if self.pretending() and self.debugLevel <= self.WHISPER:
            lines = [*args]
            lines = [re.sub(r"(\w)", r"d[\1", line, 1) for line in lines]  # Add dim prefix. Clear suffix is actually implicit
            self.print_clr(*lines)
