# SPDX-FileCopyrightText: 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from pathlib import Path
import tempfile

from kde_builder_lib.build_context import BuildContext
from kde_builder_lib.util.util import Util


def test_prune_under_dir():
    """
    Test prune_under_directory_p, including ability to remove read-only files in subtree.
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
    ctx.set_option("log-dir", os.path.abspath(tmpdir))
    Util.prune_under_directory(ctx, os.path.abspath(tmpdir))

    assert not os.path.exists(file), "Known read-only file removed"

    files = list(Path(tmpdir).rglob("*"))
    if len(files) == 0:
        assert len(files) == 0, f"entire directory {tmpdir} removed"
    else:
        files = [str(file) for file in files]
        assert len(files) == 0, "Files in temp dir: " + ", ".join(files)
