(before-building)=
# Installation and initial configuration

(initial-setup-of-kde-builder)=
## Initial Setup of KDE Builder

(get-kde-builder)=
### Install KDE Builder

You can install KDE Builder with its installation script:

```bash
cd ~
curl 'https://invent.kde.org/sdk/kde-builder/-/raw/master/scripts/initial_setup.sh?ref_type=heads' > initial_setup.sh
bash initial_setup.sh
```

The installation script will prompt to install KDE Builder's runtime dependencies,
and do installation itself.

You can update KDE Builder later by running this script again.

```{note}
If for some reason you want to make installation differently, consult [](#alternative-installation).
```

(generate-rcfile)=
### Prepare the configuration file

KDE Builder uses a [configuration file](./configure-data) to control
which modules are built, where they are installed to, etc.

Run this command to generate configuration file:

```bash
kde-builder --generate-config
```

The config file will be located at `~/.config/kdesrc-buildrc`
(or `$XDG_CONFIG_HOME/kdesrc-buildrc`, if `$XDG_CONFIG_HOME` is set).

You can then edit the `~/.config/kdesrc-buildrc` configuration file to make any changes you see fit.

(initial-install-distro-packages)=
### Install the dependencies for modules

Building of modules requires some packages from your distribution to be installed.

Run this command to install needed dependencies:

```bash
kde-builder --install-distro-packages
```
