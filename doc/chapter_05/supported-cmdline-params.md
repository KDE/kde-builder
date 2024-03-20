(supported-cmdline-parameters)=
# Supported command-line parameters

## Generic

(cmdline-pretend)=
`--pretend` (or `--dry-run` or `-p`)  
kde-builder will run through the update and build process, but instead
of performing any actions to update or build, will instead output what
the script would have done (e.g. what commands to run, general steps
being taken, etc.).

```{note}
Simple read-only commands (such as reading file information) may still
be run to make the output more relevant (such as correctly simulating
whether source code would be checked out or updated).
```

```{important}
This option requires that some needed metadata is available, which is
normally automatically downloaded, but downloads are disabled in pretend
mode. If you've never run kde-builder (and therefore, don't have this
metadata), you should run `kde-builder --metadata-only` to download the
required metadata first.
```

(cmdline-include-dependencies)=
`--include-dependencies` (or `-d`), `--no-include-dependencies` (or `-D`)  
This option causes kde-builder to automatically include other KDE and
Qt modules in the build, if required for the modules you have requested
to build on the command line or in your [configuration
file](../chapter_02/configure-data).

The modules that are added are as recorded within the KDE source code
management system. See the section called [](#kde-projects-module-sets).

The corresponding configuration file option is
[include-dependencies](#conf-include-dependencies).

This option is enabled by default.

(cmdline-ignore-modules)=
`--ignore-modules` (or `-!`) `module [module ...]`  
Do not include the modules passed on the rest of the command line in the
update/build process (this is useful if you want to build most of the
modules in your [configuration file](../chapter_02/configure-data) and just skip a
few).

Note that this option does not override
[ignore-modules](#conf-ignore-modules) config option in global section.
Instead, it appends it.

(cmdline-run)=
`--run` (or `--start-program`) \[-e\|--exec name\] \[-f\|--fork\] `program [parameters ...]`  
This option interprets the next item on the command line as a program to
run, and kde-builder will then finish reading the configuration file,
source the prefix.sh to apply environment variables, and then execute
the given program.

(cmdline-revision)=
`--revision` \<id\>  
This option causes kde-builder to checkout a specific numbered revision
for each Git module, overriding any [branch](#conf-branch),
[tag](#conf-tag), or [revision](#conf-revision) options already set for
these modules.

This option is likely not a good idea, and is only supported for
compatibility with older scripts.

(cmdline-delete-my-patches)=
`--delete-my-patches`, `--no-delete-my-patches`  
This option is used to let kde-builder delete source directories that
may contain user data, so that the module can be re-downloaded. This
would normally only be useful for KDE developers (who might have local
changes that would be deleted).

You should not use this option normally, kde-builder will prompt to be
re-run with it if it is needed.

(cmdline-delete-my-settings)=
`--delete-my-settings`, `--no-delete-my-settings`  
This option is used to let kde-builder overwrite existing files which
may contain user data.

This is currently only used for xsession setup for the login manager.
You should not use this option normally, kde-builder will prompt to be
re-run with it if it is needed.

(cmdline-option-name)=
`--<option-name>` \<value\>  
You can use this option to override an option in your [configuration
file](../chapter_02/configure-data) for every module. For instance, to override the
[log-dir](#conf-log-dir) option, you would do: `--log-dir /path/to/dir`.

```{note}
This feature can only be used for option names already recognized by
kde-builder, that are not already supported by relevant command line
options. For example the [async](#conf-async) configuration file option
has specific [--async](#cmdline-async) and [--no-async](#cmdline-async)
command line options that are preferred by kde-builder.
```

(cmdline-set-module-option-value)=
`--set-module-option-value <module-name>,<option-name>,<option-value>`  
You can use this option to override an option in your [configuration
file](../chapter_02/configure-data) for a specific module.

## Resuming and stopping

(cmdline-resume-from)=
`--resume-from` (or `--from` or `-f`) \<module\>  
This option is used to resume the build starting from the given module.
You should not specify other module names on the command line.

```{note}
If you want to avoid source updates when resuming, simply pass
`--no-src` in addition to the other options.
```

See also: [--resume-after](#cmdline-resume-after) and the section called
[](#resuming-failed). You would prefer to use this command line
option if you have fixed the build error and want kde-builder to
complete the build.

(cmdline-resume-after)=
`--resume-after` (or `--after` or `-a`) \<module\>  
This option is used to resume the build starting after the given module.
You should not specify other module names on the command line.

```{note}
If you want to avoid source updates when resuming, simply pass
`--no-src` in addition to the other options.
```

See also: [--resume-from](#cmdline-resume-from) and the section called
[](#resuming-failed). You would prefer to use this command line
option if you have fixed the build error and have also built and
installed the module yourself, and want kde-builder to start again with
the next module.

(cmdline-resume)=
`--resume`  
This option can be used to run kde-builder after it has had a build
failure.

It resumes the build from the module that failed, using the list of
modules that were waiting to be built before, and disables source and
metadata updates as well. The use case is when a simple mistake or
missing dependency causes the build failure. Once you correct the error
you can quickly get back into building the modules you were building
before, without fiddling with `--resume-from` and `--stop-before`.

(cmdline-stop-before)=
`--stop-before` (or `--until`) \<module\>  
This option is used to stop the normal build process just *before* a
module would ordinarily be built.

For example, if the normal build list was moduleA, moduleB, moduleC,
then `--stop-before moduleB` would cause kde-builder to only build
`moduleA`.

(cmdline-stop-after)=
`--stop-after` (or `--to`) \<module\>  
This option is used to stop the normal build process just *after* a
module would ordinarily be built.

For example, if the normal build list was moduleA, moduleB, moduleC,
then `--stop-after moduleB` would cause kde-builder to build `moduleA`
and `moduleB`.

(cmdline-stop-on-failure)=
`--stop-on-failure`, `--no-stop-on-failure`  
This option controls if the build will be aborted as soon as a failure
occurs. Default behavior is --stop-on-failure. You may override it if
you wish to press on with the rest of the modules in the build, to avoid
wasting time in case the problem is with a single module.

See also the [stop-on-failure](#conf-stop-on-failure) configuration file
option.

(cmdline-rebuild-failures)=
`--rebuild-failures`  
Use this option to build only those modules which failed to build on a
previous kde-builder run. This is useful if a significant number of
failures occurred mixed with successful builds. After fixing the issue
causing the build failures you can then easily build only the modules
that failed previously.

```{note}
Note that the list of “previously-failed modules” is reset every time a
kde-builder run finishes with some module failures. However, it is not
reset by a completely successful build, so you can successfully rebuild
a module or two and this flag will still work.
```

## Modules information

(cmdline-query)=
`--query` `mode`  
This command causes kde-builder to query a parameter of the modules in
the build list (either passed on the command line or read in from the
configuration file), outputting the result to screen (one module per
line).

This option must be provided with a “mode”, which may be one of the
following:

- `source-dir`, which causes kde-builder to output the full path to
  where the module's source code is stored.

- `build-dir`, which causes kde-builder to output the full path to
  where the module build process occurs.

- `install-dir`, which causes kde-builder to output the full path to
  where the module will be installed.

- `project-path`, which causes kde-builder to output the location of
  the module within the hierarchy of KDE source code repositories. See
  the section called [](#kde-projects-module-sets) for more information on this
  hierarchy.

- `branch`, which causes kde-builder to output the resolved git branch
  that will be used for each module, based on the [tag](#conf-tag),
  [branch](#conf-branch) and [branch-group](#conf-branch-group) settings
  in effect.

- `module-set`, which causes kde-builder to output the name of
  module-set which contains the module. This can be used to generate zsh
  autocompletion cache.

- `build-system`, which causes kde-builder to output the name of build
  system detected for the module. This can be used to debug build system
  auto-detection problems, or when developing tests for specific build
  systems.

- Any option name that is valid for modules in the [configuration
  file](../chapter_04/conf-options-table).

For example, the command
`kde-builder --query branch kactivities kdepim` might end up with
output like:

```
kactivities: master
kdepim: master
```

(cmdline-dependency-tree)=
`--dependency-tree`  
Prints out dependency information on the modules that would be built
using a tree format (recursive). Listed information also includes which
specific commit/branch/tag is depended on and whether the dependency
would be built. Note: the generated output may become quite large for
applications with many dependencies.

(cmdline-dependency-tree-fullpath)=
`--dependency-tree-fullpath`  
Prints out dependency information on the modules that would be built
using a tree format (recursive). In fullpath format. Note: the generated
output may become quite large for applications with many dependencies.

(cmdline-list-installed)=
`--list-installed`  
Print installed modules and exit. This can be used to generate
autocompletion for the --run option.

## Exclude specific action

(cmdline-no-metadata)=
`--no-metadata` (or `-M`)  
Do not automatically download the extra metadata needed for KDE git
modules. The source updates for the modules themselves will still occur
unless you pass [--no-src](#cmdline-no-src) as well.

This can be useful if you are frequently re-running kde-builder since
the metadata does not change very often. But note that many other
features require the metadata to be available. You might want to
consider running kde-builder with the
[--metadata-only](#cmdline-metadata-only) option one time and then using
this option for subsequent runs.

(cmdline-no-src)=
`--no-src` (or `-S`)  
Skip contacting the Git server.

(cmdline-no-build)=
`--no-build`  
Skip the build process.

(cmdline-no-install)=
`--no-install`  
Do not automatically install packages after they are built.

## Only specific action

(cmdline-metadata-only)=
`--metadata-only`  
Only perform the metadata download process. kde-builder normally
handles this automatically, but you might manually use this to allow the
`--pretend` command line option to work.

(cmdline-src-only)=
`--src-only` (or `-s`)  
Only perform the source update.

(cmdline-build-only)=
`--build-only`  
Only perform the build process.

(cmdline-install-only)=
`--install-only`  
If this is the only command-line option, it tries to install all the
modules contained in `log/latest/build-status`. If command-line options
are specified after this option, they are all assumed to be modules to
install (even if they did not successfully build on the last run).

(cmdline-build-system-only)=
`--build-system-only`  
This option causes kde-builder to abort building a module just before
the `make` command would have been run. This is supported for
compatibility with older versions only, this effect is not helpful for
the current KDE build system.

## Build behavior

(cmdline-build-when-unchanged)=
`--build-when-unchanged` (or `--force-build`), `--no-build-when-unchanged` (or `--no-force-build`)  
Enabling this option explicitly disables skipping the build process (an
optimization controlled by the
[build-when-unchanged](#conf-build-when-unchanged) option). This is
useful for making kde-builder run the build when you have changed
something that kde-builder cannot check. This option is enabled by
default.

(cmdline-refresh-build)=
`--refresh-build` (or `-r`)  
Recreate the build system and make from scratch.

(cmdline-reconfigure)=
`--reconfigure`  
Run `cmake` (for KDE modules) or `configure` (for Qt) again, without
cleaning the build directory. You should not normally have to specify
this, as kde-builder will detect when you change the relevant options
and automatically re-run the build setup. This option is implied if
`--refresh-build` is used.

(cmdline-install-dir)=
`--install-dir path`  
This allows you to change the directory where modules will be installed
to. This option implies [`--reconfigure`](#cmdline-reconfigure), but
using [`--refresh-build`](#cmdline-refresh-build) may still be required.

(cmdline-generate-vscode-project-config)=
`--generate-vscode-project-config`, `--no-generate-vscode-project-config`  
Generate a `.vscode` directory with configurations for building and
debugging in Visual Studio Code. This option is disabled by default.

## Script runtime

(cmdline-async)=
`--async`, `--no-async`  
Enables or disables the [asynchronous mode](#conf-async), which can
perform the source code updates and module builds at the same time. If
disabled, the update will be performed in its entirety before the build
starts. Disabling this option will slow down the overall process. If you
encounter IPC errors while running kde-builder try disabling it, and
submitting a [bug report](https://bugs.kde.org/). This option is enabled
by default.

(cmdline-color)=
`--color` (or `--colorful-output`), `--no-color` (or `--no-colorful-output`)  
Enable or disable colorful output. By default, this option is enabled
for interactive terminals.

(cmdline-nice)=
`--nice` (or `--niceness`) \<value\>  
This value adjusts the computer CPU priority requested by kde-builder,
and should be in the range of 0-20. 0 is highest priority (because it is
the least “nice”), 20 is the lowest priority. This option defaults to
10.

(cmdline-rc-file)=
`--rc-file` \<file\>  
The file to read the configuration options from. The default value for
this parameter is `kdesrc-buildrc` (checked in the current working
directory). If this file doesn't exist, `~/.config/kdesrc-buildrc`
(`$XDG_CONFIG_HOME/kdesrc-buildrc`, if `$XDG_CONFIG_HOME` is set) will
be used instead. See also [](../chapter_04/index).

## Setup

(cmdline-initial-setup)=
`--initial-setup`  
Has kde-builder perform the one-time initial setup necessary to prepare
the system for kde-builder to operate, and for the newly-installed KDE
software to run.

This includes:

- Installing known dependencies (on supported Linux distributions)

- Adding required environment variables to `~/.bashrc`

This option is exactly equivalent to using `--install-distro-packages`
`--generate-config` at the same time. In kde-builder (perl
implementation) it additionally uses "--install-distro-packages-perl".

(cmdline-install-distro-packages)=
`--install-distro-packages`  
Installs distro packages (on supported Linux distributions) necessary to
prepare the system for kde-builder to operate, and for the
newly-installed KDE software to run.

See also `--initial-setup`

(cmdline-generate-config)=
`--generate-config`  
Generate the kde-builder configuration file.

See also `--initial-setup`

## Verbosity level

(cmdline-debug)=
`--debug`  
Enables debug mode for the script. Currently, this means that all output
will be dumped to the standard output in addition to being logged in the
log directory like normal. Also, many functions are much more verbose
about what they are doing in debugging mode.

(cmdline-quiet)=
`--quiet` (or `--quite` or `-q`)  
Do not be as noisy with the output. With this switch only the basics are
output.

(cmdline-really-quiet)=
`--really-quiet`  
Only output warnings and errors.

(cmdline-verbose)=
`--verbose`  
Be very descriptive about what is going on, and what kde-builder is
doing.

## Script information

(cmdline-version)=
`--version` (or `-v`)  
Display the program version.

(cmdline-help)=
`--help` (or `-h`)  
Only display simple help on this script.

(cmdline-show-info)=
`--show-info`  
Displays information about kde-builder and the operating system, that
may prove useful in bug reports or when asking for help in forums or
mailing lists.

(cmdline-show-options-specifiers)=
`--show-options-specifiers`  
Print the specifier lines (in the format that GetOpts::Long accepts) for
all command line options supported by the script. This may be used by
developers, for example, for generating zsh autocompletion functions.
