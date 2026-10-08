(before-building)=
# Initial configuration

(initial-setup-of-kde-builder)=
## Initial Setup of KDE Builder

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
