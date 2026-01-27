# SPDX-FileCopyrightText: 2012, 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import yaml
import os
import re

from ..kb_exception import KBRuntimeError
from ..kb_exception import ProgramError
from ..debug import Debug
from ..util.util import Util


class Metadata:
    """
    Stores data (ignored projects and branch groups) that is read from repo-metadata repository.
    """

    def __init__(self, path_to_metadata: str):
        self.path_to_metadata = path_to_metadata

        self.ignored_projects = self._ignored_modules()
        self.branch_groups = self._logical_module_groups()

    def _ignored_modules(self) -> list[str]:
        """
        Return a list of the full kde-project paths for each module to ignore.
        """
        path = self.path_to_metadata + "/kde-dependencies/ignore-kde-projects"

        # Now that we in theory have up-to-date source code, read in the
        # ignore file and propagate that information to our context object.

        if Debug().is_testing():
            kb_repo_dir = os.path.normpath(os.path.dirname(os.path.realpath(__file__)) + "/../..")
            path = kb_repo_dir + "/tests/fixtures/repo-metadata/kde-dependencies/ignore-kde-projects"

        try:
            fh = open(path, "r")
        except IOError:
            raise ProgramError(f"Unable to read ignore data from {path}")

        ignore_modules = []
        for line in fh:
            # 1 Remove comments
            line = re.sub("#.*$", "", line)

            # 2 Filter empty lines
            if not line.strip():
                continue

            # 3 Remove newlines
            line = line.rstrip("\n")

            ignore_modules.append(line)
        fh.close()
        return ignore_modules

    def _logical_module_groups(self) -> dict:
        """
        Return a dict of the branch-groups.yaml file.

        The metadata should already be downloaded.
        """
        path = self.path_to_metadata + "/kde-dependencies/branch-groups.yaml"

        if Debug().is_testing():
            kb_repo_dir = os.path.normpath(os.path.dirname(os.path.realpath(__file__)) + "/../..")
            path = kb_repo_dir + "/tests/fixtures/repo-metadata/kde-dependencies/branch-groups.yaml"

        try:
            fh = open(path, "r")
        except IOError:
            raise ProgramError("Unable to read branch-groups.yaml")

        try:
            yaml_str = fh.read()  # slurps the whole file
            yaml_dict = yaml.safe_load(yaml_str)
            fh.close()
        except Exception as e:
            raise KBRuntimeError(f"Unable to load branch-groups from {path}! :(\n\t{e}")
        return yaml_dict
