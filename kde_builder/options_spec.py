# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from argparse import ArgumentParser
from dataclasses import dataclass
from dataclasses import field
from typing import Any


def add_bootstrap_arguments(parser: ArgumentParser) -> None:
    """
    We need to reuse that in the bootstrap parser, and in the cmd_line parser.

    This way we will be able to see bootstrap options in cmd_line parser.
    """
    parser.add_argument("--initial-setup", action="store_true", help="")
    parser.add_argument("--install-distro-packages", action="store_true", help="")
    parser.add_argument("--generate-config", action="store_true", help="")
    parser.add_argument("--prompt-answer", nargs=1, help="")
    parser.add_argument("--debug", action="store_true", help="")
    parser.add_argument("--log-level", type=lambda x: x.split("=", 2), action="append", help="")


@dataclass
class Option:
    """
    Single option specification.
    """

    name: str
    default: Any
    aliases: list[str] = field(default_factory=list)
    help: str = ""

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
        Option(name="build-system-only", default="", help=""),
        Option(name="reconfigure", default="", help=""),
        Option(name="refresh-build", aliases=["r"], default="", help=""),
        Option(name="refresh-build-first", default="", help=""),
        Option(name="metadata-only", default="", help=""),
        Option(name="pretend", aliases=["dry-run", "p"], default="", help=""),
    ]

    # These options are exposed as cmdline options that require some parameter
    global_options_with_parameter = [
        Option(name="binpath", default="", help=""),
        Option(name="branch", default="", help=""),
        Option(name="branch-group", default="latest-kf6", help=""),
        Option(name="build-dir", default=os.getenv("HOME") + "/kde/build", help=""),
        Option(name="cmake-generator", default="", help=""),
        Option(name="cmake-options", default="", help=""),
        Option(name="configure-flags", default="", help=""),
        Option(name="cxxflags", default="-pipe", help=""),
        Option(name="directory-layout", default="flat", help=""),
        Option(name="dest-dir", default="${MODULE}", help=""),
        Option(name="git-user", default="", help=""),
        Option(name="install-dir", default=os.getenv("HOME") + "/kde/usr", help=""),
        Option(name="libname", default=libname, help=""),
        Option(name="libpath", default="", help=""),
        Option(name="log-dir", default=os.getenv("HOME") + "/kde/log", help=""),
        Option(name="make-install-prefix", default="", help=""),  # Some people need sudo
        Option(name="make-options", default="", help=""),
        Option(name="meson-options", default="", help=""),
        Option(name="niceness", aliases=["nice"], default=10, help=""),
        Option(name="ninja-options", default="", help=""),
        Option(name="num-cores", default="", help=""),  # Used for build constraints
        Option(name="num-cores-low-mem", default="2", help=""),  # Needs to be a string, not int
        Option(name="override-build-system", default="", help=""),
        Option(name="persistent-data-file", default="", help=""),
        Option(name="qmake-options", default="", help=""),
        Option(name="qt-install-dir", default="", help=""),
        Option(name="remove-after-install", default="none", help=""),  # { none, builddir, all }
        Option(name="revision", default="", help=""),
        Option(name="source-dir", default=os.getenv("HOME") + "/kde/src", help=""),
        Option(name="source-when-start-program", default="/dev/null", help=""),
        Option(name="tag", default="", help=""),
        Option(name="taskset-cpu-list", default="", help=""),
    ]

    # These options are exposed as cmdline options without parameters, and having the negatable form with "--no-".
    global_options_with_negatable_form = [
        Option(name="async", default=True, help=""),
        Option(name="check-self-updates", default=True, help=""),
        Option(name="colorful-output", aliases=["color"], default=True, help=""),
        Option(name="compile-commands-export", default=True, help=""),
        Option(name="compile-commands-linking", default=True, help=""),
        Option(name="generate-clion-project-config", default=False, help=""),
        Option(name="generate-vscode-project-config", default=False, help=""),
        Option(name="generate-qtcreator-project-config", default=False, help=""),
        Option(name="hold-performance-profile", default=True, help=""),
        Option(name="hold-work-branches", default=True, help=""),
        Option(name="include-dependencies", default=True, help=""),
        Option(name="install-login-session", default=True, help=""),
        Option(name="purge-old-logs", default=True, help=""),
        Option(name="run-tests", default=False, help=""),
        Option(name="stop-on-failure", default=True, help=""),
        Option(name="use-clean-install", default=False, help=""),
        Option(name="use-idle-io-priority", default=False, help=""),
    ]

    # These options are exposed as cmdline options, but handled differently.
    global_options_with_extra_specifier = [
        Option(name="ignore-projects", aliases=["!"], default="", help=""),
        Option(name="targets", default={}, help=""),
    ]

    # These options are used for internal state, they are _not_ exposed as cmdline options
    global_options_private = [
        Option(name="build-configs-dir", default=os.environ.get("XDG_STATE_HOME", os.environ["HOME"] + "/.local/state") + "/sysadmin-repo-metadata/build-configs", help=""),
        Option(name="filter-out-phases", default="", help=""),
        Option(name="git-push-protocol", default="git", help=""),
        Option(name="git-repository-base", default={"qt6-copy": "https://invent.kde.org/qt/qt/", "_": "fake/"}, help=""),
        Option(name="repository", default="kde-projects", help=""),
        Option(name="set-env", default={}, help=""),  # dict of environment vars to set
        Option(name="use-projects", default="", help=""),
    ]

    phase_changing_options = [
        Option(name="build-only", default="", help=""),
        Option(name="install-only", default="", help=""),
        Option(name="no-build", default="", help=""),
        Option(name="no-install", default="", help=""),
        Option(name="no-src", aliases=["S"], default="", help=""),
        Option(name="src-only", aliases=["s"], default="", help=""),
        Option(name="uninstall", default="", help=""),
    ]

    non_context_options_without_parameter = [
        Option(name="dependency-tree", default="", help=""),
        Option(name="dependency-tree-fullpath", default="", help=""),
        Option(name="list-installed", default="", help=""),
        Option(name="no-metadata", aliases=["M"], default="", help=""),
        Option(name="rebuild-failures", default="", help=""),
    ]

    non_context_options_without_parameter_manually_handled = [
        Option(name="all-config-projects", default="", help=""),
        Option(name="all-kde-projects", default="", help=""),
        Option(name="help", aliases=["h"], default="", help=""),
        Option(name="install-login-session-only", default="", help=""),
        Option(name="resume", default="", help=""),
        Option(name="resume-refresh-build-first", aliases=["R"], default="", help=""),
        Option(name="self-update", default="", help=""),
        Option(name="show-info", default="", help=""),
        Option(name="version", aliases=["v"], default="", help=""),
    ]

    non_context_options_with_parameter = [
        Option(name="resume-after", aliases=["after", "a"], default="", help=""),
        Option(name="resume-from", aliases=["from", "f"], default="", help=""),
        Option(name="stop-after", aliases=["to"], default="", help=""),
        Option(name="stop-before", aliases=["until"], default="", help=""),
    ]

    non_context_options_with_parameter_manually_handled = [
        Option(name="query", default="", help=""),
        Option(name="rc-file", default="", help=""),
    ]

    non_context_options_with_extra_specifier = [
        Option(name="set-project-option-value", default="", help=""),
        Option(name="d", default="", help=""),
        Option(name="D", default="", help=""),
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
        for option in cls.global_options_private:
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
        for option in cls.global_options_private:
            ret[option.name] = option.default
        return ret

    @classmethod
    def all_global_options_names(cls) -> list[str]:
        ret = list(cls.all_global_options().keys())
        return ret

    @classmethod
    def all_possible_options_names(cls) -> list[str]:
        global_options = cls.all_global_options_names()
        phase_changing_options = [el.name for el in OptionsSpec.phase_changing_options]
        ret = sorted(global_options + phase_changing_options)
        return ret

    @classmethod
    def all_boolean_options_names(cls) -> list[str]:
        ret = [el.name for el in cls.global_options_with_negatable_form]
        return ret

    @classmethod
    def get_option_by_name(cls, opt_name: str) -> Option:
        extra_specified_options = cls.global_options_with_extra_specifier + cls.non_context_options_with_extra_specifier
        for opt in extra_specified_options:
            if opt.name == opt_name:
                return opt
        raise KeyError(f"Option {opt_name} is not found in extra specified")
