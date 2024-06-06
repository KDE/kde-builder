# SPDX-FileCopyrightText: 2012, 2016, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
# from overrides import override

from .BuildSystem import BuildSystem
from ..Util.Util import Util
from ..Debug import Debug, kbLogger
from ..BuildException import BuildException

logger_buildsystem = kbLogger.getLogger("build-system")


class BuildSystem_Autotools(BuildSystem):
    """
    This is a class used to support configuring with autotools.
    """

    @staticmethod
    # @override
    def name() -> str:
        return "autotools"

    def _findConfigureCommands(self) -> str:
        """
        Returns the specific configure command to use.

        This may execute commands to re-run autoconf to generate the script.

        If these commands fail will raise exception.
        """
        module = self.module
        sourcedir = module.fullpath("source")

        configureCommand = next((item for item in ["configure", "autogen.sh"] if os.path.exists(f"{sourcedir}/{item}")), None)
        configureInFile = next((item for item in ["configure.in", "configure.ac"] if os.path.exists(f"{sourcedir}/{item}")), None)

        if configureCommand != "autogen.sh" and configureInFile:
            return configureCommand

        # If we have a configure.in or configure.ac but configureCommand is autogen.sh
        # we assume that configure is created by autogen.sh as usual in some GNU Projects.
        # So we run autogen.sh first to create the configure command and
        # recheck for that.
        if configureInFile and configureCommand == "autogen.sh":
            exitcode = Util.run_logged(module, "autogen", sourcedir, [f"{sourcedir}/{configureCommand}"])

            if exitcode != 0:
                print(f"Autogen failed with exit code {exitcode}")
                exit(1)

            # Cleanup any stray Makefiles that may be present, if generated
            if os.path.exists(f"{sourcedir}/Makefile"):
                exitcode = Util.run_logged(module, "distclean", sourcedir, ["make", "distclean"])
            else:
                # nothing to do, use successful exit code
                exitcode = 0

            if exitcode != 0:
                print(f"Failed to run make distclean, exit code {exitcode}")
                exit(1)

            # Now recheck
            configureCommand = next((item for item in ["configure", "autogen.sh"] if os.path.exists(f"{sourcedir}/{item}")), None)
            return configureCommand

        if not configureCommand:
            BuildException.croak_runtime("No configure command available")

        return configureCommand

    # @override
    def configureInternal(self) -> bool:
        """
        Return value style: boolean
        """
        module = self.module
        sourcedir = module.fullpath("source")
        builddir = module.fullpath("build")
        installdir = module.installationPath()

        # "module"-limited option grabbing can return None, so use Logical Defined-Or
        # to convert to empty string in that case.
        bootstrapOptions = Util.split_quoted_on_whitespace(module.getOption("configure-flags", "module") or "")
        try:
            configureCommand = self._findConfigureCommands()
            Util.p_chdir(module.fullpath("build"))
            exitcode = Util.run_logged(module, "configure", builddir, [f"{sourcedir}/{configureCommand}", f"--prefix={installdir}", *bootstrapOptions])
            result = exitcode
        except BuildException as err:
            logger_buildsystem.error(f"\tError configuring {module}: r[b[{err}]")
            return False

        return result == 0
