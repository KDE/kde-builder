# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import shutil
import tempfile

from kde_builder_lib.build_context import BuildContext
from kde_builder_lib.module.module import Module
from kde_builder_lib.util.logged_subprocess import UtilLoggedSubprocess


def test_logged_subprocess():
    """
    Test that LoggedSubprocess works (and works reentrantly no less).
    """
    origdir = os.getcwd()
    ctx = BuildContext()
    m = Module(ctx, "test")

    assert ctx, "BuildContext setup"
    assert m, "Module set up"
    assert m.name == "test", "Module has a name"

    tmp = tempfile.mkdtemp()
    ctx.set_option("log-dir", f"{tmp}/kde-builder-test")

    def func(mod):
        print(f"Calculating stuff for {mod}")

    cmd = UtilLoggedSubprocess() \
        .module(m) \
        .log_to("test-suite-1") \
        .set_command(["perl", "-E", "my $x = 2 + 2; say qq($x);"]) \
        .chdir_to(tmp) \
        .announcer(func)

    assert isinstance(cmd, UtilLoggedSubprocess), "got the right type of cmd"

    output = None

    def func2(line):
        nonlocal output
        output = line
        output = output.removesuffix("\n")

    cmd.on({"child_output": func2})

    prog1_exit = cmd.start()

    # Create a second LoggedSubprocess while the first one is still alive, even
    # though it is finished.
    cmd2 = UtilLoggedSubprocess() \
        .module(m) \
        .log_to("test-suite-2") \
        .set_command(["perl", "-E", "my $x = 4 + 4; say qq(here for stdout); die qq(hello);"]) \
        .chdir_to(tmp)

    prog2_exit = cmd2.start()

    assert output == "4", "Interior child command successfully completed"
    assert prog1_exit == 0, "Program 1 exited correctly"
    assert prog2_exit != 0, "Program 2 failed"

    assert os.path.isdir(f"{tmp}/kde-builder-test/latest/test"), "Test module had a \"latest\" dir setup"
    assert os.path.islink(f"{tmp}/kde-builder-test/latest-by-phase/test/test-suite-1.log"), "Test suite 1 phase log created"
    assert os.path.islink(f"{tmp}/kde-builder-test/latest-by-phase/test/test-suite-2.log"), "Test suite 2 phase log created"

    os.chdir(origdir)  # ensure we're out of the test directory
    shutil.rmtree(tmp)
