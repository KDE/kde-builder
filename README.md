<!--
SPDX-License-Identifier: CC-BY-SA-4.0
SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
-->

# KDE Builder

This tool streamlines the process of setting up and maintaining a development environment for KDE software.

It does this by automating the process of downloading source code from the
KDE source code repositories, building that source code, and installing it
to your local system.

KDE Builder downloads and used data from special repository [**repo-metadata**](https://invent.kde.org/sysadmin/repo-metadata).  
It contains KDE Projects database, names of branches to checkout for each project, build configs (default cmake options)
for projects, and some other data.  

## Tutorials on develop.kde.org

For quick start, you can follow these tutorials:
- https://develop.kde.org/docs/getting-started/building/kde-builder-setup/
- https://develop.kde.org/docs/getting-started/building/kde-builder-compile/

## Documentation

For more details, consult the project documentation at https://kde-builder.kde.org/.

Shortcuts to some pages:

- [Installation](https://kde-builder.kde.org/en//getting-started/installation.html)
- [Initial setup steps](https://kde-builder.kde.org/en//getting-started/before-building.html#initial-setup-of-kde-builder)
- [List of supported configuration options](https://kde-builder.kde.org/en/configuration/conf-options-table.html)
- [Supported command line parameters](https://kde-builder.kde.org/en/cmdline/supported-cmdline-params.html)
