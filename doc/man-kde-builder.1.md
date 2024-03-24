Michael Pyne mpyne@kde.org
Authored man page
2019-08-31
kde-builder 19.08
kde-builder 1
19.08
kde-builder

Downloads, builds and installs KDE software.

kde-builder

OPTIONS

Module name \| Module set name

# DESCRIPTION

The `kde-builder` command is used in order to download and build KDE
software directly from its source Git repositories. It interfaces with
the KDE project database, and supports controlling which options are
passed to `make`(1) and `cmake`(1). The operation of `kde-builder` is
driven by a configuration file, typically `~/.config/kdesrc-buildrc`
(`$XDG_CONFIG_HOME/kdesrc-buildrc`, if `$XDG_CONFIG_HOME` is set).

The \<module name\> or \<module set name\> as given on the command line
should be as those names were defined in the configuration file (either
in a `module` definition or `use-modules` declaration, or in a
`module-set` definition). In addition, it can be the name of a KDE
module listed in the KDE project database (and you can precede the
module name with `+` to force this).

`kde-builder` is designed to be able to be completely headless
(however, see **ENVIRONMENT**), and so typically ignores its input
completely. Command output is logged instead of being shown on the
kde-builder output.

Modules are built one after the other. If a module fails to update then
it is not built. `kde-builder` will not abort just because of a module
failure, instead it will keep trying to update and build subsequent
modules. By default, `kde-builder` will commence building a module as
soon as the source code update is complete for that module, even if
other updates are occurring concurrently.

At the end `kde-builder` will show which modules failed to build, and
where the logs were kept for that build run.

# EXIT STATUS

**0**  
Success

**1**  
Normally this means some part of the update, build or install process
failed, but is also used for any abnormal program end not otherwise
covered below.

**5**  
A signal was received that killed `kde-builder`, but it attempted to
perform normal closedown.

**8**  
Unknown option was passed on the command line.

**99**  
An exception was raised that forced `kde-builder` to abort early.

# SIGNALS

kde-builder supports `SIGHUP`, which if received will cause
kde-builder to exit after the current modules for the build thread (and
update thread, if still active) have completed.

# FILES

`~/.config/kdesrc-buildrc` (`$XDG_CONFIG_HOME/kdesrc-buildrc`, if
`$XDG_CONFIG_HOME` is set) - Default global configuration file.

`kdesrc-buildrc` - If this file is found in the **current directory**
when kde-builder is run, this file will be used for the configuration
instead of `~/.config/kdesrc-buildrc`.

`~/.local/state/kdesrc-build-data` (`$XDG_STATE_DIR/kdesrc-buildrc`, if
`$XDG_STATE_DIR` is set) - `kde-builder` uses this file to store
persistent data (such as last CMake options used, last revision
successfully installed, etc.). It can be safely deleted.

# BUGS

See <https://bugs.kde.org/>. Be sure to search against the
`kde-builder` product.

# EXAMPLE

\$ `kde-builder`  
Downloads, builds and installs all modules listed in the configuration
file, in the order defined therein.

\$ `kde-builder --pretend`  
Same as above, except no permanent actions are taken (specifically no
log files are created, downloads performed, build processes run, etc.).
**EXCEPTION**: If you are trying to build a module defined in the KDE
project database, and the database has not been downloaded yet,
`kde-builder` will download the database since this can significantly
affect the final build order.

\$ `kde-builder --no-src --refresh-build kdebase`  
Deletes the build directory for the *kdebase* module set
(`--refresh-build`) and then starts the build process again without
updating the source code in-between.

\$ `kde-builder --rc-file /dev/null --pretend`  
Forces `kde-builder` to read an empty configuration file and simulate
the resultant build process. This shows what would happen by default
with no configuration file, without an error message about a missing
configuration file.

\$ `kde-builder +kdebase/kde-baseapps`  
Downloads, builds and installs the `kde-baseapps` module from the KDE
project database. Since the module name is preceded by a `+` it is
assumed to defined in the KDE project database even if this hasn't been
specifically configured in the configuration file.

The `kdebase/` portion forces `kde-builder` to ignore any
`kde-baseapps` modules that are not children of the `kdebase`
supermodule in the project database (although it is contrived for this
example).

\$ `kde-builder --refresh-build --cmake-options="-DCMAKE_BUILD_TYPE=Debug"`  
Downloads, builds and installs all modules defined in the configuration
file but overrides the `cmake-options` option to have the value given on
the command line for this run only. Any further `kde-builder` runs will
use the `cmake-options` given in the configuration file.

# SEE ALSO

build-tool - A program by Michael Jansen which can build KDE software
based on included recipes.

# RESOURCES

Main web site: <https://apps.kde.org/kdesrc_build/>

Documentation: <https://docs.kde.org/?application=kdesrc-build>

# COPYING

Copyright (C) 2003-2022 Michael Pyne.

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
