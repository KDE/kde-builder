# SPDX-FileCopyrightText: 2003 - 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2004 - 2024 KDE Contributors (see git history) <community@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

from typing import NoReturn
# from overrides import override

from .ModuleSet import ModuleSet
from ..BuildException import BuildException


class ModuleSet_Null(ModuleSet):
    """
    Used automatically by <Module> to represent the absence of a <ModuleSet> without
    requiring definedness checks.
    """

    def __init__(self):
        # No need to call parent __init__.
        pass
        self.name = ""  # pl2py: support returning name by not invoking the function. Needed for `wayland` module for example.

    # @override
    def name(self) -> str:
        return ""

    @staticmethod
    # @override(check_signature=False)
    def convertToModules(*_) -> NoReturn:
        BuildException.croak_internal("kde-builder should not have made it to this call. :-(")
