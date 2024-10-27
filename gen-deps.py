#!/usr/bin/python

import os
import re
import sys
import requests
import yaml

IGNORE_LIST = {
    "kfloppy",
    # Plasma Mobile
    "plank-player",
    "qrca",
}
OVERRIDES = {
    "kdeconnect-kde": "kdeconnect",
    "polkit-qt-1": "polkit-qt",
}

# There's no easy way to get these out of pacman
META_PACKAGES = {
    "phonon-vlc",
    "phonon",
    "packagekit-qt",
    "kdsoap",
    "libqaccessibilityclient",
    "qca",
    "qtkeychain",
}


[pacman_list_path, kde_buidler_list_path] = sys.argv[1:]

pacman_list = set(open(pacman_list_path).read().splitlines())
kde_buidler_list = set(open(kde_buidler_list_path).read().splitlines())


def match_package(package: str):
    if package in pacman_list:
        return package
    if package in OVERRIDES:
        return OVERRIDES[package]
    if package in META_PACKAGES:
        return package

    return None


packages_map = {
    kde_package: match_package(kde_package)
    for kde_package in kde_buidler_list
    if kde_package not in IGNORE_LIST
}

# check for missing packages
missing_packages = {
    kde_package: package for kde_package, package in packages_map.items() if not package
}
if missing_packages:
    print("Ignoring missing packages:", file=sys.stderr)
    for kde_package, package in missing_packages.items():
        candidates = [p for p in pacman_list if kde_package in p]
        print(f"  {kde_package} -> {candidates}", file=sys.stderr)

# Remove missing packages so we don't have to worry about them going forward
packages_map = {
    kde_package: package for kde_package, package in packages_map.items() if package
}

packages_count = len(packages_map) - len(missing_packages)
packages_done = 0
print()
for kde_package, package in packages_map.items():

    src_info_url = f"https://gitlab.archlinux.org/archlinux/packaging/packages/{package}/-/raw/main/.SRCINFO"
    src_info_file = f"{package}.SRCINFO"

    packages_done += 1

    if os.path.exists(src_info_file):
        continue

    sys.stdout.write(
        f"[{packages_done}/{packages_count}] Downloading SRCINFO for {package}... "
    )

    response = requests.get(src_info_url)
    if response.status_code == 200 and f"pkgbase = {package}" in response.text:
        with open(src_info_file, "wb") as file:
            file.write(response.content)
        print("OK")
    else:
        print(f"Failed to download {src_info_url}", file=sys.stderr)

# read all the files into memeory so we can search them multiple times
srcinfo_files = {
    package: open(f"{package}.SRCINFO").read()
    for package in packages_map.values()
    if package
}

# Packages that have more than one instance of pkgname are split packages
split_package_names = {
    package: [
        line.split(" = ")[1]
        for line in srcinfo_files[package].splitlines()
        if "pkgname =" in line
    ]
    for package in packages_map.values()
}
split_package_names = {
    package: pkgnames
    for package, pkgnames in split_package_names.items()
    if len(pkgnames) > 1
}

if len(split_package_names) > 0:
    print("Ignoring split packages:", file=sys.stderr)
    for package, pkgnames in split_package_names.items():
        if len(pkgnames) > 1:
            print(f"  {package}: {pkgnames}", file=sys.stderr)

# Remove split packages so we don't have to worry about them going forward
packages_map = {
    kde_package: package
    for kde_package, package in packages_map.items()
    if package not in split_package_names
}

# Find the dependencies for each package
dependencies = {
    package: {
        "optdepends": [
            line.split(" = ")[1]
            for line in srcinfo_files[package].splitlines()
            if "optdepends =" in line
        ],
        "makedepends": [
            line.split(" = ")[1]
            for line in srcinfo_files[package].splitlines()
            if "makedepends =" in line
        ],
        "depends": [
            line.split(" = ")[1]
            for line in srcinfo_files[package].splitlines()
            if "\tdepends =" in line
        ],
    }
    for package in packages_map.values()
}

# Since we are only interested external dependencies, remove the ones that are in the packages_map
dependencies = {
    package: {
        dep_type: [dep for dep in deps if dep not in packages_map.values()]
        for dep_type, deps in dep_types.items()
    }
    for package, dep_types in dependencies.items()
}

print()
print("Dependencies:")
print(yaml.dump(dependencies, default_flow_style=False, indent=2))
