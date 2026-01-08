# SPDX-FileCopyrightText: 2013, 2014, 2017, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os.path
from pathlib import Path
import re

import yaml

from ..kb_exception import KBRuntimeError
from ..debug import Debug


class KDEProjectsReader:
    """
    Enumerates and provides basic metadata of KDE projects, based on the metadata.yaml included in sysadmin/repo-metadata.
    """

    def __init__(self, repo_metadata_fullpath: str):
        """
        Construct a new KDEProjectsReader. This doesn't contradict any part of the class documentation which claims this class is a singleton.

        Args:
            repo_metadata_fullpath: string that is a path to repo-metadata.
        """
        self.repositories: dict[str, dict[str, str | bool]] = {}
        """Maps short names to repo info blocks."""

        self._read_project_data(repo_metadata_fullpath)

    def _read_project_data(self, repo_metadata_fullpath: str) -> None:
        # The "main" method for this class. Reads in *all* KDE projects and notes
        # their details for later queries.
        # Be careful, can throw exceptions.

        if Debug().is_testing():
            kb_repo_dir = os.path.normpath(os.path.dirname(os.path.realpath(__file__)) + "/../..")
            srcdir = kb_repo_dir + "/tests/fixtures/repo-metadata"
        else:
            srcdir = repo_metadata_fullpath

        if not os.path.isdir(srcdir):
            raise KBRuntimeError(f"No such source directory {srcdir}!")

        repo_meta_files: list[str] = list(map(str, Path(f"{srcdir}/projects").resolve().rglob("metadata.yaml")))  # resolve /projects symlink first, then recurse through dir tree

        for metadata_path in repo_meta_files:
            self._read_yaml(metadata_path)

        if not len(repo_meta_files) > 0:
            raise KBRuntimeError(f"Failed to find KDE project entries from {srcdir}!")

    def _read_yaml(self, filename: str) -> None:
        with open(filename, "r") as file:
            proj_data = yaml.safe_load(file)

        if proj_data["kind"] != "software":
            return

        repo_path = proj_data["repopath"]
        repo_name = proj_data["identifier"]

        cur_repository = {
            "invent_name": repo_path,
            "repo": f"kde:{repo_path}.git",
            "name": repo_name,
            "active": bool(proj_data["repoactive"]),
        }

        self.repositories[repo_name] = cur_repository

    def get_modules_for_project(self, proj: str) -> list[dict[str, str | bool]]:
        """
        Get modules for project.

        Note on ``proj``: A "/"-separated path is fine, in which case we look
        for the right-most part of the full path which matches all of searchProject.
        e.g. kde/kdebase/kde-runtime would be matched by a proj of either
        "kdebase/kde-runtime" or simply "kde-runtime".
        """
        repositories = self.repositories
        results: list[str] = []

        def find_results():
            match_list: list[str] = []
            sorted_keys = sorted(repositories.keys())
            for key in sorted_keys:
                if KDEProjectsReader.project_path_matches_wildcard_search(repositories[key]["invent_name"], proj):
                    match_list.append(key)

            results.extend(match_list)

        # Wildcard matches happen as specified if asked for.
        # Non-wildcard matches have an implicit "$proj/*" search as well for
        # compatibility with previous use-projects
        # Project specifiers ending in .git are forced to be non-wildcarded.
        if not re.search(r"\*", proj) and not re.search(r"\.git$", proj):
            # We have to do a search to account for over-specified module names
            # like phonon/phonon
            find_results()

            # Now setup for a wildcard search to find things like kde/kdelibs/baloo
            # if just "kdelibs" is asked for.
            proj += "/*"

        proj = re.sub(r"\.git$", "", proj)

        # If still no wildcard and no "/" then we can use direct lookup by module
        # name.
        if not re.search(r"\*", proj) and not re.search(r"/", proj) and proj in repositories:
            results.append(proj)
        else:
            find_results()

        # As we run find_results twice (for example, when proj is "workspace"), remove duplicates
        results = list(set(results))
        ret = [repositories[result] for result in results]
        return ret

    @staticmethod
    def project_path_matches_wildcard_search(project_path: str, search_item: str) -> bool:
        """
        Return true if the given kde-project full path (e.g. kde/kdelibs/nepomuk-core) matches the given search item.

        The search item itself is based on path-components. Each path component in
        the search item must be present in the equivalent path component in the
        module's project path for a match. A "*" in a path component position for the
        search item matches any project path component.

        Finally, the search is pinned to search for a common suffix. E.g. a search
        item of "kdelibs" would match a project path of "kde/kdelibs" but not
        "kde/kdelibs/nepomuk-core". However, "kdelibs/*" would match
        "kde/kdelibs/nepomuk-core".

        Args:
            project_path: The full project path from the kde-projects database.
            search_item: The search item.

        Returns:
             True if they match, False otherwise.
        """
        search_parts: list[str] = search_item.split("/")
        name_stack: list[str] = project_path.split("/")

        if len(name_stack) >= len(search_parts):
            size_difference = len(name_stack) - len(search_parts)

            # We might have to loop if we somehow find the wrong start point for our search.
            # E.g. looking for a/b/* against a/a/b/c, we'd need to start with the second a.
            i = 0
            while i <= size_difference:
                # Find our common prefix, then ensure the remainder matches item-for-item.
                while i <= size_difference:
                    if name_stack[i] == search_parts[0]:
                        break
                    i += 1

                if i > size_difference:  # Not enough room to find it now
                    return False

                # At this point we have synched up name_stack to search_parts, ensure they
                # match item-for-item.
                found = 1
                j = 0
                while found and j < len(search_parts):
                    if search_parts[j] == "*":  # This always works
                        return True
                    if search_parts[j] != name_stack[i + j]:
                        found = 0
                    j += 1

                if found:  # We matched every item to the substring we found.
                    return True
                i += 1  # Try again
        return False
