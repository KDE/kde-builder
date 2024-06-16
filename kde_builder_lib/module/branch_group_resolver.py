# SPDX-FileCopyrightText: 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations


class Module_BranchGroupResolver:
    """
    This provides an object that can be used to look up the appropriate git branch
    to use for a given KDE project module and given desired logical branch group, using
    supplied JSON data (from repo-metadata's /dependencies directory).

    See also https://community.kde.org/Infrastructure/Project_Metadata
    """

    def __init__(self, jsonData: dict):

        # Copy just the objects we want over.
        self.layers = jsonData.get("layers", [])
        self.groups = jsonData.get("groups", [])

        # For layers and groups, remove anything beginning with a '_' as that is
        # defined in the spec to be a comment of some sort.
        self.layers = [layer for layer in self.layers if not layer.startswith("_")]

        # Deleting keys that starts with underscore.
        self.groups = {key: self.groups[key] for key in self.groups if not key.startswith("_")}

        # Extract wildcarded groups separately as they are handled separately
        # later. Note that the specific catch-all group '*' is itself handled
        # as a special case in find_module_branch.

        self.wildcardedGroups = {key: self.groups[key] for key in self.groups if key[-1] == "*"}

    def _find_logical_group(self, module: str, logicalGroup: str) -> str | None:
        """
        Returns the branch for the given logical group and module specifier. This
        function should not be called if the module specifier does not actually
        exist.
        """

        # Using defined-or and still returning None is on purpose, silences
        # warning about use of undefined value.
        return self.groups[module].get(logicalGroup, None)

    def find_module_branch(self, module: str, logicalGroup: str) -> str | None:
        if module in self.groups:
            return self._find_logical_group(module, logicalGroup)

        # Map module search spec to prefix string that is required for a match
        catchAllGroupStats = {key: key[:-1] for key in self.wildcardedGroups.keys()}

        # Sort longest required-prefix to the top... first match that is valid will
        # then also be the right match.
        orderedCandidates = sorted(catchAllGroupStats.keys(), key=lambda x: catchAllGroupStats[x], reverse=True)

        match = next((candidate for candidate in orderedCandidates if module[:len(catchAllGroupStats[candidate])] == catchAllGroupStats[candidate]), None)

        if match:
            return self._find_logical_group(match, logicalGroup)

        if "*" in self.groups:
            return self._find_logical_group("*", logicalGroup)

        return
