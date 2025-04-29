# SPDX-FileCopyrightText: 2019, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os.path
import re

from .build_system import BuildSystem
from ..debug import Debug
from ..debug import KBLogger
from ..util.util import Util
from ..util.textwrap_mod import textwrap

logger_buildsystem = KBLogger.getLogger("build-system")


class BuildSystemQt5(BuildSystem):
    """
    Build system for the Qt5 toolkit.
    """

    @staticmethod
    # @override
    def configured_module_file_name() -> str:
        return "Makefile"

    @staticmethod
    # @override
    def name() -> str:
        return "Qt5"

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
        commands.append("-nomake")
        commands.append("examples")
        commands.append("-nomake")
        commands.append("tests")

        # Get the user's CXXFLAGS
        cxxflags = module.get_option("cxxflags")
        module.queue_environment_variable("CXXFLAGS", cxxflags)

        installdir = module.get_option("install-dir")
        qt_installdir = module.get_option("qt-install-dir")

        if installdir and qt_installdir and installdir != qt_installdir:
            logger_buildsystem.warning(textwrap.dedent(f"""\
                b[y[*]
                b[y[*] Building the Qt module, but the install directory for Qt is not set to the
                b[y[*] Qt directory to use.
                b[y[*]   install directory ("install-dir" option): b[{installdir}]
                b[y[*]   Qt install to use ("qt-install-dir"  option): b[{qt_installdir}]
                b[y[*]
                b[y[*] Try setting b[qt-install-dir] to the same setting as the Qt module's b[install-dir].
                b[y[*]
                """))

        if not installdir:
            installdir = qt_installdir  # Use qt-install-dir for install if install-dir not set

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
        commands.append(installdir)
        commands.insert(0, script)

        builddir = module.fullpath("build")
        old_flags = module.get_persistent_option("last-configure-flags") or ""
        cur_flags = Util.get_list_digest(commands)

        if cur_flags == old_flags and not module.get_option("reconfigure") and os.path.exists(f"{builddir}/Makefile"):
            return True

        logger_buildsystem.warning(f"\tb[r[LGPL license selected for Qt].  See {srcdir}/LICENSE.LGPL")
        logger_buildsystem.info("\tRunning g[configure]...")

        module.set_persistent_option("last-configure-flags", cur_flags)

        return Util.good_exitcode(Util.run_logged(module, "configure", builddir, commands))
