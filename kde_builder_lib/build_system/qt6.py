# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from .kde_cmake import BuildSystemKDECMake


class BuildSystemQt6(BuildSystemKDECMake):
    """
    Class responsible for building Qt6 CMake-based modules.
    """

    @staticmethod
    # @override
    def name() -> str:
        return "Qt6"

    # @override
    def prepare_module_build_environment(self) -> None:
        # We're installing Qt6 modules, make sure our Qt directory matches our
        # install prefix so that environment variables are properly set.
        module = self.module
        prefix = self.module.installation_path()
        module.set_option({"qt-install-dir": prefix})
        return super().prepare_module_build_environment()
