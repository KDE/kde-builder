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

## Installation

This project targets Python version 3.12.

### Using distribution package

If your distribution provides dependencies listed in `Pipfile`, or has packaged
kde-builder, you can use that.

#### Arch Linux

```
yay -S kde-builder-git
```

#### openSUSE Tumbleweed
```
sudo zypper addrepo https://download.opensuse.org/repositories/home:/enmo/openSUSE_Tumbleweed/home:enmo.repo
sudo zypper install kde-builder
```

---

### Using virtual environment

Install Python 3.12:

* Arch Linux: `yay -S python312`
* Fedora 39: `sudo dnf install python3.12`
* openSUSE Tumbleweed: `sudo zypper install python312`
* Debian/Ubuntu:
```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12
```

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
kdesrc-build --version
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
