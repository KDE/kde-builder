<!--
SPDX-License-Identifier: CC-BY-4.0
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

## Generic installation

```bash
cd ~
curl 'https://invent.kde.org/sdk/kde-builder/-/raw/master/scripts/initial_setup.sh?ref_type=heads' > initial_setup.sh
bash initial_setup.sh
```

## Alternative installation methods

See [Alternative Installation](doc/getting-started/alternative-installation.md)

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

For more details, consult the project documentation at https://kde-builder.kde.org/. The most important pages are:

- [List of supported configuration options](https://kde-builder.kde.org/en/chapter_04/conf-options-table.html)
- [Supported command line parameters](https://kde-builder.kde.org/en/chapter_05/supported-cmdline-params.html)
