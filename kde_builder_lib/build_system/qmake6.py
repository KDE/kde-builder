# SPDX-FileCopyrightText: 2012, 2017, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import glob
import re

from .build_system import BuildSystem
from ..kb_exception import ProgramError
from ..debug import Debug
from ..debug import KBLogger
from ..util.util import Util

logger_buildsystem = KBLogger.getLogger("build-system")


class BuildSystemQMake6(BuildSystem):
    """
    A build system used to build modules that use qmake.
    """

    possible_qmake_names = ["qmake-qt6", "qmake6", "qmake-mac", "qmake"]

    @staticmethod
    # @override
    def name() -> str:
        return "qmake6"

    @staticmethod
    # @override
    def required_programs() -> list[str]:
        return ["qmake"]

    @classmethod
    def abs_path_to_qmake(cls) -> str:
        """
        Return the absolute path to "qmake".

        Note the actual executable name may
        not necessarily be "qmake" as some distributions rename it to allow for
        co-installability with previous Qt versions.
        If no suitable qmake can be found, None is returned.
        """
        return next((p for p in cls.possible_qmake_names if Util.locate_exe(p)), None)

    # @override
    def configure_internal(self) -> bool:
        module = self.module
        builddir = module.fullpath("build")
        sourcedir = module.fullpath("source")

        qmake_opts = module.get_option("qmake-options").split(" ")
        qmake_opts = [el for el in qmake_opts if el != ""]  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it.
        project_files = glob.glob(f"{sourcedir}/*.pro")

        if not project_files and Debug().pretending():
            project_files = [f"{module}.pro"]

        if not project_files or not project_files[0]:
            raise ProgramError(f"No *.pro files could be found for {module}")

        if len(project_files) > 1:
            logger_buildsystem.error(f" b[r[*] Too many possible *.pro files for {module}")
            return False

        qmake = self.abs_path_to_qmake()

        if not qmake:
            return False

        logger_buildsystem.info("\tRunning g[qmake]...")

        return Util.good_exitcode(Util.run_logged(module, "qmake", builddir, [qmake, *qmake_opts, project_files[0]]))
