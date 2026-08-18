# SPDX-FileCopyrightText: 2012, 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import yaml

from kde_builder import KB_REPO_DIR
from kde_builder.kb_exception import KBRuntimeError
from kde_builder.debug import Debug


class Metadata:
    """
    Stores data (ignored projects and branch groups) that is read from repo-metadata repository.
    """

    def __init__(self, path_to_metadata: str):
        self.path_to_metadata = path_to_metadata

        self.ignored_projects = self._read_ignore_kde_projects()
        self.branch_groups = self._read_branch_groups()

    def _read_ignore_kde_projects(self) -> list[str]:
        """
        Return a list of the full kde-project paths for each project to ignore.
        """
        path = self.path_to_metadata + "/ignore-kde-projects"

        if Debug().is_testing():
            path = KB_REPO_DIR + "/tests/fixtures/repo-metadata/ignore-kde-projects"

        ignore_projects = []
        try:
            with open(path, "r") as file:
                for line in file:
                    line = line.split("#", 1)[0].strip()  # Remove comments, leading and trailing whitespace and newlines
                    if not line:
                        continue
                    ignore_projects.append(line)
        except FileNotFoundError:
            raise KBRuntimeError("Unable to read ignore-kde-projects")

        return ignore_projects

    def _read_branch_groups(self) -> dict:
        """
        Return a dict of the branch-groups.yaml file.

        The metadata should already be downloaded.
        """
        path = self.path_to_metadata + "/branch-groups.yaml"

        if Debug().is_testing():
            path = KB_REPO_DIR + "/tests/fixtures/repo-metadata/branch-groups.yaml"

        try:
            with open(path, "r") as file:
                yaml_dict = yaml.safe_load(file)
        except FileNotFoundError:
            raise KBRuntimeError("Unable to read branch-groups.yaml")
        except yaml.YAMLError:
            raise KBRuntimeError(f"Unable to load branch-groups.yaml")

        return yaml_dict
