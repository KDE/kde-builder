# SPDX-FileCopyrightText: 2019, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder_lib.application import Application
from kde_builder_lib.debug import Debug


@pytest.fixture
def mock_application(monkeypatch):
    # Redefine Application._resolveModuleDependencies to avoid requiring metadata module.
    def mock_resolve_module_dependency_graph(self, modules: list):
        new_module = self.module_factory("setmod2")

        graph = {
            "setmod1": {
                "votes": {
                    "setmod2": 1,
                    "setmod3": 1
                },
                "build": 1,
                "module": modules[0]
            },
            "setmod2": {
                "votes": {
                    "setmod3": 1
                },
                "build": bool(self.context.get_option("include-dependencies")),
                "module": new_module
            },
            "setmod3": {
                "votes": {},
                "build": 1,
                "module": modules[1]
            }
        }

        result = {
            "graph": graph
        }

        return result

    monkeypatch.setattr(Application, "_resolve_module_dependency_graph", mock_resolve_module_dependency_graph)


def test_no_include_deps(mock_application):
    """
    Verify that --no-include-dependencies is recognized and results in right value.
    """
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder-with-deps.yaml --no-include-dependencies setmod1 setmod3".split(" ")
    app = Application(args)
    module_list = app.modules

    assert len(module_list) == 2, "Right number of modules (include-dependencies)"
    assert module_list[0].name == "setmod1", "mod list[0] == setmod1"
    assert module_list[1].name == "setmod3", "mod list[2] == setmod3"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton


def test_no_include_deps_ignore_modules(mock_application):
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder-with-deps.yaml --no-include-dependencies setmod1 setmod3 --ignore-projects setmod2".split(" ")
    app = Application(args)
    module_list = app.modules

    assert len(module_list) == 2, "Right number of modules (include-dependencies+ignore-projects)"
    assert module_list[0].name == "setmod1", "mod list[0] == setmod1"
    assert module_list[1].name == "setmod3", "mod list[1] == setmod3"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
