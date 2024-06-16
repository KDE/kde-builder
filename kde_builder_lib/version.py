# SPDX-FileCopyrightText: 2012 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import subprocess


class Version:
    """
    This class is just a place to put the kde-builder version number
    in one spot, so it only needs changed in one place for a version bump.
    """

    # It is expected that future git tags will be in the form 'YY.MM' and will
    # be time-based instead of event-based as with previous releases.
    VERSION = "22.07"
    SCRIPT_PATH = ""  # For auto git-versioning
    SCRIPT_VERSION = VERSION

    @staticmethod
    def set_base_path(newPath: str) -> None:
        """
        Should be called before using ``script_version`` to set the base path for the
        script. This is needed to auto-detect the version in git for kde-builder
        instances running from a git repo.
        """
        Version.SCRIPT_PATH = newPath if newPath else Version.SCRIPT_PATH

    @staticmethod
    def script_version() -> str:
        """
        Call this function to return the kde-builder version.
        ::

            version = kde_builder_lib.Version.script_version()  # "22.07"

        If the script is running from within its git repository (and ``set_base_path`` has
        been called), this function will try to auto-detect the git SHA1 ID of the
        current checkout and append the ID (in ``git-describe`` format) to the output
        string as well.
        """
        can_run_git = subprocess.call("type " + "git", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
        if Version.SCRIPT_PATH and can_run_git and os.path.isdir(f"{Version.SCRIPT_PATH}/.git"):
            result = subprocess.run(['printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short=7 HEAD)"'], shell=True, capture_output=True, check=False, cwd=Version.SCRIPT_PATH)
            output = result.stdout.decode("utf-8").removesuffix("\n")
            ok = result.returncode == 0
            if ok and output:
                return f"{output}"
        return Version.SCRIPT_VERSION
