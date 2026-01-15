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

    def resolve_branch_group(self, repopath_entry_str: str, layer_name: str) -> str | None:
        """
        Return the branch for the given group name and entry_name.

        Args:
            repopath_entry_str: full repo path string that is searched in groups keys (for example, "sdk/kde-builder")
            layer_name: value of branch-group layer name (for example, "latest-kf6")
        """
        if repopath_entry_str in self.groups:
            ret = self.groups[repopath_entry_str].get(layer_name, None)
            if ret is not None:
                return ret

        for wildcarded_prefix in self.ordered_wildcarded_prefixes:
            prefix = wildcarded_prefix.removesuffix("*")
            if repopath_entry_str.startswith(prefix):
                if layer_name in self.groups[wildcarded_prefix]:
                    ret = self.groups[wildcarded_prefix][layer_name]
                    return ret

        return None
