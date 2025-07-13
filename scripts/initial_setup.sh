#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
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

  if [ "$ID" = "alpine" ]; then
    (set -x; sudo apk update)
    (set -x; sudo apk add git py3-yaml py3-setproctitle py3-pip)
  elif [[ "$ID_LIKE" == *"arch"* || "$ID" = "arch" ]]; then
    (set -x; sudo pacman -S git dbus-python python-yaml python-setproctitle --needed)
  elif [ "$ID" = "debian" ] || [ "$ID" = "ubuntu" ] || [ "$ID" = "neon" ]; then
    (set -x; sudo apt update)
    (set -x; sudo apt install git python3-dbus python3-yaml python3-setproctitle)
  elif [ "$ID" = "fedora" ]; then
    (set -x; sudo dnf install git python3-dbus python3-pyyaml python3-setproctitle)
  elif [ "$ID" = "gentoo" ]; then
    (set -x; sudo emerge -qu dev-python/dbus-python dev-python/pyyaml dev-python/setproctitle)
  elif [ "$ID" = "opensuse-leap" ]; then
    (set -x; sudo zypper install python311 python311-PyYAML)
    # Does not have packages: dbus-python, setproctitle
    pip install pipenv
    # For building from source code the Python module dbus-python.
    (set -x; sudo zypper install cmake gcc libdbus-c++-devel libglib-testing-devel python311-devel)
  elif [[ "$ID_LIKE" == *"opensuse-tumbleweed"* || "$ID" = "opensuse-tumbleweed" ]]; then
    (set -x; sudo zypper refresh)
    (set -x; sudo zypper install git python3-dbus-python python3-pyaml python3-setproctitle)
  elif [ "$ID" = "freebsd" ]; then
    FREEBSD_OSVERSION=$(uname -U)
    if [ $FREEBSD_OSVERSION -ge 1402000 ]; then
      (set -x; sudo pkg install git python3 py311-pyyaml py311-setproctitle py311-dbus)
    else
      (set -x; sudo pkg install git python3 py39-yaml py39-setproctitle py39-dbus)
    fi
  elif [ "$ID" = "openbsd" ]; then
    VNAME=${VNAME:-$(sysctl -n kern.osrelease)}
    VTYPE=$( sed -n "/^OpenBSD $VNAME\([^ ]*\).*$/s//\1/p" \
    /var/run/dmesg.boot | sed '$!d' )
    [ "$VTYPE" = -current ] && PKG_SNAP=-Dsnap
    (set -x; doas pkg_add $PKG_SNAP python%3 py3-yaml py3-setproctitle py3-dbus)
  else
    echo -e "${Yellow}Warning: Unsupported OS: $ID, skipping installation of runtime packages.${Color_Off}" 1>&2

    if ! type git >/dev/null 2>&1; then
      echo -e "${Red}The git binary is missing. Please install git package manually.${Color_Off}"
      err_report  # manually show error message
      exit 1
    fi

    check_python_module() {
      local pymod_name="$1"
      if ! python3 -c "import $pymod_name" &>/dev/null; then
        echo -e "${Red}The required python python module \"$pymod_name\" is missing. Please install it manually.${Color_Off}"
        err_report  # manually show error message

        local answer
        read -r -p "Do you want to proceed anyway? (y/n) " answer
        if [ "$answer" = "y" ]; then
          echo "Continuing..."
        else
          echo "Cancelled by user."
          exit 1
        fi
      fi
    }

    check_python_module yaml
    check_python_module setproctitle
  fi
}

clone_or_update_repository() {
  mkdir -p ~/.local/share
  cd ~/.local/share
  if [ -d kde-builder ]; then
    echo "Updating git repository"
    git -C kde-builder pull --ff-only
  else
    echo "Cloning git repository"
    git clone https://invent.kde.org/sdk/kde-builder.git
  fi
}

