# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

import shutil
from promise import Promise
import os
import tempfile
from ksblib.Module.Module import Module
from ksblib.BuildContext import BuildContext
from ksblib.Util.LoggedSubprocess import Util_LoggedSubprocess


def test_logged_subprocess():
    """
    Test that LoggedSubprocess works (and works reentrantly no less)
    """
    origdir = os.getcwd()
    ctx = BuildContext()
    m = Module(ctx, "test")

    assert ctx, "BuildContext setup"
    assert m, "ksb::Module setup"
    assert m.name == "test", "ksb::Module has a name"

    tmp = tempfile.mkdtemp()
    ctx.setOption({"log-dir": f"{tmp}/kde-builder-test"})

    def func(mod):
        print(f"Calculating stuff for {mod}")

    cmd = Util_LoggedSubprocess() \
        .module(m) \
        .log_to("test-suite-1") \
        .set_command(["perl", "-E", "my $x = 2 + 2; say qq($x);"]) \
        .chdir_to(tmp) \
        .announcer(func)

    assert isinstance(cmd, Util_LoggedSubprocess), "got the right type of cmd"

    output = None
    prog1Exit = None
    prog2Exit = None

    def func2(line):
        nonlocal output
        output = line
        output = output.removesuffix("\n")

    cmd.on({"child_output": func2})

    def func3(exitcode):
        nonlocal prog1Exit
        prog1Exit = exitcode

        # Create a second LoggedSubprocess while the first one is still alive, even
        # though it is finished.
        cmd2 = Util_LoggedSubprocess() \
            .module(m) \
            .log_to("test-suite-2") \
            .set_command(["perl", "-E", "my $x = 4 + 4; say qq(here for stdout); die qq(hello);"]) \
            .chdir_to(tmp)

        def func4(exit2):
            nonlocal prog2Exit
            prog2Exit = exit2

        promise2 = cmd2.start().then(func4)

        return promise2  # Resolve to another promise that requires resolution

    promise = cmd.start().then(func3)

    assert isinstance(promise, Promise), "A promise should be a promise!"
    Promise.wait(promise)

    assert output == "4", "Interior child command successfully completed"
    assert prog1Exit == 0, "Program 1 exited correctly"
    assert prog2Exit != 0, "Program 2 failed"

    assert os.path.isdir(f"{tmp}/kde-builder-test/latest/test"), "Test module had a 'latest' dir setup"
    assert os.path.islink(f"{tmp}/kde-builder-test/latest-by-phase/test/test-suite-1.log"), "Test suite 1 phase log created"
    assert os.path.islink(f"{tmp}/kde-builder-test/latest-by-phase/test/test-suite-2.log"), "Test suite 2 phase log created"

    os.chdir(origdir)  # ensure we're out of the test directory
    shutil.rmtree(tmp)
