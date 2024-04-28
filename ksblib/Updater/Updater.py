# SPDX-FileCopyrightText: 2012 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

from typing import NoReturn

from ..BuildException import BuildException


class Updater:
    """
    Base class for classes that handle updating the source code for a given
    L<ksb::Module>.  It should not be used directly.
    """

    def __init__(self, module):
        self.module = module

    @staticmethod
    def name() -> NoReturn:
        BuildException.croak_internal("This package should not be used directly.")

    def module(self):
        return self.module
