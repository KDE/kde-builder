# SPDX-FileCopyrightText: 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations


class ModuleBranchGroupResolver:
    """
    Provides an object that can be used to look up the appropriate git branch to use for a given KDE project module and given desired logical branch group.

    Uses supplied JSON data (from repo-metadata's /dependencies directory).

    See also https://community.kde.org/Infrastructure/Project_Metadata
    """

    def __init__(self, json_data: dict):

        # Copy just the objects we want over.
        self.layers: list[str] = json_data.get("layers", [])
        self.groups: dict[str, dict[str, str]] = json_data.get("groups", {})

        # For layers and groups, remove anything beginning with a "_" as that is
        # defined in the spec to be a comment of some sort.
        self.layers = [layer for layer in self.layers if not layer.startswith("_")]

        # Deleting keys that starts with underscore.
        self.groups = {key: self.groups[key] for key in self.groups if not key.startswith("_")}

        # Extract wildcarded groups separately as they are handled separately
        # later. Note that the specific catch-all group "*" is itself handled
        # as a special case in find_module_branch.

        self.wildcarded_groups: dict[str, dict[str, str]] = {key: self.groups[key] for key in self.groups if key[-1] == "*"}

    def find_module_branch(self, entry_name: str, logical_group: str) -> str | None:
        """
        Return the branch for the given logical group and entry_name.

        Args:
            entry_name: full key name from lms groups (may contain "*")
            logical_group: value of logical group
        """
        if entry_name in self.groups:
            return self.groups[entry_name].get(logical_group, None)

        # Map module search spec to prefix string that is required for a match
        catch_all_group_stats: dict[str, str] = {key: key[:-1] for key in self.wildcarded_groups.keys()}

        # Sort longest required-prefix to the top... first match that is valid will
        # then also be the right match.
        ordered_candidates: list[str] = sorted(catch_all_group_stats.keys(), key=lambda x: catch_all_group_stats[x], reverse=True)

        match: str | None = next((candidate for candidate in ordered_candidates if entry_name[:len(catch_all_group_stats[candidate])] == catch_all_group_stats[candidate]), None)

        if match:
            return self.groups[match].get(logical_group, None)

        if "*" in self.groups:
            return self.groups["*"].get(logical_group, None)

        return None
