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
    Ensure that the custom-build-command can at least make it to the module.build_internal() portion when no build system can be auto-detected.
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
    def mock_build_internal(self, *args, **kwargs):
        assert self.name() == "generic", "custom-build-system is generic unless overridden"
        BuildSystem.testSucceeded = 1

        return {"was_successful": 1}

    # Mock override
    def mock_needs_refreshed(self):
        return ""

    # Mock override
    def mock_create_build_system(self):
        return 1

    # Mock override
    def mock_configure_internal(self):
        return 1

    monkeypatch.setattr(BuildSystem, "build_internal", mock_build_internal)
    monkeypatch.setattr(BuildSystem, "needs_refreshed", mock_needs_refreshed)
    monkeypatch.setattr(BuildSystem, "create_build_system", mock_create_build_system)
    monkeypatch.setattr(BuildSystem, "configure_internal", mock_configure_internal)

    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --all-config-projects --no-metadata --custom-build-command echo --override-build-system generic".split(" ")
    app = Application(args)
    module_list = app.modules

    assert len(module_list) == 4, "Right number of modules"
    assert module_list[0].name == "setmod1", "mod list[0] == setmod1"

    module = module_list[0]
    assert module.get_option("custom-build-command") == "echo", "Custom build command setup"
    assert module.get_option("override-build-system") == "generic", "Custom build system required"

    assert module.build_system() is not None, "module has a build_system"

    # Don't use ->isa because we want this exact class
    assert isinstance(module.build_system(), BuildSystem)

    # Disable --pretend mode, the build/install methods should be mocked and
    # harmless and we won't proceed to build_internal if in pretend mode
    # otherwise.
    Debug().set_pretending(False)
    orig_dir = os.getcwd()
    module.build()
    os.chdir(orig_dir)  # pl2py somehow the changed dir in this test remains in another. So we will revert dir manually.

    assert BuildSystem.testSucceeded == 1, "Made it to build_internal()"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
