Michael Pyne mpyne@kde.org
Authored man page
2019-08-31
kdesrc-build 19.08
kdesrc-build 1
19.08
kdesrc-build

Downloads, builds and installs KDE software.

kdesrc-build

OPTIONS

Module name \| Module set name

# DESCRIPTION

The `kdesrc-build` command is used in order to download and build KDE
software directly from its source Git repositories. It interfaces with
the KDE project database, and supports controlling which options are
passed to `make`(1) and `cmake`(1). The operation of `kdesrc-build` is
driven by a configuration file, typically `~/.config/kdesrc-buildrc`
(`$XDG_CONFIG_HOME/kdesrc-buildrc`, if `$XDG_CONFIG_HOME` is set).

The \<module name\> or \<module set name\> as given on the command line
should be as those names were defined in the configuration file (either
in a `module` definition or `use-modules` declaration, or in a
`module-set` definition). In addition, it can be the name of a KDE
module listed in the KDE project database (and you can precede the
module name with `+` to force this).

`kdesrc-build` is designed to be able to be completely headless
(however, see **ENVIRONMENT**), and so typically ignores its input
completely. Command output is logged instead of being shown on the
kdesrc-build output.

Modules are built one after the other. If a module fails to update then
it is not built. `kdesrc-build` will not abort just because of a module
failure, instead it will keep trying to update and build subsequent
modules. By default, `kdesrc-build` will commence building a module as
soon as the source code update is complete for that module, even if
other updates are occurring concurrently.

At the end `kdesrc-build` will show which modules failed to build, and
where the logs were kept for that build run.

# OPTIONS

**NOTE**: Some options have short forms, but the `kdesrc-build` option
parser does not support combining short options into one at this point.
(E.g. running `kdesrc-build -pv` would not be the same as
`kdesrc-build --pretend --verbose`).

`-h, --help`  
Shows a brief synopsis and frequently-used command line options.

`--show-info`  
Shows information about kdesrc-build and the operating system which may
be useful in bug reports or when requesting help on forums or mailing
lists.

`--initial-setup`  
Performs one-time setup for users running kdesrc-build on common
distributions. This includes installation of known system dependencies,
a default configuration file setup, and changes to your ~/.bashrc to
make the software installed by kdesrc-build accessible. This is exactly
equivalent to using "--install-distro-packages --generate-config" at the
same time. In kdesrc-build (perl implementation) it additionally uses
"--install-distro-packages-perl".

`--install-distro-packages`  
Installs distro packages (on supported Linux distributions) necessary to
prepare the system for kdesrc-build to operate, and for the
newly-installed KDE software to run.

`--generate-config`  
Generate the kdesrc-build configuration file.

`-p, --pretend`  
Operate in a "dry run" mode. No network accesses are made, no log files
are created, no modules are built, and no other permanent changes to
disk are made. One *important exception* is that if you try to build a
module that comes from the KDE project database, and the database hasn't
been downloaded yet, the database will be downloaded since the
pretend-mode output may change significantly based on the database
results.

`--install-only`  
Skips the update and build phase and immediately attempts to install the
modules given.

`--uninstall`  
Skips the update and build phase and immediately attempts to uninstall
the modules given. **NOTE**: This is only supported for buildsystems
that supports the `make uninstall` command (e.g. KDE CMake-based).

`-S, --no-src`  
Skips the source update phase. Other phases are included as normal.

`-M, --no-metadata`  
Skips the metadata update phase for KDE modules. Other phases (including
the source update phase) are included as normal. If you wish to avoid
all network updates you should also pass `--no-src`.

This option can be useful if you are frequently running `kdesrc-build`
since the metadata itself does not change very often.

`--no-install`  
Skips the install phase from the build. Other phases are included as
normal.

`--no-build`  
Skips the build phase for the build. Internally the install phase
depends on the build phase completing so this is effectively equivalent
to `--src-only`, but the semantics may change in the future (e.g. when
test suites are moved into their own phase).

`--no-tests`  
Disables running the test suite for CMake-based modules. To be fully
effective this requires re-running CMake, which can be forced by using
the `--reconfigure` or `--refresh-build` options.

`-s, --src-only`  
Only performs the source update phase, does not build or install.

`--build-only`  
Forces the build process to be performed without updating source code
first. In addition, installation is not performed. (Testing is still
performed if applicable, but this will change in a future release)

`--metadata-only`  
Only updates the build metadata needed for KDE modules, then exits. This
is useful to allow the `--pretend` option to work if you've never run
kdesrc-build. See also `--no-metadata`.

