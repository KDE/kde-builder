# SPDX-FileCopyrightText: 2018, 2020, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import re
import subprocess
import time
from typing import NoReturn

from .build_context import BuildContext
from .kb_exception import KBException
from .kb_exception import SetupError
from .debug import KBLogger
from .os_support import OSSupport

logger_fr = KBLogger.getLogger("first-run")


class FirstRun:
    """
    Performs initial-install setup, implementing the ``--initial-setup`` option.

    Examples:
    ::

        exitcode = FirstRun.setup_user_system()
        exit(exitcode)
    """

    def __init__(self, prefilled_prompt_answer: str | None = None):
        self.oss = OSSupport()
        self.base_dir = None
        self.supported_distros = ["alpine", "arch", "debian", "fedora", "gentoo", "mageia", "opensuse"]  # Debian handles Ubuntu also
        self.supported_other_os = ["freebsd", "openbsd"]
        self.prefilled_prompt_answer = prefilled_prompt_answer

    def setup_user_system(self, base_dir, setup_steps: list[str]) -> NoReturn:
        self.base_dir = base_dir

        try:
            if "install-distro-packages" in setup_steps:
                logger_fr.warning("=== install-distro-packages ===")

                # The distro dependencies are listed in sysadmin/repo-metadata repository
                # First, we need to download metadata with Application.

                from .application import Application
                Application(["--metadata-only", "--metadata-only"])  # invokes _download_kde_project_metadata internally
                # We use a hack to catch exactly this command line to make the app not exit. This way we do not influence the normal behavior, and we
                # do not create a normal instance of Application, because it will create a lockfile.
                # todo remove this hack after moving take_lock to another place before actual work from the Application.__init__

                metadata_distro_deps_path = os.environ.get("XDG_STATE_HOME", os.environ["HOME"] + "/.local/state") + "/sysadmin-repo-metadata/distro-dependencies"
                self._install_system_packages(metadata_distro_deps_path)
            if "generate-config" in setup_steps:
                logger_fr.warning("=== generate-config ===")
                self._setup_base_configuration()
        except KBException as e:
            msg = e.message
            logger_fr.error(f"  b[r[*] r[{msg}]")
            exit(1)

        exit(0)

    # Internal functions

    @staticmethod
    def _read_packages(vendor, version, deps_data_path) -> dict:
        """
        Read from the files from data/pkg and dump the contents in a dict keyed by filename (the "[pkg/vendor/version]" part between each resource).
        """
        packages = {}
        cur_key = ""
        with open(f"{deps_data_path}/{vendor}.ini", "r") as file:
            while line := file.readline():
                line = line.removesuffix("\n")
                if match := re.match(r"^\[ *([^ ]+) *]$", line):
                    cur_key = match.group(1)
                    packages[cur_key] = []
                    continue
                if line.startswith("#") or line == "":
                    continue
                packages[cur_key].append(line)
        return packages

    def confirmed_to_continue(self) -> bool:
        if self.prefilled_prompt_answer is None:
            answer = input("   Do you want to continue? [Y/n]: ")
        else:
            answer = self.prefilled_prompt_answer

        answer = answer.lower()
        if answer in ["y", "yes", ""]:
            return True
        else:
            return False

    def _install_system_packages(self, deps_data_path) -> None:

        vendor = self.oss.ID

        logger_fr.info(f" b[-] Installing b[system packages] for b[{vendor}]...")

        packages = self._find_best_vendor_package_list(deps_data_path)
        if not packages:
            logger_fr.error(f" r[b[*] Packages could not be installed, because kde-builder does not know your distribution ({vendor})")
            return

        install_cmd = self._find_best_install_cmd()
        not_found_in_repo_packages = []

        # Remake the command for Arch Linux to not require running sudo command when not needed (https://bugs.kde.org/show_bug.cgi?id=471542)
        if self.oss.is_based_on("arch"):
            required_packages_and_required_groups = packages
            missing_packages_and_required_groups = subprocess.run("pacman -T " + " ".join(required_packages_and_required_groups), shell=True, capture_output=True, check=False).stdout.decode("utf-8").removesuffix("\n").split("\n")
            all_possible_groups = subprocess.run("pacman -Sg", shell=True, capture_output=True, check=False).stdout.decode("utf-8").removesuffix("\n").split("\n")
            required_groups = [el for el in missing_packages_and_required_groups if el in all_possible_groups]
            missing_packages_not_grouped = [el for el in missing_packages_and_required_groups if el not in required_groups]
            missing_packages_from_required_groups = []
            if required_groups:
                for required_group in required_groups:
                    missing_packages_from_required_group = subprocess.run(f"pacman -Sqg {required_group} | xargs pacman -T", shell=True, capture_output=True, check=False).stdout.decode("utf-8").removesuffix("\n").split("\n")
                    missing_packages_from_required_group = list(filter(None, missing_packages_from_required_group))  # Remove empty string element. It appears if there is no any unresolved package from the group
                    missing_packages_from_required_groups += missing_packages_from_required_group
            packages = missing_packages_not_grouped + missing_packages_from_required_groups

        if self.oss.is_based_on("debian"):
            all_available_packages = subprocess.run("apt list", shell=True, capture_output=True).stdout.decode("utf-8").removesuffix("\n").split("\n")
            all_available_packages.pop(0)  # The 0 element is "Listing..."
            all_available_packages = [pkg.split("/")[0] for pkg in all_available_packages]

            for package in packages:
                if package not in all_available_packages:
                    not_found_in_repo_packages.append(package)
            if not_found_in_repo_packages:
                logger_fr.warning(" y[*] These packages were not found in repositories:\n\t" + "\n\t".join(not_found_in_repo_packages))
                logger_fr.warning(" y[*] Removing them from the list of installation")
                for package in not_found_in_repo_packages:
                    packages.remove(package)

        if packages:
            logger_fr.info(f""" b[*] Would run \"b[{" ".join(install_cmd + packages)}]\"""")
            if not self.confirmed_to_continue():
                print("Interrupted by user.")
                return

            result = subprocess.run(install_cmd + packages, shell=False)
            exit_status = result.returncode
        else:
            logger_fr.info(" b[*] No packages to install, no need to run installer. b[:)]")
            exit_status = 0

        if exit_status != 0:
            # Install one at a time if we can
            individual_failed_packages = []

            logger_fr.warning(" b[*] The command with all listed packages failed. Will retry installing packages one by one.\n")
            if not self.confirmed_to_continue():
                print("Interrupted by user.")
                return

            for one_package in packages:
                logger_fr.info(f"""\n b[*] Running \"b[{" ".join(install_cmd + [one_package])}]\"""")
                # Allow for Ctrl+C.
                time.sleep(250 / 1000)
                result = subprocess.run(install_cmd + [one_package], shell=False)

                if result.returncode != 0:
                    individual_failed_packages.append(one_package)

            if not_found_in_repo_packages:  # repeat this, because that info was in the very beginning before the long installation output
                logger_fr.warning(" y[*] Some packages were not found in repositories and were removed from installation list:\n\t" + "\n\t".join(not_found_in_repo_packages))

            if individual_failed_packages:
                logger_fr.warning("\n y[b[*] Some packages failed to install:\n" + "\n\t".join(individual_failed_packages))
            else:
                logger_fr.warning(f" r[b[*] Packages were installed individually, but the command to install them at once failed with exit status {exit_status}. Please report this case.")
        else:
            if not_found_in_repo_packages:  # repeat this, because that info was in the very beginning before the long installation output
                logger_fr.warning(" y[*] Some packages were not found in repositories and were removed from installation list:\n\t" + "\n\t".join(not_found_in_repo_packages))
            logger_fr.info(" b[*] b[g[Packages were successfully installed!]")

    @staticmethod
    def _setup_base_configuration() -> None:
        # According to XDG spec, if $XDG_CONFIG_HOME is not set, then we should
        # default to ~/.config
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.environ.get("HOME") + "/.config")
        xdg_config_home_short = xdg_config_home.replace(os.environ.get("HOME"), "~")  # Replace $HOME with ~
        known_locations = [os.getcwd() + "/kde-builder.yaml",
                           f"{xdg_config_home}/kde-builder.yaml",
                           os.environ.get("HOME") + "/kde-builder.yaml"]
        located_file = None
        for known_location in known_locations:
            if os.path.isfile(known_location):
                located_file = known_location
                break

        if located_file:
            printable_located_file = located_file.replace(os.environ.get("HOME"), "~")
            logger_fr.warning(f"b[*] You already have a configuration file: b[y[{printable_located_file}]")
            return

        logger_fr.info(f"b[*] Creating b[sample configuration file]: b[y[\"{xdg_config_home_short}/kde-builder.yaml\"]...")

        with open(os.path.dirname(os.path.realpath(__file__)) + "/../data/kde-builder.yaml.in", "r") as data_file:
            sample_rc = data_file.read()

        sample_rc = sample_rc.replace("%{num_cores}", "\"" + "auto" + "\"")
        sample_rc = sample_rc.replace("%{num_cores_low}", "\"" + "auto" + "\"")

        gl = BuildContext().build_options["global"]  # real global defaults

        def fill_placeholder(option_name, mode="") -> None:
            value = gl[option_name]
            if mode == "bool_to_str":
                # Perl doesn't have native boolean types, so config internally operates on 0 and 1.
                # But it will be convenient to users to use "true"/"false" strings in their config files.
                value = "true" if value else "false"
            elif mode == "home_to_tilde":
                value = re.sub(rf"""^{os.environ.get("HOME")}""", "~", value)
            nonlocal sample_rc
            sample_rc = sample_rc.replace(f"%{{{option_name}}}", value)

        fill_placeholder("include-dependencies", "bool_to_str")
        fill_placeholder("source-dir", "home_to_tilde")
        fill_placeholder("build-dir", "home_to_tilde")
        fill_placeholder("install-dir", "home_to_tilde")
        fill_placeholder("log-dir", "home_to_tilde")
        fill_placeholder("install-login-session", "bool_to_str")
        fill_placeholder("stop-on-failure", "bool_to_str")
        fill_placeholder("directory-layout")
        fill_placeholder("compile-commands-linking", "bool_to_str")
        fill_placeholder("compile-commands-export", "bool_to_str")
        fill_placeholder("generate-clion-project-config", "bool_to_str")
        fill_placeholder("generate-vscode-project-config", "bool_to_str")
        fill_placeholder("generate-qtcreator-project-config", "bool_to_str")
        fill_placeholder("check-self-updates", "bool_to_str")

        os.makedirs(xdg_config_home, exist_ok=True)
        with open(f"{xdg_config_home}/kde-builder.yaml", "w") as sample_fh:
            sample_fh.write(sample_rc)
        print()

    def _find_best_install_cmd(self) -> list[str]:
        cmds = {
            "cmd/install/alpine/unknown": "apk add --virtual .makedeps-kde-builder",
            "cmd/install/arch/unknown": "pacman -S --noconfirm",
            "cmd/install/debian/unknown": "apt-get -q -y --no-install-recommends install",
            "cmd/install/fedora/unknown": "dnf -y install --skip-broken",
            "cmd/install/freebsd/unknown": "pkg install -y",
            "cmd/install/openbsd/unknown": "pkg_add -I",
            "cmd/install/gentoo/unknown": "emerge -v --noreplace",
            "cmd/install/opensuse/unknown": "zypper install -y --no-recommends",
        }

        supported_distros = [cmddist.removeprefix("cmd/install/").removesuffix("/unknown") for cmddist in cmds.keys()]

        best_vendor = self.oss.best_distro_match(supported_distros)
        logger_fr.info(f"    Using installer for b[{best_vendor}]")

        version = self.oss.vendor_version()
        cmd = []

        for opt in [f"{best_vendor}/{version}", f"{best_vendor}/unknown"]:
            key = f"cmd/install/{opt}"
            if key in cmds.keys():
                cmd = cmds[key].split(" ")
                break

        if not cmd:
            raise SetupError(f"No installer for {best_vendor}!")

        # If not running as root already, add sudo
        if os.geteuid() != 0:
            has_sudo = subprocess.call("type " + "sudo", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
            if has_sudo:
                cmd.insert(0, "sudo")
            else:
                logger_fr.error("r[*] You are missing g[sudo]! Cannot continue.")
                exit(1)
        return cmd

    def _find_best_vendor_package_list(self, deps_data_path) -> list[str]:
        best_vendor = self.oss.best_distro_match(self.supported_distros + self.supported_other_os)
        version = self.oss.vendor_version()
        logger_fr.info(f"    Installing packages for b[{best_vendor}]/b[{version}]")
        return self._packages_for_vendor(best_vendor, version, deps_data_path)

    def _packages_for_vendor(self, vendor, version, deps_data_path) -> list[str]:
        packages = self._read_packages(vendor, version, deps_data_path)
        for opt in [f"pkg/{vendor}/{version}", f"pkg/{vendor}/unknown"]:
            if opt in packages.keys():
                return packages[opt]
        return []
