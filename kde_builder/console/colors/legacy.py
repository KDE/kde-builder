# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Legacy colorization method."""

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal

if TYPE_CHECKING:
    from collections.abc import Mapping


class Colorizer:
    """
    Format strings by replacing tags with escape sequences.

    Translates custom styling tags like "r[" (red), "g[" (green), "y[" (yellow),
    "b[" (bold) into ANSI terminal escape sequences. It ensures that colors are
    automatically reset back to normal at the end of each log message.
    """

    def __init__(self) -> None:
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

    def colorize(self, text: str) -> str:
        """Colorize a string."""
        # Colors
        text = text.replace("r[", self.RED)
        text = text.replace("g[", self.GREEN)
        text = text.replace("y[", self.YELLOW)
        # Other
        text = text.replace("]", self.NORMAL)
        text = text.replace("b[", self.BOLD)

        return text + self.NORMAL


decolorizer = Colorizer()


def strip_color_tags(text: str) -> str:
    """Remove styling tags from a string."""
    return decolorizer.colorize(text)


class ColorFormatter(logging.Formatter):
    """
    Custom logging formatter that parses color and text-formatting tags.

    Translates custom styling tags like "r[" (red), "g[" (green), "y[" (yellow),
    "b[" (bold) into ANSI terminal escape sequences. It ensures that colors are
    automatically reset back to normal at the end of each log message.
    """

    def __init__(
        self,
        colorizer: Colorizer,
        *,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
        validate: bool = True,
        defaults: Mapping[str, Any] | None = None,
    ) -> None:

        super().__init__(
            fmt=fmt,
            style=style,
            datefmt=datefmt,
            validate=validate,
            defaults=defaults,
        )

        self._legacy_colorizer = colorizer

    # ruff: ignore[invalid-function-name]
    # This is an override, so we have no choice regarding the naming.
    def formatMessage(self, record: logging.LogRecord) -> str:
        """
        Return the string that should be substituted for `%(message)s`.

        It sets the `record.message` attribute, which overrides the value that
        `Formatter.format()` computes with `LogRecord.getMessage()`, which is
        assumed to use percent-style formatting (i.e. `.msg % .args`).

        Since the every `Formatter` overwrites `record.message` when formatting
        a record, this has no effect on other formatters rendering this record.
        """
        if record.args:
            message = self._legacy_colorizer.colorize(str(record.msg)) % record.args
        else:
            message = self._legacy_colorizer.colorize(str(record.msg))

        # The record.message attribute is the only attribute that can be safely
        # overwritten without affecting other formatters.
        record.message = message

        return super().formatMessage(record)
