# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os.path
import tempfile

from kde_builder_lib.util.util import Util


def test_safe_lndir():
    """
    Test safe_lndir_p.
    """
    tmpdir = tempfile.mkdtemp(prefix="kde-builder-testXXXXXX")
    assert tmpdir, "tempdir created"

    file = os.path.join(tmpdir, "a")
    open(file, "a").close()
    assert os.path.exists(file), "first file created"

    dir2 = os.path.join(tmpdir, "b/c")
    os.makedirs(dir2)
    assert os.path.isdir(f"{tmpdir}/b/c"), "dir created"

    file2 = os.path.join(tmpdir, "b", "c", "file2")
    open(file2, "a").close()
    assert os.path.exists(f"{tmpdir}/b/c/file2"), "second file created"

    to = tempfile.mkdtemp(prefix="kde-builder-test2")
    Util.safe_lndir(os.path.abspath(tmpdir), os.path.abspath(to))

    assert os.path.isdir(f"{to}/b/c"), "directory symlinked over"
    assert os.path.islink(f"{to}/a"), "file under directory is a symlink"
    assert os.path.exists(f"{to}/a"), "file under directory exists"
    assert not os.path.exists(f"{to}/b/d/file3"), "nonexistent file does not exist"
    assert os.path.islink(f"{to}/b/c/file2"), "file2 under directory is a symlink"
    assert os.path.exists(f"{to}/b/c/file2"), "file2 under directory exists"
