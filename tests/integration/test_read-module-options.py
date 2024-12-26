# SPDX-FileCopyrightText: 2018 - 2020, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys

# Now we can load `Application`, which will load a bunch more modules all
# using log_command and run_logged_p from `Util`
from kde_builder_lib.application import Application
from kde_builder_lib.debug import Debug
from kde_builder_lib.updater.updater import Updater
from kde_builder_lib.util.logged_subprocess import UtilLoggedSubprocess  # load early so we can override


def test_option_reading(monkeypatch):
    """
    Test basic option reading from rc-files.
    """
    cmd = []

    # Override UtilLoggedSubprocess.set_command for final test to see if it is called with "cmake"
    def mock_set_command(self, set_command: list[str]):
        nonlocal cmd
        if not set_command:
            raise "No arg to module"
        command = set_command
        if "cmake" in command:
            cmd = command
        return self

    monkeypatch.setattr(UtilLoggedSubprocess, "set_command", mock_set_command)

    # Override start.
    def mock_start(self) -> int:
        return 0

    monkeypatch.setattr(UtilLoggedSubprocess, "start", mock_start)

    app = Application("--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --all-config-projects".split(" "))
    module_list = app.modules

    assert len(module_list) == 4, "Right number of modules"

    # module2 is last in rc-file so should sort last
    assert module_list[3].name == "module2", "Right module name"

    scm = module_list[3].scm()
    assert isinstance(scm, Updater)

    branch, sourcetype = scm.determine_preferred_checkout_source()

    assert branch == "refs/tags/fake-tag5", "Right tag name"
    assert sourcetype == "tag", "Result came back as a tag"

    # setmod2 is second module in set of 3 at start, should be second overall
    assert module_list[1].name == "setmod2", "Right module name from module-set"
    branch, sourcetype = module_list[1].scm().determine_preferred_checkout_source()

    assert branch == "refs/tags/tag-setmod2", "Right tag name (options block)"
    assert sourcetype == "tag", "options block came back as tag"

    # Test some of the option parsing indirectly by seeing how the value is input
    # into build system.

    # Override auto-detection since no source is downloaded
    module_list[1].set_option("override-build-system", "kde")

    # Should do nothing in --pretend
    assert module_list[1].setup_build_system(), "setup fake build system"

    assert cmd, "run_logged_p cmake was called"
    if sys.prefix != sys.base_prefix:
        assert len(cmd) == 14
    else:
        assert len(cmd) == 12

    assert cmd[0] == "cmake", "CMake command should start with cmake"
    assert cmd[1] == "-B",    "Passed build dir to cmake"
    assert cmd[2] == ".",     "Passed cur dir as build dir to cmake"
    assert cmd[3] == "-S",    "Pass source dir to cmake"
    assert cmd[4] == "/tmp/setmod2", "CMake command should specify source directory after -S"
    assert cmd[5] == "-G", "CMake generator should be specified explicitly"
    assert cmd[6] == "Unix Makefiles", "Expect the default CMake generator to be used"
    assert cmd[7] == "-DCMAKE_EXPORT_COMPILE_COMMANDS:BOOL=ON", "Per default we generate compile_commands.json"
    assert cmd[8] == "-DCMAKE_BUILD_TYPE=a b", "CMake options can be quoted"
    assert cmd[9] == "bar=c", "CMake option quoting does not eat all options"
    assert cmd[10] == "baz", "Plain CMake options are preserved correctly"
    assert cmd[11] == f"""-DCMAKE_INSTALL_PREFIX={os.environ.get("HOME")}/kde/usr""", "Prefix is passed to cmake"
    if sys.prefix != sys.base_prefix:
        assert cmd[12] == "-DPython3_FIND_VIRTUALENV=STANDARD", "If in venv, Python3_FIND_VIRTUALENV is appended"
        assert cmd[13] == "-DPython3_FIND_UNVERSIONED_NAMES=FIRST", "If in venv, Python3_FIND_UNVERSIONED_NAMES is appended"

    # See https://phabricator.kde.org/D18165
    assert module_list[0].get_option("cxxflags") == "", "empty cxxflags renders with no whitespace in module"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
