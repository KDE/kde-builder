# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import re
import subprocess
import sys
from datetime import datetime
from enum import Enum
from enum import auto
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version
from typing import NoReturn

from kde_builder import KB_REPO_DIR
from kde_builder.debug import KBLogger
from kde_builder.os_support import OSSupport
from kde_builder.util.textwrap_mod import dedent

logger_app = KBLogger.getLogger("application")

class InstallationType(Enum):
    """
    Types of KDE Builder installations.
    """

    GIT = auto()
    UV = auto()
    PIPX = auto()
    UNKNOWN = auto()


class Version:
    """
    Can determine kde-builder version, installation type, upgrade command.
    """

    UPSTREAM_URL = "https://invent.kde.org/sdk/kde-builder.git"
    UPSTREAM_BRANCH = "master"

    @classmethod
    def script_version(cls) -> str:
        """
        Returns a dynamic version string complying with PEP 440.

        Some examples of returned string:
          "26.04"
            - when installed from a tagged release
          "26.04.post5+g123abc99c"
            - when there are 5 additional commits after the tagged commit.
          "26.04.post5+g123abc99c.d20260504"
            - when there are 5 additional commits after the tagged commit, and uncommitted changes.
          "26.04.post0+g123abc99c.d20260504"
            - when there are no commits after the tag, but there are uncommitted changes.
        """
        inst_type = cls.detect_installation_type()

        if inst_type == InstallationType.GIT:
            res_tags = subprocess.run(["git", "tag"], capture_output=True, text=True, cwd=KB_REPO_DIR)
            has_tags = bool(res_tags.stdout.strip())

            cmd = ["git", "describe", "--tags", "--long", "--always", "--abbrev=9", "--dirty"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=KB_REPO_DIR)
            git_output = result.stdout.strip()
            if result.returncode == 0 and git_output:
                is_dirty = False
                date_suffix = ""
                if git_output.endswith("-dirty"):
                    is_dirty = True
                    date_suffix = f".d{datetime.now().strftime('%Y%m%d')}"
                    git_output = git_output.removesuffix("-dirty")

                if not has_tags:
                    rev_cmd = ["git", "rev-list", "--count", "HEAD"]
                    res_rev = subprocess.run(rev_cmd, capture_output=True, text=True, cwd=KB_REPO_DIR)
                    commits_count = res_rev.stdout.strip() if res_rev.returncode == 0 else "0"
                    return f"0.0.post{commits_count}+g{git_output}{date_suffix}"

                try:
                    tag, commits_count, commit_hash = git_output.rsplit("-", 2)
                    clean_tag = tag.lstrip("v")
                    if commits_count == "0" and not is_dirty:
                        return clean_tag

                    return f"{clean_tag}.post{commits_count}+{commit_hash}{date_suffix}"
                except ValueError:
                    return f"{git_output}{date_suffix}"

        else:
            try:
                current_version = version("kde-builder")
                return current_version
            except PackageNotFoundError:
                pass

        return "Unknown"

    @classmethod
    def self_update(cls) -> NoReturn:
        inst_type = cls.detect_installation_type()
        upg_cmd = cls.get_upgrade_command(inst_type)
        if inst_type == InstallationType.GIT:
            logger_app.info(f"b[*] Running g[{upg_cmd}]")
            subprocess.run(upg_cmd, shell=True)
        elif inst_type == InstallationType.UV:
            logger_app.info(dedent(f"""
                 r[*] This installation of KDE Builder is managed by uv. Please use the following command:
                    y[{upg_cmd}]
                """, preserve_len=1))
        elif inst_type == InstallationType.PIPX:
            logger_app.info(dedent(f"""
                 r[*] This installation of KDE Builder is managed by pipx. Please use the following command:
                   y[{upg_cmd}]
                """, preserve_len=1))
        else:
            logger_app.info(" r[*] This installation of KDE Builder is not self managed. Please use the appropriate update method.")
        sys.exit()

    @classmethod
    def check_for_updates(cls) -> None:
        logger_app.info("\n b[*] Checking for kde-builder updates.")
        inst_type = cls.detect_installation_type()
        current_ver = cls.script_version()

        if inst_type == InstallationType.GIT:
            subprocess.run("git fetch origin master:refs/remotes/origin/master", shell=True, cwd=KB_REPO_DIR)
            local_master_head = subprocess.run("git rev-parse --short=7 refs/heads/master", shell=True, capture_output=True, check=False, cwd=KB_REPO_DIR).stdout.decode("utf-8").removesuffix("\n")
            remote_master_head = subprocess.run("git rev-parse --short=7 refs/remotes/origin/master", shell=True, capture_output=True, check=False, cwd=KB_REPO_DIR).stdout.decode("utf-8").removesuffix("\n")

            if local_master_head != remote_master_head:
                logger_app.warning(" y[*] Your kde-builder version seems to be outdated.")
            else:
                logger_app.info(" g[*] Your kde-builder version is up-to-date.")
            return

        if current_ver == "Unknown":
            logger_app.warning(" y[*] Cannot determine local version to check for updates.")
            return

        ver_components = cls.extract_version_components(current_ver)

        if ver_components is None:
            logger_app.warning(f" y[*] Cannot parse local version: {current_ver}")
            return

        # noinspection bad-assignment
        local_tag: str = ver_components["base"]
        local_hash = ver_components["hash"]

        latest_remote_tag = cls.latest_remote_tag()

        local_tag_v = cls.tag_to_tuple(local_tag)
        remote_tag_v = cls.tag_to_tuple(latest_remote_tag)

        if remote_tag_v > local_tag_v:
            logger_app.warning(" y[*] Your kde-builder version seems to be outdated.")
            return
        elif remote_tag_v < local_tag_v:
            logger_app.warning(" y[*] Your kde-builder version seems to not yet been released.")
            return

        if local_hash is None:
            logger_app.debug(" g[*] You are using released version of kde-builder, determining the commit hash of the tag.")
            if latest_remote_tag == "v0.0":
                # User has installation of plain "0.0" version, without ".postN+gXXXXX"!?
                # This is only possible in case we intentionally create a "v0.0" tag, and user installs it, and there are no yet newer tags.
                # Still check this just to be safe.
                logger_app.warning(" y[*] Remote repo does not have tags.")
                return
            else:
                tag_commit_hash = cls.remote_tag_commit_hash(latest_remote_tag)
                if tag_commit_hash is None:
                    logger_app.warning(" y[*] Cannot determine remote tag commit hash.")
                    return
                local_hash = tag_commit_hash

        latest_remote_hash = cls.remote_branch_head_commit_hash()

        if latest_remote_hash is None:
            logger_app.warning(" y[*] Cannot determine remote commit hash.")
            return

        n = min(len(local_hash), len(latest_remote_hash))
        if n == 0:
            logger_app.warning(" y[*] Cannot compare remote and local commit hash.")
            return

        if local_hash[:n] != latest_remote_hash[:n]:
            logger_app.warning(" y[*] Your kde-builder version seems to be outdated.")
        else:
            logger_app.info(" g[*] Your kde-builder version is up-to-date.")

    @classmethod
    def show_version_and_exit(cls) -> NoReturn:
        ver = cls.script_version()
        print(ver)
        sys.exit()

    @classmethod
    def show_info_and_exit(cls) -> NoReturn:
        ver = cls.script_version()
        os_vendor = OSSupport().ID
        inst_type = cls.detect_installation_type().name
        print(dedent(f"""
            Version: {ver}
            Installation type: {inst_type}
            OS: {os_vendor}
            """))
        sys.exit()

    @classmethod
    def detect_installation_type(cls) -> InstallationType:
        in_system_environment = sys.prefix == sys.base_prefix

        if in_system_environment:
            can_run_git = subprocess.call("type " + "git", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
            if KB_REPO_DIR and can_run_git and os.path.isdir(f"{KB_REPO_DIR}/.git"):
                return InstallationType.GIT

        if not in_system_environment:
            # We cannot rely on uv key in pyvenv.cfg, because pipx also may use uv for venv creation.
            if os.path.isfile(sys.prefix + "/uv-receipt.toml"):
                return InstallationType.UV
            # User may use PIPX_HOME, so we will not rely on "pipx" in path.
            if os.path.exists(sys.prefix + "/pipx_metadata.json"):
                return InstallationType.PIPX

        return InstallationType.UNKNOWN

    @staticmethod
    def get_upgrade_command(inst_type: InstallationType) -> str:
        match inst_type:
            case InstallationType.GIT:
                return f"git -C {KB_REPO_DIR} pull origin master"
            case InstallationType.UV:
                return "uv tool upgrade kde-builder"
            case InstallationType.PIPX:
                return "pipx upgrade kde-builder"
            case _:
                return "unknown command"

    @classmethod
    def _list_remote_tags(cls) -> list[str]:
        repo_url = cls.UPSTREAM_URL
        res = subprocess.run(["git", "ls-remote", "--tags", repo_url], capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return []

        tags: set[str] = set()
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            refname = parts[1]
            if not refname.startswith("refs/tags/"):
                continue
            name = refname[len("refs/tags/"):]
            if name.endswith("^{}"):
                name = name[:-3]
            tags.add(name)
        return list(tags)

    @staticmethod
    def tag_to_tuple(v: str) -> tuple[int, ...]:
        """
        Convert a tag string into version tuple.

        Examples:
          "v1.2.3" -> (1, 2, 3)
          "v1.2" -> (1, 2)
          other -> ()
        """
        v = v.lstrip("vV").strip()
        m = re.match(r"^(\d+(?:\.\d+)*)", v)
        if not m:
            return ()
        return tuple(int(x) for x in m.group(1).split("."))

    @classmethod
    def latest_remote_tag(cls) -> str:
        """
        Determines the remote tag, that has most recent version.

        In case there are no remote tags, returns "v0.0".
        """
        tags = cls._list_remote_tags()
        tup_versions: dict[tuple[int, ...], str] = {}
        for tag in tags:
            tup_version: tuple[int, ...] = cls.tag_to_tuple(tag)
            if tup_version:
                tup_versions[tup_version] = tag
        if not tup_versions:
            return "v0.0"
        latest_version: tuple[int, ...] = max(tup_versions)
        return tup_versions[latest_version]

    @staticmethod
    def extract_version_components(version_str: str) -> dict[str, str | None] | None:
        """
        Separate the kde-builder version into its components.
        """
        pattern = re.compile(
            r"^(?P<base>\d+\.\d+(?:\.\d+)?)"  # Tag version
            r"(?:\.post(?P<post>\d+))?"  # Number of commits after tag (optional)
            r"(?:\+g(?P<hash>[a-f0-9]+))?"  # Commit hash (optional)
            r"(?:\.d(?P<date>\d{8}))?$"  # Date of dirty build (optional)
        )

        match = pattern.match(version_str)
        if not match:
            return None

        components = match.groupdict()
        return {
            "base": components["base"],
            "post": components["post"],
            "hash": components["hash"],
            "date": components["date"],
        }

    @classmethod
    def remote_branch_head_commit_hash(cls) -> str | None:
        """
        Commit hash of the HEAD of remote branch.
        """
        repo_url = cls.UPSTREAM_URL
        branch = cls.UPSTREAM_BRANCH
        res = subprocess.run(["git", "ls-remote", repo_url, f"refs/heads/{branch}"], capture_output=True, text=True, check=False)
        if res.returncode != 0 or not res.stdout.strip():
            return None
        sha = res.stdout.split()[0]
        return sha[:9]

    @classmethod
    def remote_tag_commit_hash(cls, tag_name: str) -> str | None:
        """
        Returns the commit SHA for a given remote tag.
        """
        repo_url = cls.UPSTREAM_URL
        res = subprocess.run(["git", "ls-remote", repo_url, f"refs/tags/{tag_name}"], capture_output=True, text=True, check=False)
        if res.returncode != 0 or not res.stdout.strip():
            return None

        lines = res.stdout.splitlines()

        target_ref_annotated = f"refs/tags/{tag_name}" + "^{}}"
        for line in lines:
            parts = line.split()
            if len(parts) == 2 and parts[1] == target_ref_annotated:
                return parts[0][:9]

        target_ref_exact = f"refs/tags/{tag_name}"
        for line in lines:
            parts = line.split()
            if len(parts) == 2 and parts[1] == target_ref_exact:
                return parts[0][:9]

        return None
