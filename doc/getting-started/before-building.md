(before-building)=
# Installation and initial configuration

(initial-setup-of-kde-builder)=
## Initial Setup of KDE Builder

(get-kde-builder)=
### Install KDE Builder

Before installing, configure your PATH environment variable to include the `~/.local/bin` path - the location where kde-builder will be installed.
See [how to set environment variables](https://wiki.archlinux.org/title/Environment_variables#Per_user) for more information.

For example, add this code to your `~/.bashrc` or `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

or, if using fish shell, you can add it by running (this stays permanent):

```shell
fish_add_path ~/.local/bin
```

```{note}
On Debian-like distros, the default `~/.profile` automatically adds `~/.local/bin` to PATH when `~/.local/bin` exists.
The initial_setup.sh script will automatically source the `~/.profile` file, so you do not need to additionally configure PATH.
```

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
