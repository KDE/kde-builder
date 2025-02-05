# SPDX-FileCopyrightText: 2019, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from ..debug import KBLogger
from .build_system import BuildSystem
from ..util.util import Util


logger_buildsystem = KBLogger.getLogger("build-system")


class BuildSystemMeson(BuildSystem):
    """
    Build system used to support configuring with Meson (https://mesonbuild.com).

    Note that Meson requires Ninja as its underlying build system so anything dealing with Meson
    can assume Ninja support is present.

    Control the flags passed to Meson's setup step using the ``meson-options`` option.
    """

    @staticmethod
    # @override
    def name() -> str:
        return "meson"

    # @override
    def configure_internal(self) -> bool:
        module = self.module
        sourcedir = module.fullpath("source")
        builddir = module.fullpath("build")
        installdir = module.installation_path()

        setup_options = Util.split_quoted_on_whitespace(module.get_option("meson-options"))

        exitcode = Util.run_logged(module, "meson-setup", sourcedir, ["meson", "setup", builddir, "--prefix", installdir, *setup_options])
        return Util.good_exitcode(exitcode)

    @staticmethod
    # @override
    def supports_auto_parallelism() -> bool:
        return True  # meson requires ninja so supports this by default

    # @override
    def build_options_name(self) -> str:
        return "ninja-options"

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