`-r, --refresh-build`  
Removes the build directory for a module before the build phase starts.
This has the desired side effect of forcing `kdesrc-build` to
re-configure the module and build it from a "pristine" state with no
existing temporary or intermediate output files. Use this option if you
have problems getting a module to build but realize it will take longer
(possibly much longer) for the build to complete as a result. When in
doubt use this option for the entire `kdesrc-build` run.

`--reconfigure`  
Force CMake to be re-run, but without deleting the build directory.
Usually you actually want `--refresh-build`, but if you are 100% sure
your change to `cmake-options` will not invalidate your current
intermediate output then this can save some time.

`--build-system-only`  
Interrupts the build process for each module built: The build process
consists of normal setup up to and including running `cmake` or
`configure` (as appropriate), but `make` is not run and no installation
is attempted. This is mostly only useful to get things like
`configure --help` and `cmake-gui` to work. Normally you want
`--reconfigure` or `--refresh-build`.

`--resume-from=foo`, `--from=foo`, `-f foo`,  
Use this option to skip module processing until the module \<foo\> is
encountered. \<foo\> and all subsequent modules will be processed
normally as if they had been specified on the command line. If you use
this option because of a build failure you may want to consider using
`--no-src` in addition to skip the resultant source update phase.

`--resume-after=foo`, `--after=foo`, `-a foo`  
This is just like `--resume-from`, except that the module \<foo\> is
*not* included in the list of modules to consider. You might use this if
you've manually built/installed foo after fixing the build and just want
to resume from there.

`--resume`  
This option can be used to run `kdesrc-build` after it has had a build
failure.

It resumes the build from the module that failed, using the list of
modules that were waiting to be built before, and disables source and
metadata updates as well. The use case is when a simple mistake or
missing dependency causes the build failure. Once you correct the error
you can quickly get back into building the modules you were building
before, without fiddling with `--resume-from` and `--stop-before`.

`--stop-before=foo`, `--until=foo`  
This is similar to the `--resume-from` flag. This option causes the
module list for the given build to be truncated just *before* \<foo\>
would normally have been built. \<foo\> is *not* built (but see
`--stop-after`).

This flag may be used with `--resume-from` or `--resume-after`.

`--stop-after=foo`, `--to=foo`  
This is just like `--stop-before`, except that the given module *is*
included in the build.

This flag may be used with `--resume-from` or `--resume-after`.

`-d, --include-dependencies`  
This causes `kdesrc-build` to include not only the modules it would
normally build (either because they were specified on the command line,
or mentioned in the configuration file), but also to include *known
dependencies* of those modules in the build. This is normally the
default; you can use `--no-include-dependencies` to disable this effect.

Dependencies are “known” to `kdesrc-build` based on the contents of the
special *kde-build-metadata* git repository, which is managed for you by
the script (see also the `--metadata-only` option). The KDE community
keeps the dependency information in that module up to date, so if
`kdesrc-build` appears to show the wrong dependencies then it may be due
to missing or incorrect dependency information.

All known dependencies will be included, which may be more than you
need. Consider using the `--resume-from` option (and similar options) to
control the build list when using this option.

`-D, --no-include-dependencies`  
This is the negation of `--include-dependencies`, for use if you have
configured dependencies to be included by default.

`--rebuild-failures`  
Use this option to build only those modules which failed to build on a
previous `kdesrc-build` run. This is useful if a significant number of
failures occurred mixed with successful builds. After fixing the issue
causing the build failures you can then easily build only the modules
that failed previously.

Note that the list of “previously-failed modules” is reset every time a
`kdesrc-build` run finishes with some module failures. However it is not
reset by a completely successful build, so you can successfully rebuild
a module or two and this flag will still work.

This option was added for kdesrc-build 15.09.

`--stop-on-failure, --no-stop-on-failure`  
This option causes the build to abort as soon as a failure occurs. This
is the default. With negative flag, `kdesrc-build` will try to press on
with the rest of the modules in the build to avoid wasting time in case
the problem is with a single module.

`-!, --ignore-modules`  
Forces **ALL** modules that follow this option to be excluded from
consideration by `kdesrc-build`. This might be useful if you know you
want to process all modules except for specific exceptions.

`--rc-file=foo`  
Use the given file, \<foo\>, for the configuration instead of
`./kdesrc-buildrc` or `~/.config/kdesrc-buildrc`. The file can be empty,
but it must exist.

`--nice=foo`  
Changes the CPU priority given to `kdesrc-build` (and all processes used
by `kdesrc-build` e.g. `make`(1)). \<foo\> should be an integer number
between -20 and 19. Positive values are "nicer" to the rest of the
system (i.e. lower priority).

