# SPDX-FileCopyrightText: 2012, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# from overrides import override

from .BuildSystem import BuildSystem
from ..Util.Util import Util


class BuildSystem_CMakeBootstrap(BuildSystem):
    """
    This is a module used to do only one thing: Bootstrap CMake onto a system
    that doesn't have it, or has only an older version of it.
    """

    @staticmethod
    # @override
    def name() -> str:
        return "cmake-bootstrap"

    @staticmethod
    # @override
    def requiredPrograms() -> list[str]:
        return ["c++", "make"]

    # @override
    def configureInternal(self) -> bool:
        """
        Return value style: boolean
        """
        module = self.module
        sourcedir = module.fullpath("source")
        installdir = module.installationPath()

        # 'module'-limited option grabbing can return undef, so use //
        # to convert to empty string in that case.
        bootstrapOptions = Util.split_quoted_on_whitespace(module.getOption("configure-flags", "module") or "")

        builddir = module.fullpath("build")

        promise = Util.run_logged_p(module, "cmake-bootstrap", builddir, [f"{sourcedir}/bootstrap", f"--prefix={installdir}", *bootstrapOptions])

        return Util.await_exitcode(promise)
