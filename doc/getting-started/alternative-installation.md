# Alternative Installation Methods

If the `initial_setup.sh` installation method does not work for you, you can choose one of the alternative methods.

KDE Builder can use Python version 3.9 or newer.  

If python is not installed, do it now (assuming you want to use Python 3.11):

* Arch Linux: `sudo pacman -S python`
* Fedora 39: `sudo dnf install python3.11`
* openSUSE Tumbleweed: `sudo zypper install python311`
* Debian/Ubuntu: `sudo apt install python3`

There are three ways of installation. Choose the one that fits you most.

| Installation way                                                                                                | Notes                                                           |
|-----------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| [Using the kde-builder package available for your operating system](#using-distribution-package)                | The easiest way, but may be unavailable for some distributions. |
| [Manual git checkout of kde-builder, use Python packages from your operating system](#using-system-environment) | Requires that all python dependencies be provided by distro.    |
| [Manual git checkout of kde-builder, use a Python virtual environment](#using-virtual-environment)              | The most reliable way, but a bit more complicated to set up.    |

(using-distribution-package)=
## Using the kde-builder package available for your operating system

Arch Linux:

```
yay -S kde-builder-git
```

openSUSE Tumbleweed:

```
sudo zypper addrepo https://download.opensuse.org/repositories/home:/enmo/openSUSE_Tumbleweed/home:enmo.repo
sudo zypper install kde-builder
```

(using-system-environment)=
## Using Python packages from your operating system

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
mkdir ~/.local/bin
ln -sf ~/.local/share/kde-builder/kde-builder ~/.local/bin
```

Make sure it works by running:

```bash
cd ~
kde-builder --version
```

(using-virtual-environment)=
## Using a Python virtual environment

Install pipenv.

* Arch Linux: `sudo pacman -S python-pipenv`
* Fedora 39: `sudo dnf install pipenv`
* openSUSE Tumbleweed: not available in the repositories. You will need to install it with `pip install`.
* Debian/Ubuntu: pipenv package seems to be broken on Ubuntu 22.04 LTS. You will need to use `pip install pipenv`.
* KDE neon is based on Ubuntu 22.04 LTS and has Python 3.10. Instructions for KDE neon (if you want to use python 3.11):

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

Note that `Pipfile` uses python 3.9 version. That is made this way because the gitlab ci job uses it, to ensure python 3.9
is correctly supported. If you want to use a more recent version, specify it with `--python /path/to/python`. 

Create a virtual environment with the required packages:

```bash
cd ~/.local/share/kde-builder
pipenv install --python /usr/bin/python3.11  # <-- use path to interpreter you want to use
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

```yaml
global:
  cmake-options ... -DPython3_FIND_VIRTUALENV=STANDARD -DPython3_FIND_UNVERSIONED_NAMES=FIRST
```

This will let cmake find python modules from your system packages.
