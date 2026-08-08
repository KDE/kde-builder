(get-kde-builder)=
# Install KDE Builder in a legacy way

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