Note that the possible priorities available on your system may be
different than listed here, see `nice`(2) for more information. Note
also that this only changes *CPU* priority, often you want to change
*I/O* priority on systems where that is supported. There is no
command-line option for I/O priority adjustment, but there is a
configuration file option: `use-idle-io-priority` (although like all
options, there is a generic way to set this from the command line).

`--run=foo`  
Runs the program named by \<foo\> using prefix.sh environment variables.
All command line arguments present after this option are passed to
\<foo\> as it is run.

`--query=mode`  
This command causes `kdesrc-build` to query a parameter of the modules
in the build list (either passed on the command line or read in from the
configuration file), outputting the result to screen (one module per
line).

This option must be provided with a “query mode”, which should be one of
the following:

- `source-dir`, which causes `kdesrc-build` to output the full path to
  where the module's source code is stored.

- `build-dir`, which causes `kdesrc-build` to output the full path to
  where the module build process occurs.

- `install-dir`, which causes `kdesrc-build` to output the full path to
  where the module will be installed.

- `project-path`, which causes `kdesrc-build` to output the location of
  the module within the hierarchy of KDE source code repositories.

- `branch`, which causes `kdesrc-build` to output the resolved git
  branch that will be used for each module, based on the `tag`, `branch`
  and `branch-group` settings in effect.

- `module-set`, which causes kdesrc-build to output the name of
  module-set which contains the module. This can be used to generate zsh
  autocompletion cache.

- `build-system`, which causes kdesrc-build to output the name of build
  system detected for the module. This can be used to debug build system
  auto-detection problems, or when developing tests for specific build
  systems.

- Otherwise, option names that are valid for modules in the
  configuration file can be used, the resolved value of which will be
  listed for each module.

This option was added with `kdesrc-build` 16.05.

For example, the command “`kdesrc-build` `--query` `branch`
`kactivities` `kdepim`” might end up with output like:

```
kactivities: master
kdepim: master
```

`--dependency-tree`  
Takes all actions up to and including dependency reordering of the
modules specified on the command line (or configuration file), and
prints dependency information for each selected module in a (recursive)
tree output format. Generated information includes which specific
commit/branch/tag is depended on, as well as whether the module would be
built. Note that the output can become quite large for applications with
many dependencies or when many modules are (implicitly) selected.

The `kde-project` metadata is downloaded first (though, see `--pretend`
or `--no-src`).

The output is not fully compatible with usage by scripts as other output
messages may be generated until the module list is shown.

`--color`  
Enables "colorful output". (Enabled by default).

`--no-color`  
Disables "colorful output". This can be made permanent by setting the
`colorful-output` option to false (or 0) in your configuration file.

`--async`  
Have `kdesrc-build` start the build process for a module as soon as the
source code has finished downloading. Without this option `kdesrc-build`
performs all source updates at once and only then starts with the build
process. This option is enabled by default.

`--no-async`  
Disables asynchronous building of modules. See `--async` for a more
detailed description. Note that `kdesrc-build`'s output will be slightly
different in this mode.

`--verbose`  
Increases the level of verbosity of `kdesrc-build` output (which is
already fairly verbose!)

`-q, --quiet`  
Makes `kdesrc-build` less noisy. Only important messages are shown.

`--really-quiet`  
Makes `kdesrc-build` even less noisy. Only warnings/errors are shown.

`--debug`  
This will fill your terminal with descriptions and debugging output,
usually unintelligible, describing what `kdesrc-build` is doing (and
thinks it should be doing). The flag is included since the output may
sometimes prove useful for debugging.

`--force-build`  
Normally when `kdesrc-build` notices that there is no source update on a
module which was previously successfully installed, it does not attempt
to build or install that module. You can pass this flag to disable that
behavior and always run `make`.

`--delete-my-patches`  
This option must be passed to allow `kdesrc-build` to remove conflicting
source directories. Currently even this only happens when trying to
clone a git-based module if an existing source directory is present.
Never specify this option unless it is suggested by `kdesrc-build`, and
only if you don't mind the source directories that are referenced being
deleted and re-cloned.

`--foo=bar`  
Any option not listed above is checked to see if it matches the list of
possible configuration file options. If so, the configuration file
option `foo` is temporarily set to `bar` for the duration of this run.

`--set-module-option-value=module,foo,bar`  
Like above, but option `foo` is only set to `bar` for the module
`module`. This does not work for module sets yet, you must repeat this
for each module you want to be affected. (Of course, you could simply
edit your configuration file...) This option worked slightly differently
prior to version 1.16.

# EXIT STATUS

**0**  
Success

**1**  
Normally this means some part of the update, build or install process
failed, but is also used for any abnormal program end not otherwise
covered below.

