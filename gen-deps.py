#!/usr/bin/python

import sys

IGNORE_LIST = {"kfloppy", "plank-player"}
OVERRIDES = {"kdeconnect-kde": "kdeconnect", "phonon-vlc": "phonon-qt6-vlc"}

[pacman_list_path, kde_buidler_list_path] = sys.argv[1:]

pacman_list = set(open(pacman_list_path).read().splitlines())
kde_buidler_list = set(open(kde_buidler_list_path).read().splitlines())


def match_package(package: str):
    if package in pacman_list:
        return package
    if f"{package}-qt6" in pacman_list:
        return f"{package}-qt6"
    if package in OVERRIDES:
        return OVERRIDES[package]

    return None
    # raise Exception(f"Missing package: {package}")


packages_map = {
    kde_package: match_package(kde_package)
    for kde_package in kde_buidler_list
    if kde_package not in IGNORE_LIST
}

# check for missing packages
missing_packages = {kde_package: package for kde_package, package in packages_map.items() if not package}
if missing_packages:
    print("Missing packages:")
    for kde_package, package in missing_packages.items():
        print(f"  {kde_package} -> {package}")