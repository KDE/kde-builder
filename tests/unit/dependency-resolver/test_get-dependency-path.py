# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder_lib.dependency_resolver import DependencyResolver
from kde_builder_lib.module.module import Module


@pytest.fixture
def mock_module_fullproject(monkeypatch):
    def mock__init__(self, projectPath, kde):
        self.projectPath = projectPath
        self.kde = kde

    def mock__str__(self):  # need to redefine, because debugger wants to use this
        return self.projectPath

    def mock_isKDEProject(self):
        return self.kde

    # Redefine `Module` to stub fullProjectPath() results
    def mock_fullProjectPath(self):
        return self.projectPath

    monkeypatch.setattr(Module, "__init__", mock__init__)
    monkeypatch.setattr(Module, "__str__", mock__str__)
    monkeypatch.setattr(Module, "isKDEProject", mock_isKDEProject)
    monkeypatch.setattr(Module, "fullProjectPath", mock_fullProjectPath)


def test_dependency_path(mock_module_fullproject):
    """
    Verify that _getDependencyPathOf() works properly
    """
    module1 = Module("test/path", True)

    assert DependencyResolver._getDependencyPathOf(module1, "foo", "bar") == "test/path", "should return full project path if a KDE module object is passed"

    module2 = None

    assert DependencyResolver._getDependencyPathOf(module2, "foo", "bar") == "bar", "should return the provided default if no module is passed"

    module3 = Module("test/path", False)
    assert DependencyResolver._getDependencyPathOf(module3, "foo", "bar") == "third-party/test/path", "should return 'third-party/' prefixed project path if a non-KDE module object is passed"
