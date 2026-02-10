# SPDX-FileCopyrightText: 2013, 2014, 2017, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os.path
from pathlib import Path
import re

import yaml

from ..kb_exception import KBRuntimeError
from ..kb_exception import NoKDEProjectsFound
from ..debug import Debug
from ..debug import KBLogger

logger_moduleset = KBLogger.getLogger("module-set")


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

    def get_identifiers_for_selector(self, selector: str, ignore_list: list[str]) -> list[str]:
        """
        Expand selector to list of project identifiers it represents.

        Args:
            selector: The selector string. May contain "/". May end with "*".
                If "/"-separated path is used, we look for the right-most part of that.
                E.g. "utilities/kcalc" would be converted to "kcalc".
            ignore_list: A list of selectors to ignore.
        """
        repositories = self.repositories
        sorted_keys = sorted(repositories.keys())

        all_matched_metadata: list[dict[str, str | bool]] = []
        for key in sorted_keys:
            if self._repopath_matches_selector(repositories[key]["invent_name"], selector):
                all_matched_metadata.append(repositories[key])

        if not all_matched_metadata:
            # To differentiate with the situation when the returned list is empty (because of ignoring some projects
            # or because of some kde projects are inactive), we will raise exception.
            raise NoKDEProjectsFound(f"No KDE projects with such path component: {selector}")

        active_matched_metadata: list[dict[str, str | bool]] = [metadata for metadata in all_matched_metadata if metadata.get("active")]

        if not active_matched_metadata:
            logger_moduleset.warning(f" y[b[*] Selector y[{selector}] is expanded only to inactive projects!")

        filtered_metadata = []

        for active_metadata in active_matched_metadata:
            active_repopath = active_metadata["invent_name"]

            for ignore_selector in ignore_list:
                if self._repopath_matches_selector(active_repopath, ignore_selector):
                    break
            else:
                filtered_metadata.append(active_metadata)

        result_names = [metadata["name"] for metadata in filtered_metadata]
        return result_names

    @staticmethod
    def _repopath_matches_selector(repopath: str, selector: str) -> bool:
        """
        Return True if the given kde-project full repopath (e.g. "utilities/kcalc") matches the given selector.

        The selector can be based on path-components. Each path component in
        the selector must be present in the equivalent path component in the
        repopath for a match. A "*" in a path component position for the
        selector matches any repopath component.

        Args:
            repopath: The full repopath from the kde-projects database.
            selector: The selector.

        Returns:
             True if they match, False otherwise.
        """
        selector_parts: list[str] = selector.split("/")
        repopath_parts: list[str] = repopath.split("/")

        if len(repopath_parts) >= len(selector_parts):
            size_difference = len(repopath_parts) - len(selector_parts)

            # We might have to loop if we somehow find the wrong start point for our search.
            # E.g. looking for a/b/* against a/a/b/c, we'd need to start with the second a.
            i = 0
            while i <= size_difference:
                # Find our common prefix, then ensure the remainder matches item-for-item.
                while i <= size_difference:
                    if repopath_parts[i] == selector_parts[0]:
                        break
                    i += 1

                if i > size_difference:  # Not enough room to find it now
                    return False

                # At this point we have synced up repopath_parts to selector_parts, ensure they
                # match item-for-item.
                found = 1
                j = 0
                while found and j < len(selector_parts):
                    if selector_parts[j] == "*":  # This always works
                        return True
                    if selector_parts[j] != repopath_parts[i + j]:
                        found = 0
                    j += 1

                if found:  # We matched every item to the substring we found.
                    return True
                i += 1  # Try again
        return False
