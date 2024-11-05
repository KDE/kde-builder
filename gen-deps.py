#!/usr/bin/env python

import os
import sys
from typing import Literal
import requests
import yaml

from srcinfo.parse import parse_srcinfo

IGNORE_LIST = {
    "kfloppy",
    # Plasma Mobile
    "plank-player",
    "qrca",
}
OVERRIDES = {
    "kdeconnect-kde": "kdeconnect",
    "polkit-qt-1": "polkit-qt",
    "polkit-kde-agent-1": "polkit-kde-agent",
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

SPLIT_PACKGE_OVERRIDES = {
    "appstream": ["appstream", "appstream-qt"],
    "gpgme": ["gpgme", "qgpgme-qt6"],
    "poppler": ["poppler", "poppler-qt6"],
    "phonon-vlc": ["phonon-qt6-vlc"],
}

MAKE_DEPENDS_OVERRIDES = {
    "phonon-vlc": ["phonon-qt6", "qt6-tools"],
    "breeze": []
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
    for kde_package, arch_package in missing_packages.items():
        candidates = [p for p in pacman_list if kde_package in p]
        print(f"  {kde_package} -> {candidates}", file=sys.stderr)

# Remove missing packages so we don't have to worry about them going forward
packages_map = {
    kde_package: package for kde_package, package in packages_map.items() if package
}

packages_count = len(packages_map) - len(missing_packages)
packages_done = 0
for kde_package, arch_package in packages_map.items():

    src_info_url = f"https://gitlab.archlinux.org/archlinux/packaging/packages/{arch_package}/-/raw/main/.SRCINFO"
    src_info_file = f"{arch_package}.SRCINFO"

    packages_done += 1

    if os.path.exists(src_info_file):
        continue

    sys.stderr.write(
        f"[{packages_done}/{packages_count}] Downloading SRCINFO for {arch_package}... "
    )

    response = requests.get(src_info_url)
    if response.status_code == 200 and f"pkgbase = {arch_package}" in response.text:
        with open(src_info_file, "wb") as file:
            file.write(response.content)
        print("OK", file=sys.stderr)
    else:
        print(f"Failed to download {src_info_url}", file=sys.stderr)


def read_parse_srcinfo(package):
    with open(f"{ package}.SRCINFO") as f:
        srcinfo, errors = parse_srcinfo(f.read())

        if errors:
            raise Exception(f"Failed to parse {package}.SRCINFO: {errors}")

        return srcinfo


# parse all the SRCINFO files
srcinfos = {package: read_parse_srcinfo(package) for package in packages_map.values()}

ignored_split_packages = {}
packages_to_use = {}
for kde_package, arch_package in packages_map.items():
    srcinfo = srcinfos[arch_package]

    if arch_package in SPLIT_PACKGE_OVERRIDES:
        packages_to_use[arch_package] = SPLIT_PACKGE_OVERRIDES[arch_package]
        continue

    pkgnames = list(srcinfo["packages"].keys())

    if len(pkgnames) == 1:
        packages_to_use[arch_package] = pkgnames
        continue

    # if one package has a `5` and the other has no number,
    # we can assume the one without the number is the kf6
    if len(pkgnames) == 2:
        if "5" in pkgnames[0] and not "5" in pkgnames[1]:
            packages_to_use[arch_package] = [pkgnames[1]]
            continue
        elif "5" in pkgnames[1] and not "5" in pkgnames[0]:
            packages_to_use[arch_package] = [pkgnames[0]]
            continue

    if not any(("5" in pkgs or "6" in pkgs) for pkgs in pkgnames):
        packages_to_use[arch_package] = pkgnames
        continue

    ignored_split_packages[arch_package] = pkgnames


if len(ignored_split_packages) > 0:
    print("Ignoring split packages:", file=sys.stderr)
    for arch_package, pkgnames in ignored_split_packages.items():
        print(f"  {arch_package}: {pkgnames}", file=sys.stderr)

    exit(1)


def get_depends(
    dependstype: Literal["optdepends", "makedepends", "depends"], packageName: str
):
    if packageName in MAKE_DEPENDS_OVERRIDES:
        if dependstype == "makedepends":
            return MAKE_DEPENDS_OVERRIDES[packageName]

    pkgs = packages_to_use[packageName]
    basedeps = (
        set(srcinfos[packageName][dependstype])
        if dependstype in srcinfos[packageName]
        else set()
    )
    for pkg in pkgs:
        if dependstype in srcinfos[packageName]["packages"][pkg]:
            basedeps.update(srcinfos[packageName]["packages"][pkg][dependstype])
    return sorted(basedeps)


# Find the dependencies for each package
dependencies = {
    kde_package: {
        "optdepends": get_depends("optdepends", packages_map[kde_package]),
        "makedepends": get_depends("makedepends", packages_map[kde_package]),
        "depends": get_depends("depends", packages_map[kde_package]),
    }
    for kde_package in packages_map.keys()
}

# Since we are only interested external dependencies, remove the ones that are in
# the packages_to_use map
dependencies = {
    kde_package: {
        dependstype: [
            dep
            for dep in deps
            if dep
            not in [pkg for sublist in packages_to_use.values() for pkg in sublist]
        ]
        for dependstype, deps in deps.items()
    }
    for kde_package, deps in dependencies.items()
}

for arch_package in dependencies.keys():
    dependencies[arch_package]["replaces"] = packages_to_use[packages_map[arch_package]]
    new_optdepends = []
    for optdepend in dependencies[arch_package]["optdepends"]:
        if ":" in optdepend:
            dep, reason = optdepend.split(":", maxsplit=1)
            new_optdepends += [{"dep": dep, "reason": reason.strip()}]
        else:
            new_optdepends += [{"dep": optdepend, "reason": ""}]
    dependencies[arch_package]["optdepends"] = new_optdepends


dep_count = {}
for name, deps in dependencies.items():
    all_deps = (
        deps["depends"] + deps["makedepends"] + [d["dep"] for d in deps["optdepends"]]
    )
    for dep in all_deps:
        dep_count[dep] = dep_count.get(dep, 0) + 1

print("common:")
total_targets = len(dependencies)
for dep, count in sorted(dep_count.items(), key=lambda x: x[1], reverse=True):
    percentage = count / total_targets * 100
    if percentage > 90:
        # remove them from individual packages to avoid duplication
        for arch_package in dependencies.keys():
            for dependstype in dependencies[arch_package].keys():
                if dep in dependencies[arch_package][dependstype]:
                    dependencies[arch_package][dependstype].remove(dep)

        print(f"- {dep} # Required by {percentage:.2f}% of projects")

print()
print(yaml.dump({"projects": dependencies}, default_flow_style=False, indent=2), end="")
