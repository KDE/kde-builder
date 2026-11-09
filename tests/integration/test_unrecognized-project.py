# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder.application import Application
from kde_builder.kb_exception import UnknownKdeProjectException


def test_raises_on_unrecognized_project():
    """Test project name that is not a kde project, and is not defined in config."""
    with pytest.raises(UnknownKdeProjectException) as excinfo:
        # kcalc is defined in test project metadata (see _load_mock_project_data).
        # "gnome-calc" is our unrecognized selector.
        app = Application(
            [
                "--pretend",
                "--rc-file",
                "tests/integration/fixtures/sample-rc/kde-builder.yaml",
                "kcalc",
                "gnome-calc",
            ],
        )
        app.generate_module_list()

    assert excinfo.value.unknown_project_name == "gnome-calc", "Correct name of the unrecognized project"


def test_does_not_raise_if_all_projects_recognized():
    """Test that KDE Builder does not raise UnknownKdeProjectException inappropriately."""
    # Test dependencies data contains "kde-builder: third-party/taglib" (see _resolve_module_dependency_graph),
    # and in the config, there is no module named "taglib". This should not raise UnknownKdeProjectException.
    try:
        app = Application(
            [
                "--pretend",
                "--rc-file",
                "tests/integration/fixtures/sample-rc/kde-builder.yaml",
                "--all-config-projects",
            ],
        )
        app.generate_module_list()
    except UnknownKdeProjectException as e:
        pytest.fail(f"Should not raise {e.__class__} when no unknown project is selected.")
