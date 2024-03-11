# KDE Builder

This tool streamlines the process of setting up and maintaining a development
environment for KDE software.

It does this by automating the process of downloading source code from the
KDE source code repositories, building that source code, and installing it
to your local system.

**kde-builder** is a successor of a previously used tool called [**kdesrc-build**](https://invent.kde.org/sdk/kdesrc-build).  
The predecessor project was written in Perl, and this was a significant barrier for new contributions.  
The successor project is written in Python - a much more acknowledged language. This means that newly wanted features can be implemented with ease.  

## Prerequisites

This project targets Python version 3.9 or newer.

Install Python (assuming you want to use Python 3.11):

* Arch Linux: `sudo pacman -S python`
* Fedora 39: `sudo dnf install python3.11`
* openSUSE Tumbleweed: `sudo zypper install python311`
* Debian/Ubuntu: `sudo apt install python3`

## Installation

There are three ways of installation. Choose the one that fits you most.

| Installation way                                                                                                 | Notes                                                           |
|------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| [Using the kde-builder package available for your operating system](#using-distribution-package)                 | The easiest way, but may be unavailable for some distributions. |
| [Manual git checkout of kde-builder, use Python packages from your operating system](#using-native-environment)  | Requires that all python dependencies be provided by distro.    |
| [Manual git checkout of kde-builder, use a Python virtual environment](#using-virtual-environment)               | The most reliable way, but a bit more complicated to set up.    |

<a name="using-distribution-package"></a>
### Installation option 1: Using the kde-builder package available for your operating system

#### Arch Linux

```
yay -S kde-builder-git
```

#### openSUSE Tumbleweed
```
sudo zypper addrepo https://download.opensuse.org/repositories/home:/enmo/openSUSE_Tumbleweed/home:enmo.repo
sudo zypper install kde-builder
```

<a name="using-native-environment"></a>
### Installation option 2: Using Python packages from your operating system

Ensure your distribution provides python packages, that correspond project dependencies listed in `Pipfile`.

Install all required dependencies manually via your package manager.

Clone `kde-builder` to the folder where you store software (assume it is `~/.local`):

```bash
mkdir -p ~/.local/share
cd ~/.local/share
git clone https://invent.kde.org/sdk/kde-builder.git
```

Create a symlink to the script (assuming the `~/.local/bin` is in your `PATH`):

```bash
mkdir -p ~/.local/bin
ln -sf ~/.local/share/kde-builder/kde-builder ~/.local/bin
# Make sure that the directory "~/.local/bin" is in $PATH.
echo $PATH
```

Make sure it works by running:

```bash
cd ~
kde-builder --version
```

<a name="using-virtual-environment"></a>
### Installation option 3: Using a Python virtual environment

Install pipenv.

* Arch Linux: `sudo pacman -S python-pipenv`
* Fedora 39: `sudo dnf install pipenv`
* openSUSE Tumbleweed: not available in the repositories. You will need to install it with `pip install`.
* Debian/Ubuntu: pipenv package seems to be broken on Ubuntu 22.04 LTS. You will need to use `pip install pipenv`.
* KDE neon is based on Ubuntu 22.04 LTS and has Python 3.10. Instructions for KDE neon:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11

python3.11 -m pip install --user pipenv
# Restart the computer in order for the PATH environment variable to contain the directory "~/.local/bin".
# Make sure that the directory "~/.local/bin" is in $PATH.
echo $PATH
which pipenv
# Should say "~/.local/bin/pipenv".

# For building from source code the Python module dbus-python.
sudo apt install pkgconf cmake libdbus-1-dev libglib2.0-dev python3.11-dev
```

Clone `kde-builder` to the folder where you store software (assume it is `~/.local`):

```bash
cd ~/.local/share
git clone https://invent.kde.org/sdk/kde-builder.git
```

Create a virtual environment with the required packages:

```bash
cd ~/.local/share/kde-builder
pipenv install
```

To be able to invoke the script by just its name, create a wrapper script.  
Create a file `~/.local/bin/kde-builder` (assuming that `~/.local/bin` is in your `PATH`). Add the following content to it:

```bash
#!/bin/bash
pipenv run python ~/.local/share/kde-builder/kde-builder $@
```

Make the file executable:

```bash
chmod u+x ~/.local/bin/kde-builder
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
