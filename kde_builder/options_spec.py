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

    @classmethod
    def all_global_options(cls) -> dict[str, Option]:
        ret = {}
        return ret

    @classmethod
    def all_global_options_defaults(cls) -> dict[str, Any]:
        ret = {}
        return ret
