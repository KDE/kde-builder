# SPDX-FileCopyrightText: 2018, 2019 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder_lib.application import Application
from kde_builder_lib.debug import Debug


@pytest.fixture
def mock_app_res_mod_dep_graph(monkeypatch):
    def mock_resolve_module_dependency_graph(self, modules: list):
        """
        Redefine :meth:`Application._resolveModuleDependencies` to avoid requiring metadata module.
        """
        new_module = self.module_factory("setmod2")

        graph = {}

        # Construct graph manually based on real module list
        for module in modules:
            name = module.name
            graph[name] = {
                "votes": {},
                "build": 1,
                "module": module,
            }

        if "setmod1" in graph:
            graph["setmod1"]["votes"] = {
                "setmod2": 1,
                "setmod3": 1
            }

            # setmod1 is only user of setmod2
            if "setmod2" not in graph:
                graph["setmod2"] = {
                    "votes": {
                        "setmod3": 1
                    },
                    "build": 1,
                    "module": new_module,
                }

        return {"graph": graph}

    monkeypatch.setattr(Application, "_resolve_module_dependency_graph", mock_resolve_module_dependency_graph)


def test_include_deps(mock_app_res_mod_dep_graph):
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --include-dependencies setmod1 setmod3".split(" ")
    app = Application(args)
    module_list = app.modules

    assert len(module_list) == 3, "Right number of modules (include-dependencies)"
    assert module_list[0].name == "setmod1", "mod list[0] == setmod1"
    assert module_list[1].name == "setmod2", "mod list[1] == setmod2"
    assert module_list[2].name == "setmod3", "mod list[2] == setmod3"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton


def test_include_deps_and_ignore_module(mock_app_res_mod_dep_graph):
    """
    Verify that --ignore-projects works for modules that would be included with --include-dependencies in effect.

    See bug 394497 -- https://bugs.kde.org/show_bug.cgi?id=394497
    """
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --include-dependencies setmod1 setmod3 --ignore-projects setmod2".split(" ")
    app = Application(args)
    module_list = app.modules

    assert len(module_list) == 2, "Right number of modules (include-dependencies+ignore-projects)"
    assert module_list[0].name == "setmod1", "mod list[0] == setmod1"
    assert module_list[1].name == "setmod3", "mod list[1] == setmod3"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton


def test_include_deps_and_ignore_module_set(mock_app_res_mod_dep_graph):
    """
    Verify that --include-dependencies on a module_set name filters out the whole set.
    """
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --all-config-projects --ignore-projects set1".split(" ")

    app = Application(args)
    module_list = app.modules

    assert len(module_list) == 1, "Right number of modules (ignore module-set)"
    assert module_list[0].name == "module2", "mod list[0] == module2"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
