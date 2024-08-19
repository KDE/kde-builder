# SPDX-FileCopyrightText: 2012, 2017, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os.path
import re
import textwrap

from .build_system import BuildSystem
from ..debug import Debug
from ..debug import KBLogger
from ..util.util import Util

logger_buildsystem = KBLogger.getLogger("build-system")


class BuildSystemQt4(BuildSystem):
    """
    Build system for the Qt4 toolkit. It actually works for Qt6 qtbase as well because of how simple it is but don't tell anyone that.
    """

    # @override(check_signature=False)
    def needs_installed(self) -> bool:
        module = self.module
        return module.get_option("qt-install-dir") != module.fullpath("build")

    @staticmethod
    # @override
    def name() -> str:
        return "Qt"

    @staticmethod
    # @override
    def needs_builddir_hack() -> bool:
        return True

    # @override
    def configure_internal(self) -> bool:
        module = self.module
        srcdir = module.fullpath("source")
        script = f"{srcdir}/configure"

        if not os.path.exists(script) and not Debug().pretending():
            logger_buildsystem.error(f"\tMissing configure script for r[b[{module}]")
            return False

        commands = re.split(r"\s+", module.get_option("configure-flags"))
        commands.append("-confirm-license")
        commands.append("-opensource")

        # Get the user's CXXFLAGS
        cxxflags = module.get_option("cxxflags")
        module.queue_environment_variable("CXXFLAGS", cxxflags)

        prefix = module.get_option("qt-install-dir")

        if not prefix:
            logger_buildsystem.error(f"\tThe b[qt-install-dir] option must be set to determine where to install r[b[{module}]")
            return False

        # Some users have added -prefix manually to their flags, they
        # probably shouldn't anymore. :)

        if any(re.match(r"^-prefix(=.*)?$", command) for command in commands):
            logger_buildsystem.warning(textwrap.dedent(f"""\
                b[y[*]
                b[y[*] You have the y[-prefix] option selected in your {module} configure flags.
                b[y[*] kde-builder will correctly add the -prefix option to match your Qt
                b[y[*] directory setting, so you do not need to use -prefix yourself.
                b[y[*]
                """))

        commands.append("-prefix")
        commands.append(prefix)
        commands.insert(0, script)

        builddir = module.fullpath("build")
        old_flags = module.get_persistent_option("last-configure-flags") or ""
        cur_flags = Util.get_list_digest(commands)

        if cur_flags != old_flags or module.get_option("reconfigure") or not os.path.exists(f"{builddir}/Makefile"):
            logger_buildsystem.warning(f"\tb[r[LGPL license selected for Qt].  See {srcdir}/LICENSE.LGPL")
            logger_buildsystem.info("\tRunning g[configure]...")

            module.set_persistent_option("last-configure-flags", cur_flags)

            return Util.good_exitcode(Util.run_logged(module, "configure", builddir, commands))

        # Skip execution of configure.
        return True
