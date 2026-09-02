# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass
class Option:
    """
    Single option specification.
    """

    name: str
    default: Any
    aliases: list[str] = field(default_factory=list)

    def dashed(self) -> list[str]:
        parts = [self.name, *self.aliases]
        dashed_parts = []
        for part in parts:
            if len(part) == 1:
                dashed_parts.append("-" + part)
            else:
                dashed_parts.append("--" + part)
        return dashed_parts


class OptionsSpec:
    """
    Options specification.

    Determines option names, their description and default values.
    """

    # There doesn't seem to be a great way to get this from CMake easily, but we can
    # reason that if there is a /usr/lib64 (and it's not just a compat symlink),
    # there will likely end up being a ${install-dir}/lib64 once kde-builder gets
    # done installing it
    libname = "lib"
    if os.path.isdir("/usr/lib64") and not os.path.islink("/usr/lib64"):
        libname = "lib64"
    if os.path.isdir("/usr/lib/x86_64-linux-gnu"):
        libname = "lib/x86_64-linux-gnu"

    # These options are exposed as cmdline options without parameters
    global_options_without_parameter = [
        Option(name="build-system-only", default=""),
        Option(name="reconfigure", default=""),
        Option(name="refresh-build", aliases=["r"], default=""),
        Option(name="refresh-build-first", default=""),
        Option(name="metadata-only", default=""),
        Option(name="pretend", aliases=["dry-run", "p"], default=""),
    ]

    # These options are exposed as cmdline options that require some parameter
    global_options_with_parameter = [
        Option(name="binpath", default=""),
        Option(name="branch", default=""),
        Option(name="branch-group", default="latest-kf6"),
        Option(name="build-dir", default=os.getenv("HOME") + "/kde/build"),
        Option(name="cmake-generator", default=""),
        Option(name="cmake-options", default=""),
        Option(name="configure-flags", default=""),
        Option(name="cxxflags", default="-pipe"),
        Option(name="directory-layout", default="flat"),
        Option(name="dest-dir", default="${MODULE}"),
        Option(name="git-user", default=""),
        Option(name="install-dir", default=os.getenv("HOME") + "/kde/usr"),
        Option(name="libname", default=libname),
        Option(name="libpath", default=""),
        Option(name="log-dir", default=os.getenv("HOME") + "/kde/log"),
        Option(name="make-install-prefix", default=""),  # Some people need sudo
        Option(name="make-options", default=""),
        Option(name="meson-options", default=""),
        Option(name="niceness", aliases=["nice"], default=10),
        Option(name="ninja-options", default=""),
        Option(name="num-cores", default=""),  # Used for build constraints
        Option(name="num-cores-low-mem", default="2"),  # Needs to be a string, not int
        Option(name="override-build-system", default=""),
        Option(name="persistent-data-file", default=""),
        Option(name="qmake-options", default=""),
        Option(name="qt-install-dir", default=""),
        Option(name="remove-after-install", default="none"),  # { none, builddir, all }
        Option(name="revision", default=""),
        Option(name="source-dir", default=os.getenv("HOME") + "/kde/src"),
        Option(name="source-when-start-program", default="/dev/null"),
        Option(name="tag", default=""),
        Option(name="taskset-cpu-list", default=""),
    ]

    # These options are exposed as cmdline options without parameters, and having the negatable form with "--no-".
    global_options_with_negatable_form = [
        Option(name="async", default=True),
        Option(name="check-self-updates", default=True),
        Option(name="colorful-output", aliases=["color"], default=True),
        Option(name="compile-commands-export", default=True),
        Option(name="compile-commands-linking", default=True),
        Option(name="generate-clion-project-config", default=False),
        Option(name="generate-vscode-project-config", default=False),
        Option(name="generate-qtcreator-project-config", default=False),
        Option(name="hold-performance-profile", default=True),
        Option(name="hold-work-branches", default=True),
        Option(name="include-dependencies", default=True),
        Option(name="install-login-session", default=True),
        Option(name="purge-old-logs", default=True),
        Option(name="run-tests", default=False),
        Option(name="stop-on-failure", default=True),
        Option(name="use-clean-install", default=False),
        Option(name="use-idle-io-priority", default=False),
    ]

    # These options are exposed as cmdline options, but handled differently.
    global_options_with_extra_specifier = [
        Option(name="ignore-projects", aliases=["!"], default=""),
        Option(name="targets", default={}),
    ]

    @classmethod
    def all_global_options(cls) -> dict[str, Option]:
        ret = {}
        for option in cls.global_options_without_parameter:
            ret[option.name] = option
        for option in cls.global_options_with_parameter:
            ret[option.name] = option
        for option in cls.global_options_with_negatable_form:
            ret[option.name] = option
        for option in cls.global_options_with_extra_specifier:
            ret[option.name] = option
        return ret

    @classmethod
    def all_global_options_defaults(cls) -> dict[str, Any]:
        ret = {}
        for option in cls.global_options_without_parameter:
            ret[option.name] = option.default
        for option in cls.global_options_with_parameter:
            ret[option.name] = option.default
        for option in cls.global_options_with_negatable_form:
            ret[option.name] = option.default
        for option in cls.global_options_with_extra_specifier:
            ret[option.name] = option.default
        return ret
