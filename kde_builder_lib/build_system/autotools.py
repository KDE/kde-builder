# SPDX-FileCopyrightText: 2012, 2016, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from .build_system import BuildSystem
from ..kb_exception import KBException
from ..kb_exception import KBRuntimeError
from ..debug import KBLogger
from ..util.util import Util

logger_buildsystem = KBLogger.getLogger("build-system")


class BuildSystemAutotools(BuildSystem):
    """
    Support configuring with autotools.

    This build system is currently only used for "gpgme" and "libgpg-error" modules. See `kde-builder --query build-system | grep autotools`.
    """

    @staticmethod
    # @override
    def name() -> str:
        return "autotools"

    def _autogen(self) -> str:
        """
        Run "autogen.sh" (if presented), and return "autogen.sh" or "configure" (depending on if "configure" is presented (after running "autogen.sh" or in repo)).
        """
        module = self.module
        sourcedir = module.fullpath("source")

        configure_in_file = next((item for item in ["configure.in", "configure.ac"] if os.path.exists(f"{sourcedir}/{item}")), None)

        # If we have a configure.in or configure.ac and autogen.sh exists,
        # we assume that configure is created by autogen.sh as usual in some GNU Projects.
        # So we run autogen.sh first to create the configure command.
        if configure_in_file and os.path.exists(f"{sourcedir}/autogen.sh"):
            exitcode = Util.run_logged(module, "autogen", sourcedir, [f"{sourcedir}/autogen.sh"])

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

        configure_command = next((item for item in ["configure", "autogen.sh"] if os.path.exists(f"{sourcedir}/{item}")), None)
        if not configure_command:
            raise KBRuntimeError("No configure command available")

        return configure_command

    # @override
    def configure_internal(self) -> bool:
        module = self.module
        sourcedir = module.fullpath("source")
        builddir = module.fullpath("build")
        installdir = module.installation_path()

        # "module"-limited option grabbing can return None, so use Logical Defined-Or
        # to convert to empty string in that case.
        bootstrap_options = Util.split_quoted_on_whitespace(module.get_option("configure-flags", "module") or "")
        try:
            configure_command = self._autogen()
            exitcode = Util.run_logged(module, "configure", builddir, [f"{sourcedir}/{configure_command}", f"--prefix={installdir}", *bootstrap_options])
            result = exitcode
        except KBException as err:
            logger_buildsystem.error(f"\tError configuring {module}: r[b[{err}]")
            return False

        return result == 0
