# SPDX-FileCopyrightText: 2012, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from .build_system import BuildSystem
from ..util.util import Util


class BuildSystemCMakeBootstrap(BuildSystem):
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
    def required_programs() -> list[str]:
        return ["c++", "make"]

    # @override
    def configure_internal(self) -> bool:
        """
        Return value style: boolean
        """
        module = self.module
        sourcedir = module.fullpath("source")
        installdir = module.installation_path()

        # "module"-limited option grabbing can return None, so use Logical Defined-Or
        # to convert to empty string in that case.
        bootstrap_options = Util.split_quoted_on_whitespace(module.get_option("configure-flags", "module") or "")

        builddir = module.fullpath("build")

        exitcode = Util.run_logged(module, "cmake-bootstrap", builddir, [f"{sourcedir}/bootstrap", f"--prefix={installdir}", *bootstrap_options])
        return Util.good_exitcode(exitcode)
