# SPDX-FileCopyrightText: 2018, 2019 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from ksblib.Application import Application
from ksblib.Debug import Debug


@pytest.fixture
def mock_app_res_mod_dep_graph(monkeypatch):
    def mock_resolveModuleDependencyGraph(self, modules: list):
        """
        Redefine :meth:`Application._resolveModuleDependencies` to avoid requiring metadata module.
        """
        newModule = self.module_factory("setmod2")

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
                    "module": newModule,
                }

        return {"graph": graph}

    monkeypatch.setattr(Application, "_resolveModuleDependencyGraph", mock_resolveModuleDependencyGraph)


def test_include_deps(mock_app_res_mod_dep_graph):
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kdesrc-buildrc --include-dependencies setmod1 setmod3".split(" ")
    app = Application(args)
    moduleList = app.modules

    assert len(moduleList) == 3, "Right number of modules (include-dependencies)"
    assert moduleList[0].name == "setmod1", "mod list[0] == setmod1"
    assert moduleList[1].name == "setmod2", "mod list[1] == setmod2"
    assert moduleList[2].name == "setmod3", "mod list[2] == setmod3"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton


def test_include_deps_and_ignore_module(mock_app_res_mod_dep_graph):
    """
    Verify that --ignore-modules works for modules that would be included with --include-dependencies in effect.
    See bug 394497 -- https://bugs.kde.org/show_bug.cgi?id=394497
    """
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kdesrc-buildrc --include-dependencies setmod1 setmod3 --ignore-modules setmod2".split(" ")
    app = Application(args)
    moduleList = app.modules

    assert len(moduleList) == 2, "Right number of modules (include-dependencies+ignore-modules)"
    assert moduleList[0].name == "setmod1", "mod list[0] == setmod1"
    assert moduleList[1].name == "setmod3", "mod list[1] == setmod3"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton


def test_include_deps_and_ignore_module_set(mock_app_res_mod_dep_graph):
    """
    Verify that --include-dependencies on a moduleset name filters out the whole set
    """
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kdesrc-buildrc --ignore-modules set1".split(" ")

    app = Application(args)
    moduleList = app.modules

    assert len(moduleList) == 1, "Right number of modules (ignore module-set)"
    assert moduleList[0].name == "module2", "mod list[0] == module2"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
