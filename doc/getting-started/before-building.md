(before-building)=
# Installation and initial configuration

(initial-setup-of-kde-builder)=
## Initial Setup of KDE Builder

(install-with-uv)=
### Install KDE Builder

Install `uv` utility with any way you prefer. See [official documentation](https://docs.astral.sh/uv/getting-started/installation/) for available options.

You do not need to install python of any version, because uv will do it automatically inside the virtual environment.

Run the installation command:
```bash
uv tool install git+https://invent.kde.org/sdk/kde-builder.git
```

Make sure it works by running:

```bash
kde-builder --version
```

Add these cmake options to your config:

```yaml
global:
  cmake-options ... -DPython3_FIND_VIRTUALENV=STANDARD -DPython3_FIND_UNVERSIONED_NAMES=FIRST
```

This will let cmake find python modules from your system packages.

(generate-rcfile)=
### Prepare the configuration file

KDE Builder uses a [configuration file](./configure-data) to control
which projects are built, where they are installed to, etc.

Run this command to generate configuration file:

```bash
kde-builder --generate-config
```

The config file will be located at `~/.config/kde-builder.yaml`
(or `$XDG_CONFIG_HOME/kde-builder.yaml`, if `$XDG_CONFIG_HOME` is set).

You can then edit the `~/.config/kde-builder.yaml` configuration file to make any changes you see fit.

(initial-install-distro-packages)=
### Install the dependencies for projects

Building of projects requires some packages from your distribution to be installed.

Run this command to install needed dependencies:

```bash
kde-builder --install-distro-packages
```
