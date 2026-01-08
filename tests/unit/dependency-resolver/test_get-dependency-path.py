# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder_lib.dependency_resolver import DependencyResolver
from kde_builder_lib.module.module import Module


@pytest.fixture
def mock_module_fullproject(monkeypatch):
    def mock__init__(self, repo_path="", is_kde=True):
        self.repo_path = repo_path
        self.is_kde = is_kde

    def mock__str__(self):  # need to redefine, because debugger wants to use this
        return self.repo_path

    def mock_is_kde_project(self):
        return self.is_kde

    def mock_get_repopath(self):
        return self.repo_path

    monkeypatch.setattr(Module, "__init__", mock__init__)
    monkeypatch.setattr(Module, "__str__", mock__str__)
    monkeypatch.setattr(Module, "is_kde_project", mock_is_kde_project)
    monkeypatch.setattr(Module, "get_repopath", mock_get_repopath)


def test_dependency_path(mock_module_fullproject):
    """
    Verify that _get_dependency_path_of() works properly.
    """
    module1 = Module(repo_path="test/path", is_kde=True)

    assert DependencyResolver._get_dependency_path_of(module1, "foo", "bar") == "test/path", "should return full project path if a KDE module object is passed"

    module2 = None

    assert DependencyResolver._get_dependency_path_of(module2, "foo", "bar") == "bar", "should return the provided default if no module is passed"

    module3 = Module(repo_path="test/path", is_kde=False)
    assert DependencyResolver._get_dependency_path_of(module3, "foo", "bar") == "third-party/test/path", "should return \"third-party/\" prefixed project path if a non-KDE module object is passed"
