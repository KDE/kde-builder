# SPDX-FileCopyrightText: 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

import os
import tempfile
from ksblib.Util.Util import Util
from ksblib.BuildContext import BuildContext
from promise import Promise
from pathlib import Path


def test_prune_under_dir():
    """
    Test prune_under_directory_p, including ability to remove read-only files in sub-tree
    """
    tmpdir = tempfile.mkdtemp(prefix="kde-builder-testXXXXXX")
    assert tmpdir, "tempdir created"

    file = os.path.join(tmpdir, "a")
    open(file, "a").close()
    assert os.path.exists(file), "first file created"

    new_permissions = 0o444
    os.chmod(file, new_permissions)
    assert os.stat(file).st_mode & new_permissions == new_permissions, "Changed mode to readonly"

    ctx = BuildContext()
    ctx.setOption({"log-dir": os.path.abspath(tmpdir)})
    promise = Util.prune_under_directory_p(ctx, os.path.abspath(tmpdir))

    # This shouldn't disappear until we let the promise start!
    # assert os.path.exists(file), "prune_under_directory_p does not start until we let promise run"  # pl2py: we use promise that starts as we make it

    Promise.wait(promise)

    assert not os.path.exists(file), "Known read-only file removed"

    files = list(Path(tmpdir).rglob("*"))
    if len(files) == 0:
        assert len(files) == 0, f"entire directory {tmpdir} removed"
    else:
        files = [str(file) for file in files]
        assert len(files) == 0, "Files in temp dir: " + ", ".join(files)