prepare_bin_path() {
  echo "Preparing bin path"
  mkdir -p ~/.local/bin

  if [[ $ID_LIKE == *"debian"* || $ID == "debian" ]] && [[ -f ~/.profile ]]; then
    # On Debian-like distros, the default ~/.profile automatically adds ~/.local/bin to PATH when it exists.
    # Because the ~/.local/bin directory could be created just now, we source the ~/.profile, so the user does not need to do it themselves - and PATH variable becomes updated.
    # shellcheck disable=SC1090
    source ~/.profile
  fi

  if [[ ":$PATH:" == *":$HOME/.local/bin:"* || ":$PATH:" == *":$HOME/.local/bin/:"* ]]; then
    echo "Your PATH is correctly set."
  else
    echo -e "${Red}Your PATH is missing ~/.local/bin. You need to add it.${Color_Off}"
    echo -e "See documentation page: https://kde-builder.kde.org/en/getting-started/before-building.html"
    err_report  # manually show error message
    exit 1
  fi
}

install_in_venv_and_make_wrapper_in_bin_path() {
  echo "Installing in venv and making wrapper"
  cd ~/.local/share/kde-builder
  pipenv install

  rm ~/.local/bin/kde-builder  # In case it was there and is symlink, the cat writes to the symlink target, so we delete it to ensure this is not a case.
  cat << EOF > ~/.local/bin/kde-builder
#!/bin/bash
export PIPENV_PIPFILE=~/.local/share/kde-builder/Pipfile
pipenv run python3 ~/.local/share/kde-builder/kde-builder \$@
EOF
  chmod u+x ~/.local/bin/kde-builder
}

make_symlink_in_bin_path() {
  echo "Making symlink in the bin path"
  if [ -f ~/.local/bin/kde-builder ]; then  # to prevent error message when it does not exist
    rm ~/.local/bin/kde-builder
  fi
  ln -sf ~/.local/share/kde-builder/kde-builder ~/.local/bin
}

install_icon_and_desktop_file() {
  echo "Installing icon and desktop file"
  mkdir -p ~/.local/share/icons
  cp -v ~/.local/share/kde-builder/logo.png ~/.local/share/icons/kde-builder.png
  mkdir -p ~/.local/share/applications
  cp -v ~/.local/share/kde-builder/data/kde-builder.desktop.in ~/.local/share/applications/kde-builder.desktop
}

ensure_kde_builder_launches() {
  echo "Ensuring kde-builder could be launched"
  cd ~
  kde-builder --version
}

check_zsh_fpath() {
  echo "Checking that fpath contains path to kde-builder zsh completions"
  local kb_completions_path="$HOME/.local/share/kde-builder/data/completions/zsh/"

  local ZDOTDIR="${ZDOTDIR:-$HOME}"
  # The $FPATH is not exported to scripts, so we get from launched subshell
  local FPATH
  # shellcheck disable=SC2016
  FPATH=$($SHELL -c "source $ZDOTDIR/.zshrc; echo "'$FPATH')

  if [[ ":$FPATH:" == *":$kb_completions_path:"* ]]; then
    echo "Your FPATH is correctly set."
  else
    echo -e "${Yellow}Warning: The $kb_completions_path was not found in your fpath. Please add it manually.${Color_Off}"
  fi
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
clone_or_update_repository
prepare_bin_path

if [ "$ID" = "opensuse-leap" ]; then
  install_in_venv_and_make_wrapper_in_bin_path
else
  make_symlink_in_bin_path
fi

install_icon_and_desktop_file

ensure_kde_builder_launches

# The $ZSH_VERSION variable is not exported to launched scripts, so we get it from launched subshell
# shellcheck disable=SC2016
if [[ -n $($SHELL -c 'echo $ZSH_VERSION') ]]; then  # Check if user's default shell is zsh
  check_zsh_fpath
fi

echo -e "${Green}Installation finished.${Color_Off}"
