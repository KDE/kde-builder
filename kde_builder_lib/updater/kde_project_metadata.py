# SPDX-FileCopyrightText: 2012, 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json
import re

from .kde_project import UpdaterKDEProject
from ..build_exception import BuildException
from ..debug import Debug
from ..ipc.null import IPCNull
from ..util.util import Util


class UpdaterKDEProjectMetadata(UpdaterKDEProject):
    """
    Updater used only to specifically update the "repo-metadata" module
    used for storing dependency information, among other things.

    Note: 2020-06-20 the previous "kde-build-metadata" module was combined into
    the "repo-metadata" module, under the "/dependencies" folder.
    """

    @staticmethod
    # @override(check_signature=False)
    def name() -> str:
        return "metadata"

    def ignored_modules(self) -> list[str]:
        """
        Returns a list of the full kde-project paths for each module to ignore.
        """
        path = self.module.fullpath("source") + "/dependencies/build-script-ignore"

        # Now that we in theory have up-to-date source code, read in the
        # ignore file and propagate that information to our context object.

        fh = Util.pretend_open(path) or BuildException.croak_internal(f"Unable to read ignore data from {path}")

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

    def logical_module_groups(self) -> dict:
        """
        If JSON support is present, and the metadata has already been downloaded
        (e.g. with ``update_internal``), returns a dict to the logical module group
        data contained within the kde-build-metadata, decoded from its JSON format.
        See https://community.kde.org/Infrastructure/Project_Metadata
        """
        path = self.module.fullpath("source") + "/dependencies/logical-module-structure.json"

        # The {} is an empty JSON obj to support pretend mode
        fh = Util.pretend_open(path, "{}") or BuildException.croak_internal("Unable to read logical module structure")

        try:
            json_string = fh.read()  # slurps the whole file
            json_dict = json.loads(json_string)
            fh.close()
        except BuildException as e:
            BuildException.croak_runtime(f"Unable to load module group data from {path}! :(\n\t{e}")
        return json_dict

    # @override(check_signature=False)
    def update_internal(self, ipc=IPCNull()) -> None:
        if Debug().is_testing():
            return

        super().update_internal(ipc)
