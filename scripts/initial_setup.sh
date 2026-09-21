#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# This script installs kde-builder

set -eE  # exit on error, errtrace to still be able to trap errors


Color_Off="\033[0m"       # Text Reset
Red="\033[0;31m"          # Red
Yellow="\033[0;33m"       # Yellow
Green="\033[0;32m"        # Green


err_report() {
  echo -e "${Red}Exited on error at line $(caller).${Color_Off}"
}
trap "err_report" ERR  # When error happens, this function will run automatically before exit.

install_runtime_packages() {
  echo "Installing runtime packages"

  if [[ "$ID" == "alpine" || "$ID_LIKE" == *"alpine"* ]]; then
    (set -x; sudo apk update)
    (set -x; sudo apk add git py3-uv)
  elif [[ "$ID" = "arch" || "$ID_LIKE" == *"arch"* ]]; then
    (set -x; sudo pacman -S git uv --needed)
  elif [[ "$ID" = "debian" || "$ID_LIKE" = *"debian"* ]]; then
    (set -x; sudo apt update)
    (set -x; sudo apt install git)
  elif [ "$ID" = "fedora" ]; then
    if [[ "$VARIANT_ID" = "kinoite" ]]; then
      echo -e "${Red}Error: Unsupported OS variant: ${Yellow}$VARIANT_ID${Red}, cannot install runtime packages.${Color_Off}" 1>&2
      err_report  # manually show error message
      exit 1
    fi
    (set -x; sudo dnf install git uv)
  elif [ "$ID" = "gentoo" ]; then
    (set -x; sudo emerge -qu dev-vcs/git dev-python/uv)
  elif [ "$ID" = "opensuse-leap" ]; then
    (set -x; sudo zypper install git)
  elif [[ "$ID" = "opensuse-tumbleweed" || "$ID_LIKE" == *"opensuse-tumbleweed"* ]]; then
    (set -x; sudo zypper refresh)
    (set -x; sudo zypper install git python-uv)
  elif [ "$ID" = "freebsd" ]; then
    (set -x; sudo pkg install git)
  elif [ "$ID" = "openbsd" ]; then
    VNAME=${VNAME:-$(sysctl -n kern.osrelease)}
    VTYPE=$( sed -n "/^OpenBSD $VNAME\([^ ]*\).*$/s//\1/p" \
    /var/run/dmesg.boot | sed '$!d' )
    [ "$VTYPE" = -current ] && PKG_SNAP=-Dsnap
    (set -x; doas pkg_add $PKG_SNAP git)
  else
    echo -e "${Yellow}Warning: Unsupported OS: $ID, skipping installation of runtime packages.${Color_Off}" 1>&2

    if ! command git &> /dev/null; then
      echo -e "${Red}The git binary is missing. Please install git package manually.${Color_Off}"
      err_report  # manually show error message
      exit 1
    fi
  fi
}

install_standalone_uv_if_needed() {
  if ! command -v uv &> /dev/null; then
      echo "Installing standalone uv"
      curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
}

install_kde_builder() {
  echo "Installing kde-builder using uv"
  uv tool install "git+https://invent.kde.org/sdk/kde-builder.git"
}

ensure_kde_builder_launches() {
  echo "Ensuring kde-builder could be launched"
  cd ~
  kde-builder --version
}

### --------------------------------
###         Script starts
### --------------------------------

if [ -f /etc/os-release ]; then
  source /etc/os-release
elif [[ "$OSTYPE" == "darwin"* ]]; then
  ID="macOS"
elif [[ "$OSTYPE" == "openbsd"* ]]; then
  ID="openbsd"
else
  echo "${Red}Unable to detect operating system.${Color_Off}" 1>&2
  exit 1
fi

echo "Your distro ID: $ID"

install_runtime_packages
install_standalone_uv_if_needed

install_kde_builder

ensure_kde_builder_launches

echo -e "${Green}Installation finished.${Color_Off}"
