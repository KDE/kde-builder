# SPDX-FileCopyrightText: 2018, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import re
import subprocess
import sys

from .build_exception import BuildException


class OSSupport:
    """
    Provides support code for handling distro-specific functionality, such as lists
    of package dependencies, command lines to update packages in the first place,
    and so on.

    See https://www.freedesktop.org/software/systemd/man/os-release.html for the
    relevant specification.

    Example:
    ::

        os = OSSupport()  # Autodetects info on running system
        print("Current OS is: " + os.vendor_id)
    """

    def __init__(self, file: str | None = None):
        """
            os = OSSupport()

        Manually point to os-release:
        ::

            os = OSSupport('/usr/lib/os-release')
        """

        self.ID = None
        self.ID_LIKE = None
        self.VERSION_CODENAME = None
        self.VERSION_ID = None

        # file might be None
        kv_list_ref = self._read_os_release(file)
        for key in kv_list_ref.keys():
            setattr(self, key, kv_list_ref[key])

    def vendor_id(self) -> str:
        """
        Returns the vendor ID from the `os-release` specification, or
        "unknown" if /etc/os-release could not be read.
        ::

            vendor = os.vendor_id  # "gentoo", "debian", etc.
        N.B., this is **not the same as the operating system**!
        """
        return self.ID or "unknown"

    def vendor_version(self) -> str:
        """
            vendor = os.vendor_version  # "xenial", "17", etc.

        Returns the vendor Version from the `os-release` specification.
        The first available value from `VERSION_ID` and then
        `VERSION_CODENAME` is used, and 'unknown' is returned if neither
        are set.
        """
        if self.VERSION_ID:
            return self.VERSION_ID
        elif self.VERSION_CODENAME:
            return self.VERSION_CODENAME
        else:
            return "unknown"

    def is_debian_based(self) -> bool:
        """
        Returns boolean. 1 (true) if this is a Linux distribution based on Debian, 0 (false) otherwise.
        """

        if self.ID == "debian":
            return True

        like_distros = self.ID_LIKE or ""
        if like_distros:
            like_distros_list = like_distros.split(" ")
            if "debian" in like_distros_list:
                return True
        return False

    def detect_total_memory(self) -> int:
        """
        Returns the amount of installed memory, in kilobytes. Linux and FreeBSD are
        supported.
        Throws a runtime exception if unable to autodetect memory capacity.
            mem_total_KiB = os.detect_total_memory()
        """
        mem_total = None
        if sys.platform == "freebsd":
            mem_total = subprocess.check_output(["sysctl", "-n", "hw.physmem"]).decode().strip()
            # FreeBSD reports memory in Bytes, not KiB. Convert to KiB so logic
            # below still works
            mem_total = int(float(mem_total) / 1024)
        elif sys.platform == "linux" or os.path.exists("/proc/meminfo"):
            # linux or potentially linux-compatible
            p = subprocess.run("cat /proc/meminfo", shell=True, capture_output=True)
            total_mem_line = next(line for line in p.stdout.decode().split("\n") if "MemTotal" in line)

            if total_mem_line and p.returncode == 0:
                mem_total = re.search(r"^MemTotal:\s*([0-9]+)", total_mem_line).group(1)  # Value in KiB
                mem_total = int(mem_total)
        else:
            BuildException.croak_runtime(f"Unable to detect total memory. OS: {sys.platform}, detected vendor: {self.vendor_id()}")

        return mem_total

    def best_distro_match(self, distros: list[str]) -> str:
        """
            # Might return "fedora" if running on Scientific Linux
            distro = os.best_distro_match(["ubuntu", "fedora", "arch", "debian"]);

        This uses the ID (and if needed, ID_LIKE) parameter in
        /etc/os-release to find the best possible match amongst the
        provided distro IDs. The list of distros should be ordered with
        most specific distro first.

        If no match is found, returns a generic os string (**not** None, "", or
        similar): "linux" or "freebsd" as the case may be.
        """

        ids = [self.vendor_id()]
        like_distros = self.ID_LIKE or ""
        if like_distros:
            for likeDistro in like_distros.split(" "):
                ids.append(likeDistro)

        for an_id in ids:
            if any(an_id == distro for distro in distros):
                return an_id

        # Special cases that aren't linux
        if ids[0] == "freebsd":
            return ids[0]
        # .. everything else is generic linux
        return "linux"

    @staticmethod
    def _read_os_release(file_name: str | None) -> dict:
        files = [file_name] if file_name else ["/etc/os-release", "/usr/lib/os-release", "/usr/local/etc/os-release"]
        file = None
        error = None

        while files:
            f = files.pop(0)
            if os.path.exists(f):
                file = f
                break

        if not file:
            return {}

        lines = None
        with open(file, "r") as fh:
            # skip comments and blank lines, and whitespace-only lines
            lines = [line.strip() for line in fh.readlines() if line.strip() and not line.strip().startswith("#")]

        result = {}
        for line in lines:
            key, value = line.split("=")
            value = backslash_decode(value.removeprefix("\"").removesuffix("\""))  # possibly also quoted in single quotes
            result[key] = value
        return result


def backslash_decode(src):
    """decode backslash-escapes"""
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
            if char == '"':
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
