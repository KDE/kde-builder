<!--
SPDX-License-Identifier: CC-BY-SA-4.0
SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
-->

# KDE Builder

This tool streamlines the process of setting up and maintaining a development environment for KDE software.

It does this by automating the process of downloading source code from the
KDE source code repositories, building that source code, and installing it
to your local system.

**kde-builder** is a successor of a previously used tool called [**kdesrc-build**](https://invent.kde.org/sdk/kdesrc-build).  
The predecessor project was written in Perl, and this was a significant barrier for new contributions.  
The successor project is written in Python - a much more acknowledged language. This means that newly wanted features can be implemented with ease.  

## Basic Usage

Before installing, configure your PATH environment variable to include the `~/.local/bin` path - the location where kde-builder will be installed.
See [documentation page](https://kde-builder.kde.org/en/getting-started/before-building.html) for more information.

Installation:

```bash
cd ~
curl 'https://invent.kde.org/sdk/kde-builder/-/raw/master/scripts/initial_setup.sh?ref_type=heads' > initial_setup.sh
bash initial_setup.sh
```

Initial setup:

```bash
kde-builder --generate-config
kde-builder --install-distro-packages
```

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

Build a specific project while skipping certain projects:

```bash
kde-builder kcalc --ignore-projects kxmlgui
```

## Documentation

For more details, consult the project documentation at https://kde-builder.kde.org/.

Shortcuts to some pages:

- [Installation and initial setup steps](https://kde-builder.kde.org/en//getting-started/before-building.html#initial-setup-of-kde-builder)
- [List of supported configuration options](https://kde-builder.kde.org/en/configuration/conf-options-table.html)
- [Supported command line parameters](https://kde-builder.kde.org/en/cmdline/supported-cmdline-params.html)
