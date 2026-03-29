# SPDX-FileCopyrightText: 2026 Benjamin Port <benjamin.port@kde.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
import sys

if sys.version_info >= (3, 11):
    from importlib.resources.abc import Traversable
else:
    from importlib.abc import Traversable
from pathlib import Path

from importlib.resources import files

def data_file_path(relative_path: str) -> Traversable | Path:
    try:
        return files("kde_builder_lib.data") / relative_path
    except ModuleNotFoundError:
        return Path(__file__).resolve().parent.parent.parent / "data" / relative_path
