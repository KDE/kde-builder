# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from typing import Protocol
from typing import override
from typing import runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping


@runtime_checkable
class ColorizerProtocol(Protocol):
    """Colorize text, when enabled."""

    def colorize(self, text: str) -> str:
        """Colorize text, if enabled."""


class ColorFormatter(logging.Formatter):
    """
    Custom logging formatter that parses color and text-formatting tags.

    Translates custom styling tags like "r[" (red), "g[" (green), "y[" (yellow),
    "b[" (bold) into ANSI terminal escape sequences. It ensures that colors are
    automatically reset back to normal at the end of each log message.
    """

    def __init__(
        self,
        colorizer: ColorizerProtocol,
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

        self._colorizer = colorizer

    @override
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
            message = self._colorizer.colorize(str(record.msg)) % record.args
        else:
            message = self._colorizer.colorize(str(record.msg))

        # The record.message attribute is the only attribute that can be safely
        # overwritten without affecting other formatters.
        record.message = message

        return super().formatMessage(record)
