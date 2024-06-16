# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from .kde_cmake import BuildSystem_KDECMake

if TYPE_CHECKING:
    from ..build_context import BuildContext
    from ..module.module import Module


class BuildSystem_Qt6(BuildSystem_KDECMake):
    """
    Class responsible for building Qt6 CMake-based modules.
    """

    @staticmethod
    # @override
    def name() -> str:
        return "Qt6"

    # @override
    def prepare_module_build_environment(self, ctx: BuildContext, module: Module, prefix: str) -> None:
        # We're installing Qt6 modules, make sure our Qt directory matches our
        # install prefix so that environment variables are properly set.
        module.set_option({"qt-install-dir": prefix})
        return super().prepare_module_build_environment(ctx, module, prefix)
