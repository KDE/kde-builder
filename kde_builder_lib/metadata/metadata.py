# SPDX-FileCopyrightText: 2012, 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json
import re
import textwrap

from ..kb_exception import KBException
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
        path = self.path_to_metadata + "/dependencies/build-script-ignore"

        # Now that we in theory have up-to-date source code, read in the
        # ignore file and propagate that information to our context object.

        if Debug().is_testing():
            from io import StringIO
            mock_build_script_ignore = textwrap.dedent("""\
                sdk/kde-ruleset  # example ignoring
                """)
            fh = StringIO(mock_build_script_ignore)
        else:
            fh = Util.open_or_fail(path)

        if not fh:
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
        Return a dict to the logical module group data.

        JSON support should be present, and the metadata should already be downloaded (e.g. with ``update_internal``).
        Logical module group data is contained within the kde-build-metadata, decoded from its JSON format.
        See https://community.kde.org/Infrastructure/Project_Metadata
        """
        path = self.path_to_metadata + "/dependencies/logical-module-structure.json"

        if Debug().is_testing():
            from io import StringIO
            mock_lms_json = textwrap.dedent("""\
                {
                    "groups": {}
                }
                """)
            fh = StringIO(mock_lms_json)
        else:
            fh = Util.open_or_fail(path)

        if not fh:
            raise ProgramError("Unable to read logical-module-structure")

        try:
            json_string = fh.read()  # slurps the whole file
            json_dict = json.loads(json_string)
            fh.close()
        except KBException as e:
            raise KBRuntimeError(f"Unable to load logical-module-structure from {path}! :(\n\t{e}")
        return json_dict
