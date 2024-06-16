# SPDX-FileCopyrightText: 2019, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from .build_system import BuildSystem
from ..util.util import Util


class BuildSystemMeson(BuildSystem):
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
    def configure_internal(self) -> bool:
        """
        Return value style: boolean
        """
        module = self.module
        sourcedir = module.fullpath("source")
        builddir = module.fullpath("build")
        installdir = module.installation_path()

        # "module"-limited option grabbing can return None, so use Logical Defined-Or
        # to convert to empty string in that case.
        setup_options = Util.split_quoted_on_whitespace(module.get_option("configure-flags", "module") or "")

        exitcode = Util.run_logged(module, "meson-setup", sourcedir, ["meson", "setup", builddir, "--prefix", installdir, *setup_options])
        return Util.good_exitcode(exitcode)

    @staticmethod
    # @override
    def supports_auto_parallelism() -> bool:
        return True  # meson requires ninja so supports this by default

    # @override(check_signature=False)
    def build_internal(self) -> dict:
        return super().build_internal("ninja-options")

    @staticmethod
    # @override
    def build_commands() -> list[str]:
        return ["ninja"]

    @staticmethod
    # @override
    def required_programs() -> list[str]:
        return ["meson", "ninja"]

    @staticmethod
    # @override
    def configured_module_file_name() -> str:
        return "build.ninja"
