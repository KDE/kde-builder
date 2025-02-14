# SPDX-FileCopyrightText: 2018, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import re
import subprocess
import sys

from .debug import KBLogger
from .kb_exception import KBRuntimeError

logger_app = KBLogger.getLogger("application")


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

    def __init__(self, file: str | None = None):
        """
        Initialize OSSupport.

            os = OSSupport()

        Manually point to os-release:
        ::

            os = OSSupport("/usr/lib/os-release")
        """
        self.ID = "unknown"  # ID from the `os-release` specification. "gentoo", "debian", etc.
        self.ID_LIKE = None
        self.VERSION_CODENAME = None
        self.VERSION_ID = None

        # file might be None
        kv_list = self._read_os_release(file)
        for key in kv_list.keys():
            setattr(self, key, kv_list[key])

    def vendor_version(self) -> str:
        """
        Returns the vendor Version from the `os-release` specification.

        The first available value from `VERSION_ID` and then `VERSION_CODENAME` is used, and "unknown" is returned if neither are set.

            vendor = os.vendor_version()  # "xenial", "17", etc.
        """
        if self.VERSION_ID:
            return self.VERSION_ID
        elif self.VERSION_CODENAME:
            return self.VERSION_CODENAME
        else:
            return "unknown"

    def is_based_on(self, id_str: str) -> bool:
        """
        Return true if passed id_str matches ID or is contained in ID_LIKE of /etc/os-release.
        """
        if self.ID == id_str:
            return True

        like_distros = self.ID_LIKE or ""
        if like_distros:
            like_distros_list = like_distros.split(" ")
            if id_str in like_distros_list:
                return True
        return False

    def best_distro_match(self, distros: list[str]) -> str:
        """
        Use the ID (and if needed, ID_LIKE) parameter in /etc/os-release to find the best possible match amongst the provided distro IDs.

        The list of distros should be ordered with most specific distro first.

            # Might return "fedora" if running on Scientific Linux
            distro = os.best_distro_match(["ubuntu", "fedora", "arch", "debian"]);

        If no match is found, returns a generic os string (**not** None, "", or
        similar): "linux" or "freebsd" as the case may be.
        """
        ids = [self.ID]
        like_distros = self.ID_LIKE or ""
        if like_distros:
            for like_distro in like_distros.split(" "):
                ids.append(like_distro)

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
            key, value = line.split("=", maxsplit=1)
            value = backslash_decode(value.removeprefix("\"").removesuffix("\""))  # possibly also quoted in single quotes
            result[key] = value
        return result


class CoresAndMemorySupport:
    """
    Provides support code for detecting available CPU cores/memory.
    """

    @staticmethod
    def _detect_total_memory() -> int:
        """
        Return the amount of installed memory, in kilobytes. Linux and FreeBSD are supported.

        Throws a runtime exception if unable to autodetect memory capacity.
            mem_total_KiB = c_and_m_sup.detect_total_memory()
        """
        mem_total = None
        if sys.platform.startswith("freebsd") or sys.platform.startswith("openbsd"):
            mem_total = subprocess.check_output(["sysctl", "-n", "hw.physmem"]).decode().strip()
            # FreeBSD, OpenBSD reports memory in Bytes, not KiB. Convert to KiB so logic below still works
            mem_total = int(float(mem_total) / 1024)
        elif sys.platform == "linux" or os.path.exists("/proc/meminfo"):
            # linux or potentially linux-compatible
            p = subprocess.run("cat /proc/meminfo", shell=True, capture_output=True)
            total_mem_line = next(line for line in p.stdout.decode().split("\n") if "MemTotal" in line)

            if total_mem_line and p.returncode == 0:
                mem_total = re.search(r"^MemTotal:\s*([0-9]+)", total_mem_line).group(1)  # Value in KiB
                mem_total = int(mem_total)
        else:
            raise KBRuntimeError(f"Unable to detect total memory. OS: {sys.platform}")

        return mem_total

    @staticmethod
    def _suggested_num_cores_for_low_memory() -> int:
        """
        Return the suggested number of cores to use for make jobs for build jobs where memory is a bottleneck, such as qtwebengine.

            num_cores = FirstRun.suggested_num_cores_for_low_memory()
        """
        # Try to detect the amount of total memory for a corresponding option for
        # heavyweight modules
        mem_total = None
        try:
            mem_total = CoresAndMemorySupport._detect_total_memory()
        except KBRuntimeError as e:
            logger_app.warning(str(e))

        if not mem_total:
            # 4 GiB is assumed if no info on memory is available, as this will calculate to 2 cores.
            mem_total = 4 * 1024 * 1024
            logger_app.warning(f"y[*] Will assume the total memory amount is {mem_total} bytes.")

        rounded_mem = int(mem_total / 1024000.0)
        return max(1, int(rounded_mem / 2))  # Assume 2 GiB per core

    @staticmethod
    def get_num_cores_for_low_memory() -> int:
        """
        Return the highest number of cores we can use based on available memory, but without exceeding the base number of cores available.
        """
        num_cores = os.cpu_count() or 4
        return min(CoresAndMemorySupport._suggested_num_cores_for_low_memory(), num_cores)


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