**5**  
A signal was received that killed `kdesrc-build`, but it attempted to
perform normal closedown.

**8**  
Unknown option was passed on the command line.

**99**  
An exception was raised that forced `kdesrc-build` to abort early.

# ENVIRONMENT

`HOME`  
Used for tilde-expansion of file names, and is the default base for the
source, build, and installation directories.

`PATH`  
This environment variable controls the default search path for
executables. You can use the `binpath` configuration file option to add
to this variable (e.g. for running from `cron`(8)).

`LC_`\*  
Environment variables starting with LC\_ control the locale used by
`kdesrc-build`. Although `kdesrc-build` is still not localizable at this
point, many of the commands it uses are. `kdesrc-build` normally sets
`LC_ALL`=C for commands that its must examine the output of but you can
manually do this as well. If setting `LC_ALL`=C fixes a `kdesrc-build`
problem please submit a bug report.

`SSH_AGENT_PID`  
This environment variable is checked to see if `ssh-agent`(1) is
running, but only if `kdesrc-build` determines that you are checking out
a module that requires an SSH login (but you should know this as no
module requires this by default).

`KDESRC_BUILD_USE_TTY`  
If set, this variable forces `kdesrc-build` not to close its input while
executing system processes. Normally `kdesrc-build` closes `stdin` since
the `stdout` and `stderr` for its child processes are redirected and
therefore the user would never see an input prompt anyways.

`KDESRC_BUILD_DUMP_CONTEXT`  
If set, this variable prints out a description of its "build context"
just after reading options and command line arguments and determining
which modules to build. You pretty much never want to set this.

others  
Many programs are used by `kdesrc-build` in the course of its execution,
including `git`(1), `make`(1), and `cmake`(1). Each of these programs
may have their own response to environment variables being set.
`kdesrc-build` will pass environment variables that are set when it is
run onto these processes. You can ensure certain environment variables
(e.g. `CC` or `CXX`) are set by using the `set-env` configuration file
option.

# SIGNALS

kdesrc-build supports `SIGHUP`, which if received will cause
kdesrc-build to exit after the current modules for the build thread (and
update thread, if still active) have completed.

# FILES

`~/.config/kdesrc-buildrc` (`$XDG_CONFIG_HOME/kdesrc-buildrc`, if
`$XDG_CONFIG_HOME` is set) - Default global configuration file.

`kdesrc-buildrc` - If this file is found in the **current directory**
when kdesrc-build is run, this file will be used for the configuration
instead of `~/.config/kdesrc-buildrc`.

`~/.local/state/kdesrc-build-data` (`$XDG_STATE_DIR/kdesrc-buildrc`, if
`$XDG_STATE_DIR` is set) - `kdesrc-build` uses this file to store
persistent data (such as last CMake options used, last revision
successfully installed, etc.). It can be safely deleted.

# BUGS

See <https://bugs.kde.org/>. Be sure to search against the
`kdesrc-build` product.

# EXAMPLE

\$ `kdesrc-build`  
Downloads, builds and installs all modules listed in the configuration
file, in the order defined therein.

\$ `kdesrc-build --pretend`  
Same as above, except no permanent actions are taken (specifically no
log files are created, downloads performed, build processes run, etc.).
**EXCEPTION**: If you are trying to build a module defined in the KDE
project database, and the database has not been downloaded yet,
`kdesrc-build` will download the database since this can significantly
affect the final build order.

\$ `kdesrc-build --no-src --refresh-build kdebase`  
Deletes the build directory for the *kdebase* module set
(`--refresh-build`) and then starts the build process again without
updating the source code in-between.

\$ `kdesrc-build --rc-file /dev/null --pretend`  
Forces `kdesrc-build` to read an empty configuration file and simulate
the resultant build process. This shows what would happen by default
with no configuration file, without an error message about a missing
configuration file.

\$ `kdesrc-build +kdebase/kde-baseapps`  
Downloads, builds and installs the `kde-baseapps` module from the KDE
project database. Since the module name is preceded by a `+` it is
assumed to defined in the KDE project database even if this hasn't been
specifically configured in the configuration file.

The `kdebase/` portion forces `kdesrc-build` to ignore any
`kde-baseapps` modules that are not children of the `kdebase`
supermodule in the project database (although it is contrived for this
example).

\$ `kdesrc-build --refresh-build --cmake-options="-DCMAKE_BUILD_TYPE=Debug"`  
Downloads, builds and installs all modules defined in the configuration
file but overrides the `cmake-options` option to have the value given on
the command line for this run only. Any further `kdesrc-build` runs will
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
