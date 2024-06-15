# SPDX-FileCopyrightText: 2021, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from kde_builder_lib.application import Application
from kde_builder_lib.build_system.build_system import BuildSystem
from kde_builder_lib.debug import Debug
from kde_builder_lib.module.module import Module


def test_build_internal(monkeypatch):
    """
    Ensure that the custom-build-command can at least make it to the
    module.buildInternal() portion when no build system can be auto-detected.
    """

    # Mock override
    def mock_update(self, *args, **kwargs):
        assert str(self) == self.name, "We're a real Module"
        assert not self.pretending(), "Test makes no sense if we're pretending"
        return 0  # shell semantics

    # Mock override
    def mock_install(self):
        return False

    monkeypatch.setattr(Module, "update", mock_update)
    monkeypatch.setattr(Module, "install", mock_install)

    BuildSystem.testSucceeded = 0

    # Mock override
    def mock_buildInternal(self, *args, **kwargs):
        assert self.name() == "generic", "custom-build-system is generic unless overridden"
        BuildSystem.testSucceeded = 1

        return {"was_successful": 1}

    # Mock override
    def mock_needsRefreshed(self):
        return ""

    # Mock override
    def mock_createBuildSystem(self):
        return 1

    # Mock override
    def mock_configureInternal(self):
        return 1

    monkeypatch.setattr(BuildSystem, "buildInternal", mock_buildInternal)
    monkeypatch.setattr(BuildSystem, "needsRefreshed", mock_needsRefreshed)
    monkeypatch.setattr(BuildSystem, "createBuildSystem", mock_createBuildSystem)
    monkeypatch.setattr(BuildSystem, "configureInternal", mock_configureInternal)

    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kdesrc-buildrc --no-metadata --custom-build-command echo --override-build-system generic".split(" ")
    app = Application(args)
    moduleList = app.modules

    assert len(moduleList) == 4, "Right number of modules"
    assert moduleList[0].name == "setmod1", "mod list[0] == setmod1"

    module = moduleList[0]
    assert module.getOption("custom-build-command") == "echo", "Custom build command setup"
    assert module.getOption("override-build-system") == "generic", "Custom build system required"

    assert module.buildSystem() is not None, "module has a build_system"

    # Don't use ->isa because we want this exact class
    assert isinstance(module.buildSystem(), BuildSystem)

    # Disable --pretend mode, the build/install methods should be mocked and
    # harmless and we won't proceed to buildInternal if in pretend mode
    # otherwise.
    Debug().setPretending(False)
    orig_dir = os.getcwd()
    module.build()
    os.chdir(orig_dir)  # pl2py somehow the changed dir in this test remains in another. So we will revert dir manually.

    assert BuildSystem.testSucceeded == 1, "Made it to buildInternal()"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
