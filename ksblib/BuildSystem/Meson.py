# SPDX-FileCopyrightText: 2019, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# from overrides import override

from .BuildSystem import BuildSystem
# use ksb::BuildException;
# use ksb::Debug;
# use ksb::Util qw(:DEFAULT :await run_logged_p);
from ..Util.Util import Util


class BuildSystem_Meson(BuildSystem):
    """
    This is a build system used to support configuring with Meson (https://mesonbuild.com).

    Note that Meson requires Ninja as its underlying build system so anything dealing with Meson
    can assume Ninja support is present.

    Control the flags passed to Meson's setup step using the ``configure-flags`` option.
    """

    @staticmethod
    # @override
    def name() -> str:
        return "meson"

    # @override
    def configureInternal(self) -> bool:
        """
        Return value style: boolean
        """
        Util.assert_isa(self, BuildSystem_Meson)
        module = self.module
        sourcedir = module.fullpath("source")
        buildDir = module.fullpath("build")
        installdir = module.installationPath()

        # "module"-limited option grabbing can return None, so use Logical Defined-Or
        # to convert to empty string in that case.
        setupOptions = Util.split_quoted_on_whitespace(module.getOption("configure-flags", "module") or "")

        exitcode = Util.run_logged(module, "meson-setup", sourcedir, ["meson", "setup", buildDir, "--prefix", installdir, *setupOptions])
        return Util.good_exitcode(exitcode)

    @staticmethod
    # @override
    def supportsAutoParallelism() -> bool:
        return True  # meson requires ninja so supports this by default

    # @override(check_signature=False)
    def buildInternal(self) -> dict:
        return super().buildInternal("ninja-options")

    @staticmethod
    # @override
    def buildCommands() -> list[str]:
        return ["ninja"]

    @staticmethod
    # @override
    def requiredPrograms() -> list[str]:
        return ["meson", "ninja"]

    @staticmethod
    # @override
    def configuredModuleFileName() -> str:
        return "build.ninja"
