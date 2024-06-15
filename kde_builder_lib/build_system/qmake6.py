# SPDX-FileCopyrightText: 2012, 2017, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import glob
import re

from .build_system import BuildSystem
from ..build_exception import BuildException
from ..debug import Debug
from ..debug import kbLogger
from ..util.util import Util

logger_buildsystem = kbLogger.getLogger("build-system")


class BuildSystem_QMake6(BuildSystem):
    """
    A build system used to build modules that use qmake
    """

    possible_qmake_names = ["qmake-qt6", "qmake6", "qmake-mac", "qmake"]

    @staticmethod
    # @override
    def name() -> str:
        return "qmake6"

    @staticmethod
    # @override
    def requiredPrograms() -> list[str]:
        return ["qmake"]

    # @override(check_signature=False)
    def needsBuilddirHack(self) -> bool:
        """
        I've never had problems with modern QMake-using modules being built in a
        specific build directory, until I tried using QMake to build Qt5 modules
        (past qtbase).  Many seem fail with builddir != srcdir
        """
        module = self.module

        # Assume code.qt.io modules all need hack for now
        return bool(re.search(r"qt\.io", module.getOption("repository")))

    @classmethod
    def absPathToQMake(cls) -> str:
        """
        Returns the absolute path to "qmake". Note the actual executable name may
        not necessarily be "qmake" as some distributions rename it to allow for
        co-installability with previous Qt versions.
        If no suitable qmake can be found, None is returned.
        """
        return next((p for p in cls.possible_qmake_names if Util.locate_exe(p)), None)

    # @override
    def configureInternal(self) -> bool:
        """
        Return value style: boolean
        """
        module = self.module
        builddir = module.fullpath("build")
        sourcedir = builddir if self.needsBuilddirHack() else module.fullpath("source")

        qmakeOpts = module.getOption("qmake-options").split(" ")
        qmakeOpts = [el for el in qmakeOpts if el != ""]  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it.
        projectFiles = glob.glob(f"{sourcedir}/*.pro")

        if not projectFiles and Debug().pretending():
            projectFiles = [f"{module}.pro"]

        if not projectFiles or not projectFiles[0]:
            BuildException.croak_internal(f"No *.pro files could be found for {module}")

        if len(projectFiles) > 1:
            logger_buildsystem.error(f" b[r[*] Too many possible *.pro files for {module}")
            return False

        qmake = self.absPathToQMake()

        if not qmake:
            return False

        logger_buildsystem.info("\tRunning g[qmake]...")

        return Util.good_exitcode(Util.run_logged(module, "qmake", builddir, [qmake, *qmakeOpts, projectFiles[0]]))
