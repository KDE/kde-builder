(conf-options-list)=
# List of available configuration options

Here are the lists of various options, containing the following
information:

- The option name

- The scope of the option: *global*, *module* or *module-set*. Options
  in *module* or/and *module-set* scope can also be defined in *options*
  sections.

- Special comments on the purpose and usage of the option.

(options-global-table)=
## Global scope only options

(conf-async)=
[`async`](conf-async)

Type: Boolean, Default value: True

This option enables the asynchronous mode of operation, where the
source code update and the build process will be performed in parallel,
instead of waiting for all of the source code updates before starting
the build process.

Related command-line option: [--async](#cmdline-async)

(conf-colorful-output)=
[`colorful-output`](conf-colorful-output)

Type: Boolean, Default value: True

Set this option to `false` to disable the colorful output
of kde-builder. Note that kde-builder will not output the color codes
to anything but a terminal (such as xterm, Konsole, or the normal Linux
console).

Related command-line option: [--color](#cmdline-color)

(conf-disable-agent-check)=
[`disable-agent-check`](conf-disable-agent-check)

Type: Boolean, Default value: False

If you are using ssh to download the sources (such as if you are
using the git+ssh protocol), this option controls if kde-builder will
try and make sure that if you are using ssh-agent, it is actually
managing some ssh identities. This is to try and prevent ssh from asking
for your pass phrase for every module.

Related command-line option: --disable-agent-check, --no-disable-agent-check

(conf-git-push-protocol)=
[`git-push-protocol`](conf-git-push-protocol)

Type: String, Possible values: https, git, Default value: git.

This option controls which network protocol to use when pushing to kde project repositories. Normally the very-efficient
`git` protocol is used, but this may be blocked in some networks (e.g. corporate intranets, public Wi-Fi). An alternative
protocol which is much better supported is the `https` protocol used for Internet websites.

If you are using one of these constrained networks you can set this option to `https`. In any other situation you
should not set this option, as the default protocol is most efficient.

```{tip}
You may also need the [http-proxy](#conf-http-proxy) option if an HTTP proxy is also needed for network traffic.
```

This option only applies to modules that are [KDE projects](#kde-projects-module-sets).

```{note}
The protocol for fetching KDE projects is always `https`.
```

(conf-git-repository-base)=
[`git-repository-base`](conf-git-repository-base)

Type: String

This option is used to create a short name to reference a specific
repository base URL in later [module set](#module-sets)
declarations, which is useful for quickly declaring many modules to
build.

You must specify two things (separated by a space): the name to
assign to the base URL, and the actual base URL itself. For example:

```{code-block} text
global
    # other options
    # This is the common path to all kde repositories
    git-repository-base kde-git kde:
end global

# Module declarations

module-set
    # Now you can use the alias you defined earlier, but only in a module-set.
    repository kde-git
    use-modules module1.git module2.git
end module-set
```

The module-set's `use-modules` option created two modules
internally, with kde-builder behaving as if it had read:

```{code-block} shell
module module1
    repository kde:module1.git
end module

module module2
    repository kde:module2.git
end module
```

The `kde:` git repository prefix used above is a shortcut
which will be set up by kde-builder automatically. Note that unlike most other
options, this option can be specified multiple times in order to create
as many aliases as necessary.

```{tip}
It is not required to use this option to take advantage of
module-set, this option exists to make it easy to use the same
repository across many different module sets.
```

(conf-install-login-session)=
[`install-login-session`](conf-install-login-session)

Type: Boolean, Default value: True

If enabled, KDE Builder will invoke session installation script from `plasma-workspace` module. See
[](#installing-login-session) for details.

Related command-line option: --install-login-session, --no-install-login-session

(conf-libpath)=
[`libpath`](conf-libpath)

Type: String

Set this option to set the environment variable
`LD_LIBRARY_PATH` while building. You cannot override this
setting in a module option. The default value is blank, but the paths
`${install-dir}/$LIBNAME` and
`${qt-install-dir}/$LIBNAME` are automatically added. You may
use the tilde (~) for any paths you add using this option.

Related command-line option: --libpath \<path\>

(conf-niceness)=
[`niceness`](conf-niceness)

Type: Integer, Default value: 10

Set this option to a number between 20 and 0. The higher the number,
the lower a priority kde-builder will set for itself, i.e. the higher
the number, the "nicer" the program is.

Related command-line option: [--nice](#cmdline-nice)

(conf-num-cores)=
[`num-cores`](conf-num-cores)

Type: Integer, Default value: Depends on system

This option is defined by kde-builder (when using
`kde-builder --generate-config`), set to be the number of
available CPUs. If kde-builder cannot detect the number of CPUs, this
value is set to 4.

See [](#make-options-example) for an example of this
option's usage.

Related command-line option: --num-cores \<value\>

(conf-num-cores-low-mem)=
[`num-cores-low-mem`](conf-num-cores-low-mem)

Type: Integer, Default value: Depends on system

This option is defined by kde-builder (when using
`kde-builder --generate-config`), set to be the number of
CPUs that is deemed safe for heavyweight or other highly-intensive
modules, such as `qtwebengine`, to avoid running out of
memory during the build.

The typical calculation is one CPU core for every 2 gigabytes (GiB)
of total memory. At least 1 core will be specified, and no more than
`num-cores` cores will be specified.

Although this option is intended to support Qt modules, you can use
it for your any module in the same way that `num-cores` is used.

If kde-builder cannot detect available memory then this value will be set to 2.

Related command-line option: --num-cores-low-mem \<value\>

(conf-persistent-data-file)=
[`persistent-data-file`](conf-persistent-data-file)

Type: String

Use this option to change where kde-builder stores its persistent
data. The default is to store this data in a file called
`.kdesrc-build-data`, placed in the same directory as the
configuration file in use. If the global configuration file is in use,
it will be saved to `~/.local/state/kdesrc-build-data`
(`$XDG_STATE_HOME/kdesrc-build-data`, if `$XDG_STATE_HOME` is set). If you have multiple available
configurations in the same directory, you may want to manually set this
option, so that different configurations do not end up with conflicting
persistent data.

Related command-line option: --persistent-data-file \<file\>

(conf-source-when-start-program)=
[`source-when-start-program`](conf-source-when-start-program)

Type: String

With this option, you can specify a path to shell file, which will be sourced before the module is launched with `--run` option.
For example, you can use it to set `QT_LOGGING_RULES` and `QT_MESSAGE_PATTERN` variables, so you could customize the debug output.

Related command line option: [--source-when-start-program](cmdline-source-when-start-program)

(conf-ssh-identity-file)=
[`ssh-identity-file`](conf-ssh-identity-file)

Type: String

Set this option to control which private SSH key file is passed to
the `ssh-add` command when kde-builder is downloading source
code from repositories that require authentication. 

See also: the section called [](#ssh-agent-reminder).

(conf-use-idle-io-priority)=
[`use-idle-io-priority`](conf-use-idle-io-priority)

Type: Boolean, Default value: False

Use lower priority for disk and other I/O, which can significantly
improve the responsiveness of the rest of the system at the expense of
slightly longer running times for kde-builder.

Related command-line option: --use-idle-io-priority, --no-use-idle-io-priority

(conf-use-inactive-modules)=
[`use-inactive-modules`](conf-use-inactive-modules)

Type: Boolean, Default value: False

Allow kde-builder to also clone and pull from repositories marked as inactive.

Related command-line option: --use-inactive-modules, --no-use-inactive-modules

(option-table)=
## All scopes (module, module-set and global) options

(conf-binpath)=
[`binpath`](conf-binpath)

Type: String

Set this option to set the environment variable PATH while building.
You cannot override this setting in a module option. The default value
is the $`PATH` that is set when the script starts. This
environment variable should include the colon-separated paths of your
development toolchain. The paths `${install-dir}/bin` and
`${qt-install-dir}/bin` are automatically added. You may use
the tilde (~) for any paths you add using this option.

Related command-line option: --binpath \<path\>

(conf-branch)=
[`branch`](conf-branch)

Type: String, Default value: master

Checkout the specified branch instead of the default branch.

```{note}
For most KDE modules you probably wish to use the [branch-group](#conf-branch-group) option instead and use this
option for case-by-case exceptions.
```

Related command-line option: --branch \<value\>

(conf-branch-group)=
[`branch-group`](conf-branch-group)

Type: String

Set this option to a general group from which you want modules to be chosen.

For modules that are kde-projects, kde-builder will determine the
actual branch to use automatically based on rules encoded by the KDE
developers (these rules may be viewed in the
`sysadmin/repo-metadata` repository. After a branch is determined that branch is used as if you
had specified it yourself using the [branch](#conf-branch)
option.

This is useful if you're just trying to maintain up-to-date on some
normal development track without having to pay attention to all the
branch name changes.

Note that if you _do_ choose a `branch` yourself,
that it will override this setting. The same is true of other specific
branch selection options such as [tag](#conf-tag).

```{note}
This option only applies to `kde-projects` modules. See also the section called [](#kde-projects-module-sets).
```

Related command-line option: --branch-group \<value\>

(conf-build-dir)=
[`build-dir`](conf-build-dir)

Type: String, Default value: `~/kde/build`

Use this option to change the directory to contain the built sources.
There are three different ways to use it:

1. Relative to the source directory (see the [source-dir](#conf-source-dir) option).
This is selected if you type a directory name that does not start with a
tilde (~) or a slash (/).

2. Absolute path. If you specify a path that begins with a /, then
that path is used directly. For example,
`/tmp/kde-obj-dir/`.

3. Relative to your home directory. If you specify a path that
begins with a ~, then the path is used relative to your home directory,
analogous to the shell's tilde-expansion. For example,
`~/builddir` would set the build directory to
`/home/user-name/builddir`.

This option can be changed per module.

Related command-line option: --build-dir \<path\>

(conf-build-when-unchanged)=
[`build-when-unchanged`](conf-build-when-unchanged)

Type: Boolean, Default value: True

Control whether kde-builder always tries to build a module that has
not had any source code updates.

If set to `true`, kde-builder always attempts the build
phase for a module, even if the module did not have any source code
updates. With this value it will more likely lead to a correct build.

If set to `false`, kde-builder will only attempt to run
the build phase for a module if the module has a source code update, or
in other situations where it is likely that a rebuild is actually
required. This can save time, especially if you run kde-builder daily,
or more frequently.

```{important}
This feature is provided as an optimization only. Like many other
optimizations, there are trade-offs for the correctness of your
installation. For instance, changes to the qt modules may
cause a rebuild of other modules to be necessary, even if the source
code doesn't change at all.
```

Related command-line option: [--build-when-unchanged](#cmdline-build-when-unchanged)

(conf-cmake-generator)=
[`cmake-generator`](conf-cmake-generator)

Type: String, Default value: Unix Makefiles

Specify which generator to use with CMake. Currently both
`Ninja` and `Unix Makefiles` as well as extra
generators based on them like `Eclipse CDT4 - Ninja` are
supported. Invalid (unsupported) values are ignored and treated as if
unset.

Note that if a valid generator is also specified through [cmake-options](#conf-cmake-options)
it will override the value for `cmake-generator`.

Related command-line option: --cmake-generator \<value\>

(conf-cmake-toolchain)=
[`cmake-toolchain`](conf-cmake-toolchain)

Type: String

Specify a toolchain file to use with CMake.

When a valid toolchain file is configured, kde-builder will _no
longer set environment variables automatically_. You can use [set-env](#conf-set-env),
[binpath](#conf-binpath) and [libpath](#conf-libpath) to fix up the environment
manually if your toolchain file does not work out of the box with
kde-builder. Refer to [the overview of standard flags added by kde-builder](#kde-builder-std-flags)
for more information.

Note that if a valid toolchain is also specified through [cmake-options](#conf-cmake-options)
it will override the value for `cmake-toolchain`.

Related command-line option: --cmake-toolchain \<value\>

(conf-cmake-options)=
[`cmake-options`](conf-cmake-options)

Type: String

Appends to global options for the default buildsystem, overrides
global for other buildsystems.

Use this option to specify what flags to pass to CMake when creating
the build system for the module. When this is used as a global option,
it is applied to all modules that KDE Builder builds. When used as a
module option, it is added to the end of the global options. This allows
you to specify common CMake options in the global section.

If a valid generator is specified among the listed options it will
override the value of [cmake-generator](#conf-cmake-generator). Invalid (unsupported)
generators are ignored and will not be passed to CMake.

If a valid toolchain file is specified among the listed options it
will override the value of [cmake-toolchain](#conf-cmake-toolchain). Invalid toolchains are
ignored and will not be passed to CMake.

Since these options are passed directly to the CMake command line,
they should be given as they would be typed into CMake. For example:

```text
cmake-options -DCMAKE_BUILD_TYPE=RelWithDebInfo
```

Since this is a hassle, kde-builder takes pains to ensure that as
long as the rest of the options are set correctly, you should be able to
leave this option blank. (In other words, _required_ CMake
parameters are set for you automatically)

Related command-line option: --cmake-options \<value\>

(conf-compile-commands-export)=
[`compile-commands-export`](conf-compile-commands-export)

Type: Boolean, Default value: True

Enables the generation of a `compile_commands.json` via
CMake inside the build directory.

Related command-line option: --compile-commands-export, --no-compile-commands-export

(conf-compile-commands-linking)=
[`compile-commands-linking`](conf-compile-commands-linking)

Type: Boolean, Default value: False

Enables the creation of symbolic links from
`compile_commands.json` generated via CMake inside the build
directory to the matching source directory.

Related command-line option: --compile-commands-linking, --no-compile-commands-linking

(conf-configure-flags)=
[`configure-flags`](conf-configure-flags)

Type: String

Appends to global options for the default buildsystem, overrides
global for other buildsystems.

Use this option to specify what flags to pass to ./configure when
creating the build system for the module. When this is used as a
global-option, it is applied to all modules that this script builds.

To change configuration settings for KDE modules, see [cmake-options](#conf-cmake-options).

Related command-line option: --configure-flags \<value\>

(conf-custom-build-command)=
[`custom-build-command`](conf-custom-build-command)

Type: String

This option can be set to run a different command (other than
`make`, for example) in order to perform the build process.
kde-builder should in general do the right thing, so you should not
need to set this option. However it can be useful to use alternate build
systems.

The value of this option is used as the command line to run, modified
by the [make-options](#conf-make-options) option as
normal.

Related command-line option: --custom-build-command \<value\>

(conf-cxxflags)=
[`cxxflags`](conf-cxxflags)

Type: String

Appends to global options for the default buildsystem, overrides
global for other buildsystems.

Use this option to specify what flags to use for building the module.
This option is specified here instead of with [configure-flags](#conf-configure-flags)
or [cmake-options](#conf-cmake-options) because this option will
also set the environment variable `CXXFLAGS` during the build
process.

```{note}
Possibly outdated info about KDE 4.
```

Note that for KDE 4 and any other modules that use CMake, it is
necessary to set the CMAKE_BUILD_TYPE option to `none` when
configuring the module. This can be done using the [cmake-options](#conf-cmake-options) option.

Related command-line option: --cxxflags \<value\>

(conf-dest-dir)=
[`dest-dir`](conf-dest-dir)

Type: String

Use this option to change the name a module is given on disk. For
example, if your module was extragear/network, you could rename it to
extragear-network using this option. Note that although this changes the
name of the module on disk, it is not a good idea to include directories
or directory separators in the name as this will interfere with any [build-dir](#conf-build-dir)
or [source-dir](#conf-source-dir) options.

Related command-line option: --dest-dir \<path\>

(conf-do-not-compile)=
[`do-not-compile`](conf-do-not-compile)

Type: String

Use this option to select a specific set of directories not to be
built in a module (instead of all of them). The directories not to build
should be space-separated.

Note that the sources to the programs will still be downloaded.

For example, to disable building the `codeeditor` and
`minimaltest` directories of the
`syntaxhighlighting` framework, you would add
`do-not-compile codeeditor minimaltest` compiling, you would
add "do-not-compile juk kscd" to your syntaxhighlighting options.

See the section called [](#not-compiling) for an example.

Related command-line option: --do-not-compile \<value\>

(conf-git-user)=
[`git-user`](conf-git-user)

Type: String

This option is intended for KDE developers. If set, it will be used
to automatically setup identity information for the git config
for _newly downloaded_ modules.

Specifically, the user's name and email fields for each new
repository are filled in to the values set by this option.

The value must be specified in the form
`User Name <email@example.com>`.

(conf-http-proxy)=
[`http-proxy`](conf-http-proxy)

Type: String

This option, if set, uses the specified URL as a proxy server to use
for any HTTP network communications (for example, when downloading the
[KDE project database](#kde-projects-module-sets)).

In addition, kde-builder will try to ensure that the tools it
depends on also use that proxy server, if possible, by setting the
`http_proxy` environment variable to the indicated server,
_if that environment variable is not already set_.

Related command-line option: --http-proxy \<value\>

(conf-directory-layout)=
[`directory-layout`](conf-directory-layout)

Type: String, Valid values: `flat`, `invent`, `metadata`, Default value: flat

This option is used to configure the layout which kde-builder should
use when creating source and build directories.

The `flat` layout will group all modules directly
underneath the top level source and build directories. For example,
`source/extragear/network/telepathy/ktp-text-ui` in the
`metadata` layout would be `source/ktp-text-ui`
using the `flat` layout instead.

The `invent` layout creates a directory hierarchy
mirroring the relative paths of repositories on [invent.kde.org](https://invent.kde.org/). For example
`source/kde/applications/kate` in the `metadata`
layout would be `source/utilities/kate` using the
`invent` layout instead. This layout only affects KDE
projects. It is a good choice for people starting out with
kde-builder.

Finally, the `metadata` layout is the same as the old
default behaviour. This layout organises KDE projects according to the
project paths specified in the project metadata for these modules. This
is a good choice if you want a directory layout which tracks with
certain KDE processes, but note that this path is therefore not always
stable. As a result, kde-builder may abandon an old copy of the
repository and clone a new one for a project due to changes in the
project metadata.

Related command-line option: --directory-layout \<value\>

(conf-generate-vscode-project-config)=
[`generate-vscode-project-config`](conf-generate-vscode-project-config)

Type: Boolean, Default value: False

Module setting overrides global

Set this option to `true` to make kde-builder create VS
Code project files (.vscode directory) in the module source
directory.

The .vscode folder will be created in the project source directory,
only if it does not already exist. The configurations will enable the
use of LSP, building, debugging, and running the project from within VS
Code.

The configuration also recommends extensions to install that are
useful for working on most KDE projects.

Related command-line option: [--generate-vscode-project-config](#cmdline-generate-vscode-project-config)

(conf-include-dependencies)=
[`include-dependencies`](conf-include-dependencies)

Type: Boolean, Default value: True

Controls if kde-builder will include known dependencies of this
module in its build, without requiring you to mention those dependencies
(even indirectly).

```{note}
This option only works for [kde-project based
modules](#kde-projects-module-sets), and requires that the metadata maintained by the KDE
developers is accurate for your selected [branch-group](#conf-branch-group).
```

This is to support building applications that need versions of Qt or
Plasma more recent than supported on common operating systems.

Related command-line option: [--include-dependencies](#cmdline-include-dependencies)

(conf-install-after-build)=
[`install-after-build`](conf-install-after-build)

Type: String, Default value: True

This option is used to install the package after it successfully
builds. You can also use the [--no-install](#cmdline-no-install) command line
flag.

Related command-line option: --install-after-build, --no-install-after-build

(conf-install-dir)=
[`install-dir`](conf-install-dir)

Type: String, Default value: `~/kde/usr`

This option controls where to install the module after it is built.
If you change this to a directory needing root access, you may want to
read about the [make-install-prefix](#conf-make-install-prefix) option as
well.

Changing this option for specific module allows you to install it to
a different directory than where the KDE Platform libraries are
installed, such as if you were using kde-builder only to build
applications.

You can use `${MODULE}` or `$MODULE` in the
path to have them expanded to the module's name.

Related command-line option: [--install-dir](#cmdline-install-dir)

(conf-libname)=
[`libname`](conf-libname)

Type: String, Default value: Auto detected

Set this option to change the default name of the installed library
directory inside ${install-dir} and ${qt-install-dir}. On many systems
this is either "lib" or "lib64". Auto-detection is attempted to set the
correct name by default, but if the guess is wrong then it can be
changed with this setting.

Related command-line option: --libname \<value\>

(conf-log-dir)=
[`log-dir`](conf-log-dir)

Type: String

Use this option to change the directory used to hold the log files
generated by KDE Builder.

Related command-line option: --log-dir \<path\>

(conf-make-install-prefix)=
[`make-install-prefix`](conf-make-install-prefix)

Type: String

Set this variable to a space-separated list, which is interpreted as
a command and its options to precede the `make install`
command used to install modules. This is useful for installing packages
with sudo for example, but please be careful while dealing with root
privileges.

Related command-line option: --make-install-prefix \<value\>

(conf-make-options)=
[`make-options`](conf-make-options)

Type: String

Set this variable in order to pass command line options to the
`make` command. This is useful for programs such as
[distcc](https://github.com/distcc/distcc) or systems with more
than one processor core.

Note that not all supported build systems use `make`. For
build systems that use `ninja` for build (such as the [Meson build system](#conf-override-build-system)),
see the [ninja-options](#conf-ninja-options) setting.

Related command-line option: --make-options \<value\>

(conf-manual-build)=
[`manual-build`](conf-manual-build)

Type: Boolean, Default value: False

Set the option value to `true` to keep the build process
from attempting to build this module. It will still be kept up-to-date
when updating from git. This option is exactly equivalent to the [--no-build](#cmdline-no-build) command line
option.

(conf-manual-update)=
[`manual-update`](conf-manual-update)

Type: Boolean, Default value: False

Set the option value to `true` to keep the build process
from attempting to update (and by extension, build or install) this
module. If you set this option for a module, then you have essentially
commented it out.

(conf-ninja-options)=
[`ninja-options`](conf-ninja-options)

Type: String

Set this variable in order to pass command line options to the
`ninja` build command. This can be useful to enable "verbose"
output or to manually reduce the number of parallel build jobs that
`ninja` would use.

Related command-line option: --ninja-options \<value\>

(conf-override-build-system)=
[`override-build-system`](conf-override-build-system)

Type: String, Default value: Auto detected, Valid values: KDE, Qt,
qmake, generic, autotools, meson

Normally kde-builder will detect the appropriate build system to use
for a module after it is downloaded. This is done by checking for the
existence of specific files in the module's source directory.

Some modules may include more than one required set of files, which
could confuse the auto-detection. In this case you can manually specify
the correct build type.

Currently supported build types that can be set are:

```{glossary}
KDE
  Used to build KDE modules. In reality it can be used to build almost
  any module that uses CMake but it is best not to rely on this.

Qt
  Used to build the Qt library itself.

qmake
  Used to build Qt modules that use qmake-style `.pro` files.

generic
  Used to build modules that use plain Makefiles and that do not
  require any special configuration.

autotools
  This is the standard configuration tool used for most Free and
  open-source software not in any of the other categories.

meson
  This is a [relatively new tool](https://mesonbuild.com)
  gaining popularity as a replacement for the autotools and may be
  required for some non-KDE modules.
```

Related command-line option: --override-build-system \<value\>

(conf-purge-old-logs)=
[`purge-old-logs`](conf-purge-old-logs)

Type: Boolean, Default value: True

This option controls whether old log directories are automatically
deleted or not.

Related command-line option: --purge-old-logs, --no-purge-old-logs

(conf-qmake-options)=
[`qmake-options`](conf-qmake-options)

Type: String

Any options specified here are passed to the `qmake`
command, for modules that use the `qmake` build system. For
instance, you can use the `PREFIX=/path/to/qt` option to
qmake to override where it installs the module.

Related command-line option: --qmake-options \<value\>

(conf-qt-install-dir)=
[`qt-install-dir`](conf-qt-install-dir)

Type: String

This option controls where to install qt modules after build. If you
do not specify this option, kde-builder will assume that Qt is provided
by the operating system.

Related command-line option: --qt-install-dir \<path\>

(conf-remove-after-install)=
[`remove-after-install`](conf-remove-after-install)

Type: String, Valid values: none, builddir, all, Default value: none

If you are low on hard disk space, you may want to use this option in
order to automatically delete the build directory (or both the source
and build directories for one-time installs) after the module is
successfully installed.

Possible values for this option are:

- none - Do not delete anything.
- builddir - Delete the build directory, but not the source.
- all - Delete both the source code and build directory.

Note that using this option can have a significant detrimental impact
on both your bandwidth usage (if you use \<all\>) and the time taken
to compile KDE software, since kde-builder will be unable to perform
incremental builds.

Related command-line option: --remove-after-install \<value\>

(conf-repository)=
[`repository`](conf-repository)

Type: String

This option is used to specify the git repository to download the
source code for the module.

(conf-revision)=
[`revision`](conf-revision)

Type: String

If this option is set to a value other than 0 (zero), kde-builder
will force the source update to bring the module to the exact revision
given, even if options like [branch](#conf-branch) are in
effect. If the module is already at the given revision then it will not
be updated further unless this option is changed or removed from the
configuration.

Related command-line option: [--revision](#cmdline-revision)

(conf-run-tests)=
[`run-tests`](conf-run-tests)

Type: Boolean, Default value: False

If set to `true`, then the module will be built with
support for running its test suite, and the test suite will be executed
as part of the build process. kde-builder will show a simple report of
the test results. This is useful for developers or those who want to
ensure their system is setup correctly.

Related command-line option: --run-tests, --no-run-tests

(conf-set-env)=
[`set-env`](conf-set-env)

Type: String

This option accepts a space-separated set of values, where the first
value is the environment variable to set, and the rest of the values is
what you want the variable set to. For example, to set the variable
`MYTEXT` to "helloworld", you would put in the appropriate
section this line:

```
set-env MYTEXT helloworld
```

This option is special in that it can be repeated without overriding
earlier set-env settings in the same section of the
[configuration file](../getting-started/configure-data). This way you can set more
than one environment variable per module (or globally).

(conf-source-dir)=
[`source-dir`](conf-source-dir)

Type: String, Default value: `~/kde/src`

This option is used to set the directory on your computer to store
the sources at. You may use the tilde (~) to represent the home
directory if using this option.

Related command-line option: --source-dir \<path\>

(conf-stop-on-failure)=
[`stop-on-failure`](conf-stop-on-failure)

Type: Boolean, Default value: True

Setting this option to `false` allows the script to
continue execution after an error occurs during the build or install
process.

Related command-line option: [--stop-on-failure](#cmdline-stop-on-failure)

(conf-tag)=
[`tag`](conf-tag)

Type: String

Use this option to download a specific release of a module.

_Note:_ The odds are very good that you _do not want_
to use this option. KDE releases are available in tarball form from the
[KDE download site](https://download.kde.org/).

Related command-line option: --tag \<value\>

(conf-use-clean-install)=
[`use-clean-install`](conf-use-clean-install)

Type: Boolean, Default value: False

Set this option to `true` in order to have kde-builder
run `make uninstall` directly before running
`make install`.

This can be useful in ensuring that there are not stray old library
files, CMake metadata, etc. that can cause issues in long-lived KDE
installations. However this only works on build systems that support
`make uninstall`.

Related command-line option: --use-clean-install,
--no-use-clean-install

(options-phase-selection-table)=
## Phase selection options

These options do not require any value (except "filter-out-phases").
They are applied if they are presented in a section.

(conf-no-src)=
[`no-src`](conf-no-src)

Remove _update_ phase. The other phases that were
presented will still be processed.

Related command-line option: [--no-src](#cmdline-no-src)

(conf-no-install)=
[`no-install`](conf-no-install)

Remove _install_ phase. The other phases that were
presented will still be processed.

Related command-line option: [--no-install](#cmdline-no-install)

(conf-no-tests)=
[`no-tests`](conf-no-tests)

Remove _test_ phase. The other phases that were presented
will still be processed.

Related command-line option: --no-tests

(conf-no-build)=
[`no-build`](conf-no-build)

Remove _build_ phase. The other phases that were presented
will still be processed.

Related command-line option: [--no-build](#cmdline-no-build)

(conf-build-only)=
[`build-only`](conf-build-only)

If had _build_ phase, remove any other phases. Otherwise,
remove all phases.

Related command-line option: [--build-only](#cmdline-build-only)

(conf-install-only)=
[`install-only`](conf-install-only)

If had _install_ phase, remove any other phases.
Otherwise, remove all phases.

Related command-line option: [--install-only](#cmdline-install-only)

(conf-uninstall)=
[`uninstall`](conf-uninstall)

If had _uninstall_ phase, remove any other phases.
Otherwise, remove all phases.

Related command-line option: --uninstall

(conf-filter-out-phases)=
[`filter-out-phases`](conf-filter-out-phases)

Remove those phases that are listed (space separated) in this
option. The other phases that were presented will still be
processed.

(options-module-set-table)=
## Modules selection options

(conf-ignore-modules)=
[`ignore-modules`](conf-ignore-modules)

Scope: global, module-set

Type: String

Note that when specified in global section,
[--ignore-modules](#cmdline-ignore-modules) cmdline option does
not override this, but instead appends.

Modules named by this option, which would be chosen by kde-builder
due to a [use-modules](#conf-use-modules) option, are instead
skipped entirely. Use this option when you want to build an entire
[kde-projects](#kde-projects-module-sets) project grouping
_except for_ some specific modules.

The option value does not necessarily have to name the module
directly. Any module that has full consecutive parts of its
[KDE projects module path](#kde-projects-module-sets) match one
of the option values will be ignored, so you can ignore multiple modules
this way.

For example, an option value of \<libs\> would result in both
`kde/kdegraphics/libs` and `playground/libs` being
excluded (though not `kde/kdelibs` since the full part
“kdelibs” is what is compared).

```{tip}
See also [](#example-ignoring-a-module).
```

Related command-line option: [--ignore-modules](#cmdline-ignore-modules)

(conf-use-modules)=
[`use-modules`](conf-use-modules)

Scope: module-set

Type: String

This option allows you to easily specify many different modules to
build at the same point in [the configuration file](./kdesrc-buildrc-overview).

Every identifier passed to this option is internally converted to a
kde-builder module, with a [repository](#conf-repository) option set to the
module-set's repository combined with the identifier name in order to
setup the final repository to download from. All other options that are
assigned in the module-set are also copied to the generated modules
unaltered.

The order that modules are defined in this option is important,
because that is also the order that kde-builder will process the
generated modules when updating, building, and installing. All modules
defined in the given module-set will be handled before kde-builder
moves to the next module after the module-set.

If you need to change the options for a generated module, simply
declare the module again after it is defined in the module-set, and set
your options as needed. Although you will change the options set for the
module this way, the module will still be updated and built in the order
set by the module-set (i.e. you can't reorder the build sequence doing
this).

```{important}
The name to use for the module if you do this is simply the name that
you passed to `use-modules`, with the exception that any `.git` is removed.
```

See the section called [](#module-sets) and [git-repository-base](#conf-git-repository-base)
for a description of its use and an example.
