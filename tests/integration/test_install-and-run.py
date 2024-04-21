# SPDX-FileCopyrightText: 2018 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

# Test install and ability to run a simple status command w/out Perl failures

import os
import subprocess
# import tempfile
# import re
from ksblib.Debug import Debug


def test_install_and_run():
    # Assume we're running directly for git source root, as required for rest of
    # test suite.

    assert os.path.isdir("tests"), "Test directory in right spot"
    assert os.path.isfile("kde-builder"), "kde-builder script in right spot"

    # This test can't pass from an installed kde-builder, unless user goes out of
    # their way to move files around or establish a broken module layout. If this
    # passes, we should be able to assume we're running from a git source dir
    assert os.path.isfile("ksblib/Version.py"), "kde-builder modules found in git-src"

    # Make sure kde-builder can still at least start when run directly
    result = subprocess.run(["./kde-builder", "--version", "--pretend"])
    assert result.returncode == 0, "Direct-run kde-builder works"

    # pl2py: Users will not "install" kde-builder to install-dir. They will run it from source-dir.

    # print("Installing kde-builder to simulate running from install-dir")
    # with tempfile.TemporaryDirectory() as tempInstallDir:
    #     os.mkdir(f"{tempInstallDir}/bin")
    #
    #     curdir = os.getcwd()
    #     os.symlink(f"{curdir}/kde-builder", f"{tempInstallDir}/bin/kde-builder")
    #
    #     # Ensure a direct symlink to the source directory of kde-builder still works
    #     os.environ["PATH"] = f"{tempInstallDir}/bin:" + os.environ.get("PATH")
    #
    #     output = subprocess.check_output("pipenv run python kde-builder --version --pretend".split(" ")).decode().strip()
    #     assert re.match(r"^kde-builder \d\d\.\d\d", output), "--version for git-based version is appropriate"
    #     assert os.path.islink(f"{tempInstallDir}/bin/kde-builder"), "kde-builder is supposed to be a symlink"
    #     assert os.unlink(f"{tempInstallDir}/bin/kde-builder") is None, "Remove kde-builder symlink, so it will not conflict with install"

    # pl2py: We do not need to install kde-builder to the install-dir. Users will run it from source dir
    # # Ensure the installed version also works.
    # # TODO: Use manipulation on installed ksb::Version to ensure we're seeing right
    # # output?
    #
    # with tempfile.TemporaryDirectory() as tempBuildDir:
    #     os.chdir(f"{tempBuildDir}")
    #
    #     # Use IPC::Cmd to capture (and ignore) output. All we need is the exit code
    #
    #     command = ["cmake", f"-DCMAKE_INSTALL_PREFIX={tempInstallDir}", "-DBUILD_doc=OFF", curdir]
    #     buildResult = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60).returncode
    #
    #     if not buildResult:
    #         raise "Couldn't run cmake!"
    #
    #     buildResult = subprocess.run(["make"]).returncode
    #
    #     if buildResult == -1 or buildResult != 0:
    #         raise f"Couldn't run make! {buildResult}"
    #
    #     buildResult = subprocess.run(["make", "install"]).returncode
    #
    #     if buildResult == -1 or buildResult != 0:
    #         raise f"Couldn't install! {buildResult}"
    #
    #     # Ensure newly-installed version is first in PATH
    #     os.environ["PATH"] = f"{tempInstallDir}/share/kde-builder:" + os.environ.get("PATH")  # Currently, we install to share.
    ## Note, that when you are running this test in your system with really installed kde-builder somewhere available in PATH, this test
    ## will not be checked properly (it will check invoke your kde-builder, but not that was installed in tmpdir).
    #
    #     # # Ensure we don't accidentally use the git repo modules/ path when we need to use
    #     # # installed or system Perl modules
    #     # local $ENV{PERL5LIB}; # prove turns -Ilib into an env setting
    #
    #     output = subprocess.run("kde-builder --version --pretend").stdout.decode()
    #     assert re.match(r"^kde-builder \d\d\.\d\d\n?$", output), "--version for installed version is appropriate"
    #     os.chdir(curdir)
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
