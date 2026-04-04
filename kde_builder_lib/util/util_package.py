# SPDX-FileCopyrightText: 2026 Benjamin Port <benjamin.port@kde.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import site
import sys

if sys.version_info >= (3, 11):
    from importlib.resources.abc import Traversable
else:
    from importlib.abc import Traversable
from importlib.resources import files

from pathlib import Path


def is_installed_as_package():
    resolved = Path(__file__).resolve()
    site_dirs = site.getsitepackages() + [site.getusersitepackages()]
    return any(resolved.is_relative_to(Path(d).resolve()) for d in site_dirs)


def data_file_path(relative_path: str) -> Traversable | Path:
    if is_installed_as_package():
        return files("kde_builder_lib.data") / relative_path

    return Path(__file__).resolve().parent.parent.parent / "data" / relative_path
