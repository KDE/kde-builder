# SPDX-FileCopyrightText: 2019, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest
from ksblib.Application import Application
from ksblib.Debug import Debug


@pytest.fixture
def mock_application(monkeypatch):
    # Redefine ksb::Application::_resolveModuleDependencies to avoid requiring metadata module.
    def mock_resolveModuleDependencyGraph(self, modules: list):
        newModule = self.module_factory("setmod2")

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
                "build": bool(self.context.getOption("include-dependencies")),
                "module": newModule
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

    monkeypatch.setattr(Application, "_resolveModuleDependencyGraph", mock_resolveModuleDependencyGraph)


def test_no_include_deps(mock_application):
    """
    Verify that --no-include-dependencies is recognized and results in right value.
    """
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kdesrc-buildrc-with-deps --no-include-dependencies setmod1 setmod3".split(" ")
    app = Application(args)
    moduleList = app.modules

    assert len(moduleList) == 2, "Right number of modules (include-dependencies)"
    assert moduleList[0].name == "setmod1", "mod list[0] == setmod1"
    assert moduleList[1].name == "setmod3", "mod list[2] == setmod3"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton


def test_no_include_deps_ignore_modules(mock_application):
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kdesrc-buildrc-with-deps --no-include-dependencies setmod1 setmod3 --ignore-modules setmod2".split(" ")
    app = Application(args)
    moduleList = app.modules

    assert len(moduleList) == 2, "Right number of modules (include-dependencies+ignore-modules)"
    assert moduleList[0].name == "setmod1", "mod list[0] == setmod1"
    assert moduleList[1].name == "setmod3", "mod list[1] == setmod3"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
