# SPDX-FileCopyrightText: 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from typing import NoReturn

from .module_set import ModuleSet
from ..kb_exception import ProgramError


class ModuleSetNull(ModuleSet):
    """
    Used automatically by ``Module`` to represent the absence of a ``ModuleSet`` without requiring definedness checks.
    """

    def __init__(self):
        # No need to call parent __init__.
        pass
        self.name = ""

    @staticmethod
    # @override(check_signature=False)
    def convert_to_modules(*_) -> NoReturn:
        raise ProgramError("kde-builder should not have made it to this call. :-(")
