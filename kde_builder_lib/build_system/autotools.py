# SPDX-FileCopyrightText: 2012, 2016, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from .build_system import BuildSystem
from ..build_exception import BuildException
from ..debug import KBLogger
from ..util.util import Util

logger_buildsystem = KBLogger.getLogger("build-system")


class BuildSystemAutotools(BuildSystem):
    """
    This is a class used to support configuring with autotools.
    """

    @staticmethod
    # @override
    def name() -> str:
        return "autotools"

    def _find_configure_commands(self) -> str:
        """
        Returns the specific configure command to use.

        This may execute commands to re-run autoconf to generate the script.

        If these commands fail will raise exception.
        """
        module = self.module
        sourcedir = module.fullpath("source")

        configure_command = next((item for item in ["configure", "autogen.sh"] if os.path.exists(f"{sourcedir}/{item}")), None)
        configure_in_file = next((item for item in ["configure.in", "configure.ac"] if os.path.exists(f"{sourcedir}/{item}")), None)

        if configure_command != "autogen.sh" and configure_in_file:
            return configure_command

        # If we have a configure.in or configure.ac but configure_command is autogen.sh
        # we assume that configure is created by autogen.sh as usual in some GNU Projects.
        # So we run autogen.sh first to create the configure command and
        # recheck for that.
        if configure_in_file and configure_command == "autogen.sh":
            exitcode = Util.run_logged(module, "autogen", sourcedir, [f"{sourcedir}/{configure_command}"])

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
            configure_command = next((item for item in ["configure", "autogen.sh"] if os.path.exists(f"{sourcedir}/{item}")), None)
            return configure_command

        if not configure_command:
            BuildException.croak_runtime("No configure command available")

        return configure_command

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
        bootstrap_options = Util.split_quoted_on_whitespace(module.get_option("configure-flags", "module") or "")
        try:
            configure_command = self._find_configure_commands()
            exitcode = Util.run_logged(module, "configure", builddir, [f"{sourcedir}/{configure_command}", f"--prefix={installdir}", *bootstrap_options])
            result = exitcode
        except BuildException as err:
            logger_buildsystem.error(f"\tError configuring {module}: r[b[{err}]")
            return False

        return result == 0
