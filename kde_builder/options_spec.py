# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass
class Option:
    """
    Single option specification.
    """

    name: str
    default: Any
    aliases: list[str] = field(default_factory=list)

    def dashed(self) -> list[str]:
        parts = [self.name, *self.aliases]
        dashed_parts = []
        for part in parts:
            if len(part) == 1:
                dashed_parts.append("-" + part)
            else:
                dashed_parts.append("--" + part)
        return dashed_parts


class OptionsSpec:
    """
    Options specification.

    Determines option names, their description and default values.
    """

    # These options are exposed as cmdline options without parameters
    global_options_without_parameter = [
        Option(name="build-system-only", default=""),
        Option(name="reconfigure", default=""),
        Option(name="refresh-build-first", default=""),
        Option(name="metadata-only", default=""),
    ]

    @classmethod
    def all_global_options(cls) -> dict[str, Option]:
        ret = {}
        for option in cls.global_options_without_parameter:
            ret[option.name] = option
        return ret

    @classmethod
    def all_global_options_defaults(cls) -> dict[str, Any]:
        ret = {}
        for option in cls.global_options_without_parameter:
            ret[option.name] = option.default
        return ret
