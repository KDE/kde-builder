# SPDX-FileCopyrightText: 2019, 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import shutil
import subprocess
import tempfile

from kde_builder_lib.updater.updater import Updater


def run_command(command):
    try:
        p = subprocess.run(command, stderr=subprocess.STDOUT, timeout=10, universal_newlines=True)
        return not p.returncode
    except subprocess.CalledProcessError:
        return False
    except subprocess.TimeoutExpired:
        return False


def test_submodule():
    """
    Test submodule-related features.
    """
    # Create an empty directory for a git module, ensure submodule-related things
    # work without a submodule, then add a submodule and ensure that things remain
    # as expected.
    origdir = os.getcwd()
    tmpdir = tempfile.mkdtemp()
    os.chdir(tmpdir)

    # Setup the later submodule
    os.mkdir("submodule")
    os.chdir("submodule")

    result = run_command(["git", "init"])
    assert result, "git init worked"

    with open("README.md", "w") as file:
        file.write("Initial content")

    result = run_command("git config --local user.name kde-builder".split(" "))
    if not result:
        raise SystemExit("Can't setup git username, subsequent tests will fail")

    result = run_command("git config --local user.email kde-builder@kde.org".split(" "))
    if not result:
        raise SystemExit("Can't setup git username, subsequent tests will fail")

    result = run_command("git add README.md".split(" "))
    assert result, "git add file worked"

    result = run_command("git commit -m FirstCommit".split(" "))
    assert result, "git commit worked"

    # Setup a supermodule
    os.chdir(tmpdir)

    os.mkdir("supermodule")
    os.chdir("supermodule")

    result = run_command("git init".split(" "))
    assert result, "git supermodule init worked"

    with open("README.md", "w") as file:
        file.write("Initial content")

    result = run_command("git config --local user.name kde-builder".split(" "))
    if not result:
        raise SystemExit("Can't setup git username, subsequent tests will fail")

    result = run_command("git config --local user.email kde-builder@kde.org".split(" "))
    if not result:
        raise SystemExit("Can't setup git username, subsequent tests will fail")

    result = run_command("git add README.md".split(" "))
    assert result, "git supermodule add file worked"

    result = run_command("git commit -m FirstCommit".split(" "))
    assert result, "git supermodule commit worked"

    # Submodule checks

    assert not Updater._has_submodules(), "No submodules detected when none present"

    # git now prevents use of local clones of other git repos on the file system
    # unless specifically enabled, due to security risks from symlinks. See
    # https://github.blog/2022-10-18-git-security-vulnerabilities-announced/#cve-2022-39253
    result = run_command("git -c protocol.file.allow=always submodule add ../submodule".split(" "))
    assert result, "git submodule add worked"

    assert Updater._has_submodules(), "Submodules detected when they are present"

    os.chdir(origdir)  # Allow auto-cleanup
    shutil.rmtree(tmpdir)
