# SPDX-FileCopyrightText: 2013, 2014, 2017, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os.path
from pathlib import Path
import re

import yaml

from .build_exception import KBRuntimeError
from .debug import Debug


class KDEProjectsReader:
    """
    Enumerates and provides basic metadata of KDE projects, based on the YAML metadata included in sysadmin/repo-management.
    """

    def __init__(self, project_metadata_module):
        """
        Construct a new KDEProjectsReader. This doesn't contradict any part of the class documentation which claims this class is a singleton.

        Args:
            project_metadata_module: :class:`Module` that is the repo-metadata module.
        """
        # pl2py: no need to check _verifyYAMLModuleLoaded()

        self.repositories = {}  # Maps short names to repo info blocks

        self._read_project_data(project_metadata_module)

    def _read_project_data(self, project_metadata_module) -> None:
        # The "main" method for this class. Reads in *all* KDE projects and notes
        # their details for later queries.
        # Be careful, can throw exceptions.

        if Debug().is_testing():
            self._load_mock_project_data()
            return

        srcdir = project_metadata_module.fullpath("source")

        if not os.path.isdir(srcdir):
            raise KBRuntimeError(f"No such source directory {srcdir}!")

        # NOTE: This is approx 1280 entries as of Feb 2023.  Need to memoize this
        # so that only entries that are used end up being read.
        # The obvious thing of using path info to guess module name doesn't work
        # (e.g. maui-booth has a disk path of maui/booth in repo-metadata, not maui/maui-booth)
        repo_meta_files = list(Path(f"{srcdir}/projects").resolve().rglob("metadata.yaml"))  # resolve /projects symlink first, then recurse through dir tree

        for metadata_path in repo_meta_files:
            self._read_yaml(metadata_path)

        if not len(repo_meta_files) > 0:
            raise KBRuntimeError(f"Failed to find KDE project entries from {srcdir}!")

    def _load_mock_project_data(self) -> None:
        # Load some sample projects for use in test mode
        # Should stay in sync with the data generated by _read_yaml
        projects = ["kde-builder", "juk", "kcalc", "konsole", "dolphin"]

        for project in projects:
            repo_data = {
                "full_name": f"test/{project}",
                "repo": f"kde:{project}.git",
                "name": project,
                "active": True,
                "found_by": "direct",
            }

            self.repositories[project] = repo_data

    def _read_yaml(self, filename) -> None:
        with open(filename, "r") as file:
            proj_data = yaml.safe_load(file)

        # This is already "covered" as a special metadata module, ignore
        if proj_data["projectpath"] == "repo-management":
            return

        repo_path = proj_data["repopath"]
        repo_name = proj_data["identifier"] if proj_data["identifier"] else repo_path

        # Keep in sync with _load_mock_project_data
        cur_repository = {
            "full_name": proj_data["projectpath"],
            "invent_name": repo_path,
            "repo": f"kde:{repo_path}.git",
            "name": repo_name,
            "active": bool(proj_data["repoactive"]),
            "found_by": "direct"  # can be changed in get_modules_for_project
        }

        self.repositories[repo_name] = cur_repository

    def get_modules_for_project(self, proj: str) -> list[dict]:
        """
        Get modules for project.

        Note on ``proj``: A "/"-separated path is fine, in which case we look
        for the right-most part of the full path which matches all of searchProject.
        e.g. kde/kdebase/kde-runtime would be matched by a proj of either
        "kdebase/kde-runtime" or simply "kde-runtime".
        """
        repositories = self.repositories
        results = []

        def find_results():
            match_list = [key for key in sorted(repositories.keys()) if KDEProjectsReader.project_path_matches_wildcard_search(repositories[key]["full_name"], proj)]

            if re.search(r"\*", proj):
                for key in match_list:
                    repositories[key]["found_by"] = "wildcard"

            results.extend(match_list)

        # Wildcard matches happen as specified if asked for.
        # Non-wildcard matches have an implicit "$proj/*" search as well for
        # compatibility with previous use-modules
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
        search_parts = search_item.split("/")
        name_stack = project_path.split("/")

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
