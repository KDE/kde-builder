# KDE Builder

This script streamlines the process of setting up and maintaining a development
environment for KDE software.

It does this by automating the process of downloading source code from the
KDE source code repositories, building that source code, and installing it
to your local system.

### The goal of the project

**KDE Builder** is a drop-in replacement for the **Kdesrc Build** project. It is the exact reimplementation
of the predecessor script, but in Python - a much more acknowledged language. The original project is in Perl,
and this is a significant barrier for new contributions.

After switching to this project, those much wanted features (see the bugtracker) can be implemented with ease.

## Prerequisites

This project targets Python version 3.11. But can be used with Python 3.10 or Python 3.12.

Install Python (assuming you want to use Python 3.11):

* Arch Linux: `yay -S python`
* Fedora 39: `sudo dnf install python3.11`
* openSUSE Tumbleweed: `sudo zypper install python311`
* Debian/Ubuntu:
```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11
```

## Installation

There are three ways of installation. Choose one of the ways that fits you most.

| Installation way                                                       | Notes                                                          |
|------------------------------------------------------------------------|----------------------------------------------------------------|
| [Use distribution package](#using-distribution-package)                | The easiest way, but may be unavailable for some distributions |
| [Manual checkout, use native environment](#using-native-environment)   | Require that all python dependencies are provided by distro    |
| [Manual checkout, use virtual environment](#using-virtual-environment) | The most reliable way, but a bit more complicated to setup     |

### Using distribution package

#### Arch Linux

```
yay -S kde-builder-git
```

#### openSUSE Tumbleweed
```
sudo zypper addrepo https://download.opensuse.org/repositories/home:/enmo/openSUSE_Tumbleweed/home:enmo.repo
sudo zypper install kde-builder
```

### Using native environment

Ensure your distribution provides python packages, that correspond project dependencies listed in `Pipfile`.

Install all required dependencies manually via your package manager.

Clone `kde-builder` to the folder where you store software (assume it is `~/.local`):

```bash
cd ~/.local/share
git clone https://invent.kde.org/ashark/kde-builder.git
```

Create a symlink to the script (assuming the `~/.local/bin` is in your `PATH`):

```bash
ln -sf ~/.local/share/kde-builder ~/.local/bin
```

Make sure it works by running:

```bash
cd ~
kde-builder --version
```

### Using virtual environment

Install pipenv.

* Arch Linux: `sudo pacman -S python-pipenv`
* Fedora 39: `sudo dnf install pipenv`
* openSUSE Tumbleweed: not available in the repositories. You will need to install it with `pip install`.
* Debian/Ubuntu: pipenv package seems to be broken on Ubuntu 22.04 LTS. You will need to use `pip install pipenv`.

Clone `kde-builder` to the folder where you store software (assume it is `~/.local`):

```bash
cd ~/.local/share
git clone https://invent.kde.org/ashark/kde-builder.git
```

Create a virtual environment with the required packages:

```bash
cd ~/.local/share/kde-builder
pipenv install
```

To be able to invoke the script by just its name, create a wrapper script.  
Create a file `~/bin/kde-builder` (assuming the `~/bin` is in your `PATH`), make this file executable.  
Add the following content to it:

```bash
#!/bin/bash

cd ~/.local/share/kde-builder
pipenv run python kde-builder $@
```

Make sure it works by running:

```bash
cd ~
kde-builder --version
```

Add these cmake options to your config:

```
global
    cmake-options ... -DPython3_FIND_VIRTUALENV=STANDARD -DPython3_FIND_UNVERSIONED_NAMES=FIRST
end global
```

This will let cmake find python modules from your system packages.

## Initial setup

Run this command to install needed dependencies:

```bash
kde-builder --install-distro-packages
```

Run this command to generate configuration file:

```bash
kde-builder --generate-config
```

## Usage

Observe the build plan:

```bash
kde-builder --pretend kcalc
```

Build a project and its dependencies:

```bash
kde-builder kcalc
```

Rebuild only a single project without updating the source code:

```bash
kde-builder --no-include-dependencies --no-src kcalc
```

Launch the binary for a project using the development environment:

```bash
kde-builder --run kcalc
```

To build a specific project while skipping certain modules:

```bash
kde-builder kcalc --ignore-modules kxmlgui
```

## Documentation

See the wiki page [Get_Involved/development](https://community.kde.org/Get_Involved/development).

For more details, consult the project documentation. The most important pages are:

- [List of supported configuration options](https://docs.kde.org/trunk5/en/kdesrc-build/kdesrc-build/conf-options-table.html)
- [Supported command line parameters](https://docs.kde.org/trunk5/en/kdesrc-build/kdesrc-build/supported-cmdline-params.html)