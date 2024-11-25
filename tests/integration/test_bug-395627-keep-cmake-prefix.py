# SPDX-FileCopyrightText: 2018, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.application import Application
from kde_builder_lib.build_system.kde_cmake import BuildSystemKDECMake
from kde_builder_lib.debug import Debug
from kde_builder_lib.util.logged_subprocess import UtilLoggedSubprocess


def test_cmake_prefix(monkeypatch):
    """
    Verify that a user-set CMAKE_PREFIX_PATH is not removed, even if we supply "magic" of our own.

    See bug 395627 -- https://bugs.kde.org/show_bug.cgi?id=395627
    """
    saved_command = []
    set_command_called = 0

    # Redefine set_command to capture whether it was properly called.
    def mock_set_command(self, set_command: list[str]):
        nonlocal set_command_called
        nonlocal saved_command
        set_command_called = 1
        saved_command = set_command
        return self

    monkeypatch.setattr(UtilLoggedSubprocess, "set_command", mock_set_command)

    # Redefine start.
    def mock_start(self) -> int:
        return 0  # success

    monkeypatch.setattr(UtilLoggedSubprocess, "start", mock_start)

    args = "--pretend --rc-file tests/integration/fixtures/bug-395627/kde-builder.yaml --all-config-projects".split(" ")
    app = Application(args)
    module_list = app.modules

    assert len(module_list) == 6, "Right number of modules"
    assert isinstance(module_list[0].build_system(), BuildSystemKDECMake)

    # This requires log_command to be overridden above
    result = module_list[0].setup_build_system()
    assert set_command_called == 1, "Overridden set_command was called"
    assert result, "Setup build system for auto-set prefix path"

    # We should expect an auto-set -DCMAKE_PREFIX_PATH passed to cmake somewhere
    prefix = next((x for x in saved_command if "-DCMAKE_PREFIX_PATH" in x), None)
    assert prefix == "-DCMAKE_PREFIX_PATH=/tmp/qt5", "Prefix path set to custom Qt prefix"

    result = module_list[2].setup_build_system()
    assert result, "Setup build system for manual-set prefix path"

    prefixes = [el for el in saved_command if "-DCMAKE_PREFIX_PATH" in el]
    assert len(prefixes) == 1, "Only one set prefix path in manual mode"
    if prefixes:
        assert prefixes[0] == "-DCMAKE_PREFIX_PATH=FOO", "Manual-set prefix path is as set by user"

    result = module_list[4].setup_build_system()
    assert result, "Setup build system for manual-set prefix path"

    prefixes = [el for el in saved_command if "-DCMAKE_PREFIX_PATH" in el]
    assert len(prefixes) == 1, "Only one set prefix path in manual mode"
    if prefixes:
        assert prefixes[0] == "-DCMAKE_PREFIX_PATH:PATH=BAR", "Manual-set prefix path is as set by user"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
