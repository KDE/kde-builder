# SPDX-FileCopyrightText: 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations


class ModuleBranchGroupResolver:
    """
    Provides an object that can be used to look up the appropriate git branch to use for a given KDE project and given desired branch group.

    Uses supplied YAML data (from repo-metadata's /kde-dependencies directory).
    """

    def __init__(self, yaml_data: dict):
        self.layers: list[str] = yaml_data.get("layers", [])
        self.groups: dict[str, dict[str, str]] = yaml_data.get("groups", {})

        wildcarded_prefixes: list[str] = [key for key in self.groups if key.endswith("*")]

        # Sort longest required-prefix to the top. First match that is valid will then also be the right match.
        self.ordered_wildcarded_prefixes: list[str] = sorted(wildcarded_prefixes, reverse=True)

    def resolve_branch_group(self, entry_name: str, group_name: str) -> str | None:
        """
        Return the branch for the given group name and entry_name.

        Args:
            entry_name: full key name from branch groups (may contain "*")
            group_name: value of group
        """
        if entry_name in self.groups:
            return self.groups[entry_name].get(group_name, None)

        match: str | None = None
        for wildcarded_prefix in self.ordered_wildcarded_prefixes:
            prefix = wildcarded_prefix.removesuffix("*")
            if entry_name.startswith(prefix):
                match = wildcarded_prefix
                break

        if match:
            return self.groups[match].get(group_name, None)

        return None
