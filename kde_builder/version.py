# SPDX-FileCopyrightText: 2012 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from importlib.metadata import version, PackageNotFoundError
import os
import subprocess
from typing import NoReturn

from kde_builder import KB_REPO_DIR
from kde_builder.debug import KBLogger

logger_app = KBLogger.getLogger("application")


class Version:
    """
    A place to put the kde-builder version number in one spot, so it only needs changed in one place for a version bump.
    """

    @staticmethod
    def script_version() -> str:
        """
        Call this function to return the kde-builder version.

        If the script is running from within its git repository (and ``set_base_path`` has
        been called), this function will try to auto-detect the git SHA1 ID of the
        current checkout and append the ID (in ``git-describe`` format) to the output
        string as well.
        """
        try:
            current_version = version("kde-builder")
            return current_version
        except PackageNotFoundError:
            can_run_git = subprocess.call("type " + "git", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
            if KB_REPO_DIR and can_run_git and os.path.isdir(f"{KB_REPO_DIR}/.git"):
                result = subprocess.run(['printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short=7 HEAD)"'], shell=True, capture_output=True, check=False, cwd=KB_REPO_DIR)
                output = result.stdout.decode("utf-8").removesuffix("\n")
                ok = result.returncode == 0
                if ok and output:
                    return f"{output}"
            return "Unknown version"

    @staticmethod
    def self_update() -> NoReturn:
        logger_app.info("b[*] Running g[git pull] in the " + KB_REPO_DIR)
        subprocess.run("git pull", shell=True, cwd=KB_REPO_DIR)
        exit()

    @staticmethod
    def check_for_updates() -> None:
        logger_app.info("\n b[*] Checking for kde-builder updates.")
        subprocess.run("git fetch origin master:refs/remotes/origin/master", shell=True, cwd=KB_REPO_DIR)
        local_master_head = subprocess.run("git rev-parse --short=7 refs/heads/master", shell=True, capture_output=True, check=False, cwd=KB_REPO_DIR).stdout.decode("utf-8").removesuffix("\n")
        remote_master_head = subprocess.run("git rev-parse --short=7 refs/remotes/origin/master", shell=True, capture_output=True, check=False, cwd=KB_REPO_DIR).stdout.decode("utf-8").removesuffix("\n")

        if local_master_head != remote_master_head:
            logger_app.warning(" y[*] Your kde-builder version seems to be outdated. To update, run y[kde-builder --self-update].")
        else:
            logger_app.info(" g[*] Your kde-builder version is up-to-date.")
