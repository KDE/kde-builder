# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder_lib.application import Application
from kde_builder_lib.kb_exception import UnknownKdeProjectException
from kde_builder_lib.debug import Debug


def test_unrecognized_project():
    """
    Test project name that is not a kde project, and is not defined in config.
    """
    with pytest.raises(UnknownKdeProjectException) as excinfo:
        # kcalc is defined in test project metadata (see _load_mock_project_data). "gnome-calc" is our unrecognized selector.
        Application(["--pretend", "--rc-file", "tests/integration/fixtures/sample-rc/kde-builder.yaml", "kcalc", "gnome-calc"])

    assert excinfo.value.unknown_project_name == "gnome-calc", "Correct name of the unrecognized project"

    try:
        # Test dependencies data contains "kde-builder: third-party/taglib" (see _resolve_module_dependency_graph), and in the config,
        # there is no module named "taglib". This should not raise UnknownKdeProjectException.
        Application(["--pretend", "--rc-file", "tests/integration/fixtures/sample-rc/kde-builder.yaml"])
    except UnknownKdeProjectException:
        pytest.fail("Unexpectedly raised UnknownKdeProjectException when there was no unknown project selector in command line")

    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
