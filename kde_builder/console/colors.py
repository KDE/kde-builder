# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import os
import sys


class ColorFormatter(logging.Formatter):
    """
    Custom logging formatter that parses color and text-formatting tags.

    Translates custom styling tags like "r[" (red), "g[" (green), "y[" (yellow),
    "b[" (bold) into ANSI terminal escape sequences. It ensures that colors are
    automatically reset back to normal at the end of each log message.
    """

    def __init__(self) -> None:
        super().__init__()

        # Colors
        self.RED = ""
        self.GREEN = ""
        self.YELLOW = ""
        # Other
        self.NORMAL = ""
        self.BOLD = ""

    def set_colorful_output(self, use_color: bool) -> None:
        if use_color:
            # Colors
            self.RED = "\033[31m"  # "r["
            self.GREEN = "\033[32m"  # "g["
            self.YELLOW = "\033[33m"  # "y["
            # Other
            self.NORMAL = "\033[0m"  # "]"
            self.BOLD = "\033[1m"  # "b["
        else:
            # Colors
            self.RED = ""
            self.GREEN = ""
            self.YELLOW = ""
            # Other
            self.NORMAL = ""
            self.BOLD = ""

    def format_string(self, text: str) -> str:
        """May be used externally from this class, for colorizing any string."""
        # Colors
        text = text.replace("r[", self.RED)
        text = text.replace("g[", self.GREEN)
        text = text.replace("y[", self.YELLOW)
        # Other
        text = text.replace("]", self.NORMAL)
        text = text.replace("b[", self.BOLD)

        return text

    def format(self, record: logging.LogRecord) -> str:
        record.msg = self.format_string(str(record.msg))
        return super().format(record) + self.NORMAL


def colors_enabled() -> bool:
    """
    Determines whether colors should be enabled.

    Broadly replicates Python's approach to controlling color. It performs the
    following checks in order:

    If the `PYTHON_COLORS` environment variable is set, then we enable colors
    if its value is equal to `1`, and disable colors if it is set to `0`.

    If the `NO_COLOR` environment variable is present, colors are disabled.

    If the `FORCE_COLOR` environment variable is present, colors are enabled.

    If the `TERM` environment variable is set to `dumb`, colors are disabled.

    If `sys.stdout.isatty()` is True, colors are enabled, otherwise disabled.
    """
    # See https://docs.python.org/3/using/cmdline.html#envvar-PYTHON_COLORS
    python_colors = os.getenv("PYTHON_COLORS")
    if python_colors == "1":
        return True
    elif python_colors == "0":
        return False

    # See https://no-color.org/
    if os.getenv("NO_COLOR", "") != "":
        return False

    # See https://force-color.org/
    if os.getenv("FORCE_COLOR", "") != "":
        return True

    # See https://docs.python.org/3/using/cmdline.html#using-on-controlling-color
    if os.getenv("TERM", "") == "dumb":
        return False

    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


color_formatter = ColorFormatter()
color_formatter.set_colorful_output(colors_enabled())


def force_colors(value: bool) -> None:
    """
    Forcefully enables or disables colors by setting environment variables.

    The usual memory safety concerns regarding setting environment variables on
    certain platforms apply, in particular in multi-threaded contexts.
    """
    if value:
        os.environ.pop("NO_COLOR", None)
        os.environ["FORCE_COLOR"] = "1"
    else:
        os.environ["NO_COLOR"] = "1"

    # Don't let python do its own thing.
    os.environ.pop("PYTHON_COLORS", None)

    color_formatter.set_colorful_output(value)


def colorize(text: str) -> str:
    """Colorizes a string using the global `ColorFormatter`."""
    return color_formatter.format_string(text)
