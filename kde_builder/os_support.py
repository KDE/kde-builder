# SPDX-FileCopyrightText: 2018, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import logging
import os

logger_app = logging.getLogger("application")


class OSSupport:
    """
    Provides support code for handling distro-specific functionality, such as lists, of package dependencies, command lines to update packages in the first place, and so on.

    See https://www.freedesktop.org/software/systemd/man/os-release.html for the
    relevant specification.

    Example:
    ::

        os = OSSupport()  # Autodetects info on running system
        print("Current OS is: " + os.vendor_id)
    """

    def __init__(self, os_release_file: str = "") -> None:
        """
        Initialize OSSupport.

        Args:
            os_release_file: Force use specific os-release file path instead of relying on default location.
        """
        self.ID = "unknown"
        """Just initial value. Intended to be overridden."""

        self.ID_LIKE = ""
        """Just initial value. Can be overridden."""

        self.VERSION_ID = "unknown"
        """Just initial value. Can be overridden."""

        kv_list = self._read_os_release(os_release_file)
        for key in kv_list.keys():
            setattr(self, key, kv_list[key])

        self.supported_os_ids = ["alpine", "arch", "debian", "fedora", "gentoo", "mageia", "opensuse"] + ["freebsd", "openbsd"]
        self.best_distro_match = self._find_best_distro_match()

    def is_based_on(self, id_str: str) -> bool:
        """
        Return true if passed id_str matches ID or is contained in ID_LIKE of /etc/os-release.
        """
        if self.ID == id_str:
            return True

        like_distros = self.ID_LIKE
        if like_distros:
            like_distros_list = like_distros.split(" ")
            if id_str in like_distros_list:
                return True
        return False

    def _find_best_distro_match(self) -> str:
        """
        Use the ID (and if needed, ID_LIKE) parameter in /etc/os-release to find the best possible match amongst the provided distro IDs.

        The list of distros should be ordered with most specific distro first.

            # Might return "fedora" if running on Scientific Linux
            os.supported_os_ids = ["ubuntu", "fedora", "arch", "debian"]
            distro = os._find_best_distro_match()

        If no match is found, returns a generic os string (**not** None, "", or similar): "linux" or "freebsd" as the case may be.
        """
        supported_distro_ids: list[str] = self.supported_os_ids
        user_os_id_and_like_ids = [self.ID]
        like_distros = self.ID_LIKE
        if like_distros:
            for like_distro in like_distros.split(" "):
                user_os_id_and_like_ids.append(like_distro)

        for user_os_id_or_like_id in user_os_id_and_like_ids:
            if any(user_os_id_or_like_id == supported_distro_id for supported_distro_id in supported_distro_ids):
                return user_os_id_or_like_id

        return "unknown"

    @staticmethod
    def _read_os_release(path_to_file: str = "") -> dict[str, str]:
        select_from_files = [path_to_file] if path_to_file else ["/etc/os-release", "/usr/lib/os-release", "/usr/local/etc/os-release"]
        selected_file = ""

        while select_from_files:
            f = select_from_files.pop(0)
            if os.path.exists(f):
                selected_file = f
                break

        if not selected_file:
            return {}

        lines = None
        with open(selected_file, "r") as fh:
            # skip comments and blank lines, and whitespace-only lines
            lines = [line.strip() for line in fh.readlines() if line.strip() and not line.strip().startswith("#")]

        result = {}
        for line in lines:
            key, value = line.split("=", maxsplit=1)
            value = backslash_decode(value.removeprefix("\"").removesuffix("\""))  # possibly also quoted in single quotes
            result[key] = value
        return result


def backslash_decode(src):
    """
    Decode backslash-escapes.
    """
    slashes = 0  # count backslashes
    dst = ""
    for loc in range(0, len(src)):
        char = src[loc]
        if char == "\\":
            slashes += 1
            if slashes == 2:
                dst += char  # decode backslash
                slashes = 0
        elif slashes == 0:
            dst += char  # normal char
        else:  # slashes == 1
            if char == "\"":
                dst += char  # decode double-quote
            elif char == "'":
                dst += char  # decode single-quote
            elif char == "$":
                dst += char  # decode dollar-quote
            elif char == "`":
                dst += char  # decode backtick-quote
            else:
                dst += "\\" + char  # keep backslash-escapes like \n or \t
            slashes = 0
    return dst
