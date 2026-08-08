# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from .qmake6 import BuildSystemQMake6


class BuildSystemQMake5(BuildSystemQMake6):
    """
    The only difference is the possible qmake names and the identifier name of the build system.
    """

    possible_qmake_names = ["qmake-qt5", "qmake5", "qmake-mac", "qmake"]

    @staticmethod
    # @override
    def name() -> str:
        return "qmake"
