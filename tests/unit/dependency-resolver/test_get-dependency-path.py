# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder_lib.dependency_resolver import DependencyResolver
from kde_builder_lib.module.module import Module


@pytest.fixture
def mock_module_fullproject(monkeypatch):
    def mock__init__(self, name: str, repo_path="", is_kde=True):
        self.name = name
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
    module1 = Module(name="mod1", repo_path="kdepath/mod1", is_kde=True)

    assert DependencyResolver._get_dependency_path_of(module1) == "kdepath/mod1", "should return full project path if a KDE module object is passed"

    module3 = Module(name="mod3", repo_path="", is_kde=False)
    assert DependencyResolver._get_dependency_path_of(module3) == "third-party/mod3", "should return \"third-party/\" prefixed project path if a non-KDE module object is passed"
