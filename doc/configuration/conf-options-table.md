(conf-options-list)=
# List of available configuration options

Here are the lists of various options, containing the following
information:

- The option name

- The scope of the option: *global*, *project* or *group*. Options
  in *project* or/and *group* scope can also be defined in *override*
  nodes.

- Special comments on the purpose and usage of the option.

(options-global-table)=
## Global scope only options

(conf-async)=
[`async`](conf-async)

Type: Boolean, Default value: True

This option enables the asynchronous mode of operation, where the
source code update and the build process will be performed in parallel,
instead of waiting for all the source code updates before starting
the build process.

Related command-line option: [--async](#cmdline-async)

(conf-check-self-updates)=
[`check-self-updates`](conf-check-self-updates)

Type: Boolean, Default value: True

If this option is enabled, kde-builder will periodically (once a week) check
if its version is outdated compared to the version available in its repository.
If it is, the warning message will be shown in the terminal.

Related command-line option: [--check-self-updates](#cmdline-check-self-updates)

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
for your pass phrase for every project.

Related command-line option: --disable-agent-check, --no-disable-agent-check

(conf-git-push-protocol)=
[`git-push-protocol`](conf-git-push-protocol)

Type: String, Possible values: https, git, Default value: git.

This option controls which network protocol to use when pushing to kde project repositories. Normally the very-efficient
`git` protocol is used, but this may be blocked in some networks (e.g. corporate intranets, public Wi-Fi). An alternative
protocol which is much better supported is the `https` protocol used for Internet websites.

If you are using one of these constrained networks you can set this option to `https`. In any other situation you
should not set this option, as the default protocol is most efficient.

This option only applies to projects that are [KDE projects](#kde-projects-groups).

```{note}
The protocol for fetching KDE projects is always `https`.
```

(conf-git-repository-base)=
[`git-repository-base`](conf-git-repository-base)

Type: String

This option is used to create a short name to reference a specific
repository base URL in later [group](#groups)
declarations, which is useful for quickly declaring many projects to
build. Only useful if you want to declare your own group of projects, not hosted on invent.kde.org.

You must specify two things (separated by a space): the name to
assign to the base URL, and the actual base URL itself. For example:

```{code-block} yaml
global:
  # other options
  # This is the common path to all Linus Torvald's repositories on GitHub
  git-repository-base: torv-gh https://github.com/torvalds/

# Project declarations

group torvalds-group1:
  # Now you can use the alias you defined earlier
  repository: torv-gh
  use-projects:
    - uemacs
    - libgit2
```

The group's `use-projects` option created two projects
internally, with kde-builder behaving as if it had read:

```{code-block} yaml
project uemacs:
  repository: https://github.com/torvalds/uemacs

project libgit2:
  repository: https://github.com/torvalds/libgit2
```

```{Tip}
If your personal project is hosted on invent.kde.org, you do not need to add any git repository bases.
Use the `kde:` git repository prefix. It is a shortcut which will be set up by kde-builder automatically.
```

Note that unlike most other
options, this option can be specified multiple times in order to create
as many aliases as necessary.

```{note}
Todo: Check that git-repository-base can be set as a list in kde-builder.yaml.
```

```{tip}
It is not required to use this option to take advantage of
group, this option exists to make it easy to use the same
repository across many different groups.
```

See also [repository](#conf-repository) option.

(conf-install-login-session)=
[`install-login-session`](conf-install-login-session)

Type: Boolean, Default value: True

If enabled, KDE Builder will invoke session installation script from `plasma-workspace` project. See
[](#installing-login-session) for details.

Related command-line option: --install-login-session, --no-install-login-session

(conf-libpath)=
[`libpath`](conf-libpath)

Type: String

Set this option to set the environment variable
`LD_LIBRARY_PATH` while building. You cannot override this
setting in a project option. The default value is blank, but the paths
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

Type: Integer, Valid values: `1` - `<maximum on your system>`, `auto` Default value: auto

This option defines a number of CPU cores that will be used when compiling projects. If set to "auto", and kde-builder cannot detect the number of CPUs,
and build system does not support detecting number of cores to use automatically, this value will be set to maximum number of available cores,
multiplied by 0.8.

See [](#make-options-example) for an example of this
option's usage.

Related command-line option: --num-cores \<value\>

(conf-num-cores-low-mem)=
[`num-cores-low-mem`](conf-num-cores-low-mem)

Type: Integer, Valid values: `1` - `<maximum on your system>`, `auto`, Default value: auto

This option defines a number of CPUs that is deemed safe for heavyweight or other highly-intensive
projects, such as `qtwebengine`, to avoid running out of memory during the build.

The typical calculation is one CPU core for every 2 gigabytes (GiB)
of total memory. If set to "auto", at least 1 core will be specified, and no more than
number of actually available cores will be specified.

Although this option is intended to support Qt projects (modules) (it is used in build configs in
[repo-metadata](https://invent.kde.org/sysadmin/repo-metadata)), you can use
it for any of project in the same way that `num-cores` is used.

If kde-builder cannot detect available memory then this value will be set to 4.

Related command-line option: --num-cores-low-mem \<value\>

(conf-persistent-data-file)=
[`persistent-data-file`](conf-persistent-data-file)

Type: String

Use this option to change where kde-builder stores its persistent data.

By default, the location for this data is determined as follows: in case the used config file was from the current working directory, then file for this data 
will be called `kde-builder-persistent-data.json`, placed in the same directory as the configuration file; in case the config from
`~/.config/kde-builder.yaml` was used, then file for this data will be `~/.local/state/kde-builder-persistent-data.json`.

If you have multiple available configurations in the same directory, you may want to manually set this
option, so that different configurations do not end up with conflicting
persistent data.

Related command-line option: --persistent-data-file \<file\>

(conf-source-when-start-program)=
[`source-when-start-program`](conf-source-when-start-program)

Type: String

With this option, you can specify a path to shell file, which will be sourced before the project binary is launched with `--run` option.
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

(conf-use-inactive-projects)=
[`use-inactive-projects`](conf-use-inactive-projects)

Type: Boolean, Default value: False

Some projects in repo-metadata are marked as inactive, and kde-builder ignores them. This option, if enabled, allows kde-builder to consider them as 
active, which can be used to clone archived projects.

Related command-line option: --use-inactive-projects, --no-use-inactive-projects

(option-table)=
## All scopes (project, group and global) options

(conf-binpath)=
[`binpath`](conf-binpath)

Type: String

Set this option to set the environment variable PATH while building.
You cannot override this setting in a project node. The default value
is the $`PATH` that is set when the tool starts. This
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
For most KDE projects you probably wish to use the [branch-group](#conf-branch-group) option instead and use this
option for case-by-case exceptions.
```

Related command-line option: --branch \<value\>

(conf-branch-group)=
[`branch-group`](conf-branch-group)

Type: String

Set this option to a general group from which you want projects to be chosen.

For projects that are kde-projects, kde-builder will determine the
actual branch to use automatically based on rules encoded by the KDE
developers (these rules may be viewed in the
`sysadmin/repo-metadata` repository). After a branch is determined that branch is used as if you
had specified it yourself using the [branch](#conf-branch)
option.

This is useful if you're just trying to maintain up-to-date on some
normal development track without having to pay attention to all the
branch name changes.

Note that if you _do_ choose a `branch` yourself,
than it will override this setting. The same is true of other specific
branch selection options such as [tag](#conf-tag).

```{note}
This option only applies to `kde-projects` projects. See also the section called [](#kde-projects-groups).
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
begins with a "~", then the path is used relative to your home directory,
analogous to the shell's tilde-expansion. For example,
`~/builddir` would set the build directory to
`/home/user-name/builddir`.

This option can be changed per project.

Related command-line option: --build-dir \<path\>

(conf-build-when-unchanged)=
[`build-when-unchanged`](conf-build-when-unchanged)

Type: Boolean, Default value: True

Control whether kde-builder always tries to build a project that has
not had any source code updates.

If set to `true`, kde-builder always attempts the build
phase for a project, even if the project did not have any source code
updates. With this value it will more likely lead to a correct build.

If set to `false`, kde-builder will only attempt to run
the build phase for a project if the project has a source code update, or
in other situations where it is likely that a rebuild is actually
required. This can save time, especially if you run kde-builder daily,
or more frequently.

```{important}
This feature is provided as an optimization only. Like many other
optimizations, there are trade-offs for the correctness of your
installation. For instance, changes to the qt projects (modules) may
cause a rebuild of other projects to be necessary, even if the source
code doesn't change at all.
```

Related command-line option: [--build-when-unchanged](#cmdline-build-when-unchanged)

(conf-cmake-generator)=
[`cmake-generator`](conf-cmake-generator)

Type: String, Default value: Unix Makefiles

The generator that will be used by cmake. You can use `Ninja` or `Unix Makefiles` on Linux.

```{note}
The Extra Generators (like `Kate - Ninja`) are also supported. But note that they are deprecated since cmake version 3.27.
See [documentation](https://cmake.org/cmake/help/latest/manual/cmake-generators.7.html#extra-generators).
```

If you specify invalid value, it will be ignored.

Also note, that you may also specify the generator directly in [cmake-options](#conf-cmake-options) (with "-G" option). In this case, if it is valid, it 
will be used, and not the value from the `cmake-generator`.

Related command-line option: --cmake-generator \<value\>

(conf-cmake-toolchain)=
[`cmake-toolchain`](conf-cmake-toolchain)

Type: String

A toolchain file to be used by cmake.

By default, the toolchain is not set, and kde-builder automatically sets the needed environment variables, see the
[standard flags added by kde-builder](#kde-builder-std-flags).  
In case you specify a valid toolchain file with this option, kde-builder will not set them automatically.
So, if it is required to set some environment variables, you can do so with [set-env](#conf-set-env). Also see [binpath](#conf-binpath) and 
[libpath](#conf-libpath).

Also note, that you may also specify a toolchain in [cmake-options](#conf-cmake-options) (with "-DCMAKE_TOOLCHAIN_FILE" option), and if it is valid, it 
will be used, and not the value from `cmake-toolchain`.

Related command-line option: --cmake-toolchain \<value\>

(conf-cmake-options)=
[`cmake-options`](conf-cmake-options)

Type: String

Appends to global options for the default buildsystem, overrides
global for other buildsystems.

Use this option to specify what flags to pass to CMake when creating
the build system for the project. When this is used as a global option,
it is applied to all projects that KDE Builder builds. When used as a
project option, it is added to the end of the global options. This allows
you to specify common CMake options in the global node.

If you specify a valid (supported) generator in `cmake-options`, it will override the value from [cmake-generator](#conf-cmake-generator) option. In case 
invalid (unsupported) generator was used, it will be ignored and will not be passed to cmake.

If you specify a valid toolchain file in `cmake-options`, it will override the value from [cmake-toolchain](#conf-cmake-toolchain) option. In case invalid 
toolchain was used, it will be ignored and not be passed to cmake.

Since these options are passed directly to the CMake command line,
they should be given as they would be typed into CMake. For example:

```yaml
cmake-options: -DCMAKE_BUILD_TYPE=RelWithDebInfo
```

Since this is a hassle, kde-builder takes pains to ensure that as
long as the rest of the options are set correctly, you should be able to
leave this option blank. (In other words, _required_ CMake
parameters are set for you automatically)

Related command-line option: --cmake-options \<value\>

(conf-compile-commands-export)=
[`compile-commands-export`](conf-compile-commands-export)

Type: Boolean, Default value: True

If enabled, the `compile_commands.json` file will be generated in the build directory.

Related command-line option: --compile-commands-export, --no-compile-commands-export

(conf-compile-commands-linking)=
[`compile-commands-linking`](conf-compile-commands-linking)

Type: Boolean, Default value: True

If enabled, kde-builder will make a symbolic link in the source directory, pointing to the `compile_commands.json` file in the build directory.

Related command-line option: --compile-commands-linking, --no-compile-commands-linking

(conf-configure-flags)=
[`configure-flags`](conf-configure-flags)

Type: String

Appends to global options for the default buildsystem, overrides
global for other buildsystems.

Use this option to specify what flags to pass to ./configure when
creating the build system for the project. When this is used as a
global option, it is applied to all projects that this script builds.

To change configuration settings for KDE projects, see [cmake-options](#conf-cmake-options).

Related command-line option: --configure-flags \<value\>

(conf-custom-build-command)=
[`custom-build-command`](conf-custom-build-command)

Type: String

This option can be set to run a different command (other than
`make`, for example) in order to perform the build process.
kde-builder should in general do the right thing, so you should not
need to set this option. However, it can be useful to use alternate build
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

Use this option to specify what flags to use for building the project.
This option is specified here instead of with [configure-flags](#conf-configure-flags)
or [cmake-options](#conf-cmake-options) because this option will
also set the environment variable `CXXFLAGS` during the build
process.

```{note}
Possibly outdated info about KDE 4.
```

Note that for KDE 4 and any other projects that use CMake, it is
necessary to set the CMAKE_BUILD_TYPE option to `none` when
configuring the project. This can be done using the [cmake-options](#conf-cmake-options) option.

Related command-line option: --cxxflags \<value\>

(conf-dest-dir)=
[`dest-dir`](conf-dest-dir)

Type: String

Use this option to change the name a project is given on disk. For
example, if your project was extragear/network, you could rename it to
extragear-network using this option. Note that although this changes the
name of the project on disk, it is not a good idea to include directories
or directory separators in the name as this will interfere with any [build-dir](#conf-build-dir)
or [source-dir](#conf-source-dir) options.

Related command-line option: --dest-dir \<path\>

(conf-do-not-compile)=
[`do-not-compile`](conf-do-not-compile)

Type: String

Use this option to select a specific set of directories not to be
built in a project (instead of all of them). The directories not to build
should be space-separated.

Note that the sources to the programs will still be downloaded.

For example, to disable building the `codeeditor` and
`minimaltest` directories of the
`syntaxhighlighting` framework, you would add
`do-not-compile: codeeditor minimaltest` compiling, you would
add "do-not-compile: juk kscd" to your syntaxhighlighting options.

See the section called [](#not-compiling) for an example.

Related command-line option: --do-not-compile \<value\>

(conf-git-user)=
[`git-user`](conf-git-user)

Type: String

If set, it will be used
to automatically setup identity information for the git config
for _newly downloaded_ projects.

Specifically, the user's name and email fields for each new
repository are filled in to the values set by this option.

The value must be specified in the form
`User Name <email@example.com>`.

(conf-directory-layout)=
[`directory-layout`](conf-directory-layout)

Type: String, Valid values: `flat`, `invent`, `metadata`, Default value: flat

Controls the structure of source and build directories for the projects when kde-builder creates them.

Assuming your [`source-dir`](conf-source-dir) is set to `~/kde/src`, and you do not redefine [`dest-dir`](conf-dest-dir).

Let's take KCalc as an example. It's metadata.yaml contains the following lines:
```yaml
projectpath: kde/kdeutils/kcalc
repopath: utilities/kcalc
```

If you use `flat` layout, the KCalc source directory will be created in the source-dir in the subfolder, named as a project: `~/kde/src/kcalc`.

If you use `invent` layout, the source directory will be created in the source-dir in the subfolders, as seen in the repository path in
[invent.kde.org](https://invent.kde.org/) (corresponds to the repopath field in metadata): `~/kde/src/utilities/kcalc`.

If you use `metadata` layout, the source directory will be created in the source-dir in the subfolders, as seen in the projectpath field in metadata: 
`~/kde/src/kde/kdeutils/kcalc`.

Please avoid the `metadata` layout, as projectpath field is not stable (and so, when it changes, kde-builder will clone the repo to the new path and 
your work may stay in the source dir from old path) and projectpath is a subject for removal.

Related command-line option: --directory-layout \<value\>

(conf-generate-clion-project-config)=
[`generate-clion-project-config`](conf-generate-clion-project-config)

Type: Boolean, Default value: False

Project setting overrides global

Set this option to `true` to make KDE Builder create CLion project files (.idea directory) in the project source directory.

The .idea folder will be created in the project source directory, only if it does not already exist.

```{note}
You will need to manually create a toolchain named "KDE Builder toolchain" in Clion.  
This cannot be automated, because this configuration is stored in IDE configs, not in the project configs.  
The IDE configs location is dependent on the IDE version.  
If you do not have any toolchanis yet, place the `data/clion/toolchains.xml` file into the configuration
directory of the IDE, i.e. the path would look like `/home/andrew/.config/JetBrains/CLion2024.2/options/linux/toolchains.xml`.
```

Related command-line option: [--generate-clion-project-config](#cmdline-generate-clion-project-config)

(conf-generate-vscode-project-config)=
[`generate-vscode-project-config`](conf-generate-vscode-project-config)

Type: Boolean, Default value: False

Project setting overrides global

Visual Studio Code IDE uses .vscode directory for the project settings in the source directory. If this directory does not exist yet, and this option 
is enabled, it will be created with the build settings and environment from kde-builder, making it easy to just start hacking on a project.

The generated .vscode project will have such conveniences as enabled use of LSP, launch/debug configuration, and will recommend to install extensions that 
may be useful for KDE development.

Related command-line option: [--generate-vscode-project-config](#cmdline-generate-vscode-project-config)

(conf-generate-qtcreator-project-config)=
[`generate-qtcreator-project-config`](conf-generate-qtcreator-project-config)

Type: Boolean, Default value: False

Project setting overrides global

Set this option to `true` to make KDE Builder create files, for ability to easily copy content from them to
Qt Creator configuration. They are generated to `.qtcreator` directory.

```{note}
See developer documentation why it is currently not possible to just generate a project configuration like it is possible for other IDEs.  
See the documentation on develop.kde.org on how to configure the Qt Creator manually to replicate KDE Builder environment.  
```

Related command-line option: [--generate-qtcreator-project-config](#cmdline-generate-qtcreator-project-config)

(conf-hold-work-branches)=
[`hold-work-branches`](cmdline-hold-work-branches)

Type: Boolean, Default value: True

Project setting overrides global

This option allows you to skip updating sources for projects that have current branch which name starts with
`work/*` or `mr/*` (for example, `work/your-username/my-awesome-feature`).

This simplifies workflow when you want to work on specific project. If you checkout someone's mr
(see [wiki documentation](https://community.kde.org/Infrastructure/GitLab)), the
branch will be called something like "mr/80", and kde-builder will behave like if you have specified a "no-src" option for that project in the config.

Related command-line option: [--hold-work-branches](#cmdline-hold-work-branches)

(conf-include-dependencies)=
[`include-dependencies`](conf-include-dependencies)

Type: Boolean, Default value: True

Controls if kde-builder will include known dependencies of this
project in its build, without requiring you to mention those dependencies
(even indirectly).

```{note}
This option only works for [kde-project based
projects](#kde-projects-groups), and requires that the metadata maintained by the KDE
developers is accurate for your selected [branch-group](#conf-branch-group).
```

This is to support building applications that need versions of Qt or
Plasma more recent than supported on common operating systems.

Related command-line option: [--include-dependencies](#cmdline-include-dependencies)

(conf-install-dir)=
[`install-dir`](conf-install-dir)

Type: String, Default value: `~/kde/usr`

This option controls where to install the project after it is built.
If you change this to a directory needing root access, you may want to
read about the [make-install-prefix](#conf-make-install-prefix) option as
well.

Changing this option for specific project allows you to install it to
a different directory than where the KDE Platform libraries are
installed, such as if you were using kde-builder only to build
applications.

The `${MODULE}` or `$MODULE` substring in the value of this option will be replaced with the project node name.

Related command-line option: [--install-dir](#cmdline-install-dir)

(conf-libname)=
[`libname`](conf-libname)

Type: String, Default value: Auto detected

Controls the installed library directory name inside ${install-dir} and ${qt-install-dir}. Usually it is "lib" or "lib64".
This is auto-detected by default. But in case something is wrong in autodetection, you can set it manually with this option.

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
command used to install projects. This is useful for installing projects
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

(conf-meson-options)=
[`meson-options`](conf-meson-options)

Type: String

Set this option in order to pass command line options to the
`meson` configure command.

Related command-line option: --meson-options \<value\>

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
for a project after it is downloaded. This is done by checking for the
existence of specific files in the project's source directory.

Some projects may include more than one required set of files, which
could confuse the auto-detection. In this case you can manually specify
the correct build type.

Currently supported build types that can be set are:

```{glossary}
KDE
  Used to build KDE projects. In reality it can be used to build almost
  any project that uses CMake but it is best not to rely on this.

Qt
  Used to build the Qt library itself.

qmake
  Used to build Qt projects (modules) that use qmake-style `.pro` files.

generic
  Used to build projects that use plain Makefiles and that do not
  require any special configuration.

autotools
  This is the standard configuration tool used for most Free and
  open-source software not in any of the other categories.

meson
  This is a [relatively new tool](https://mesonbuild.com)
  gaining popularity as a replacement for the autotools and may be
  required for some non-KDE projects.
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
command, for projects that use the `qmake` build system. For
instance, you can use the `PREFIX=/path/to/qt` option to
qmake to override where it installs the project.

Related command-line option: --qmake-options \<value\>

(conf-qt-install-dir)=
[`qt-install-dir`](conf-qt-install-dir)

Type: String

This option controls where to install qt projects (modules) after build. If you
do not specify this option, kde-builder will assume that Qt is provided
by the operating system.

Related command-line option: --qt-install-dir \<path\>

(conf-remove-after-install)=
[`remove-after-install`](conf-remove-after-install)

Type: String, Valid values: none, builddir, all, Default value: none

If you are low on hard disk space, you may want to use this option in
order to automatically delete the build directory (or both the source
and build directories for one-time installs) after the project is
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

This option is used to specify the git repository to download the source code for the project.

By default, it has magic value `kde-projects`, which can be automatically resolved (based on project name)
to the correct url for any project that is presented in KDE Projects Database (a.k.a. repo-metadata).

For all other projects, you need to specify the correct url in this option yourself. 

If using [git-repository-base](conf-git-repository-base), the url is resolved as a prefix name,
followed immediately by the given project name.

(conf-revision)=
[`revision`](conf-revision)

Type: String

If this option is set to a value other than 0 (zero), kde-builder
will force the source update to bring the project to the exact revision
given, even if options like [branch](#conf-branch) are in
effect. If the project is already at the given revision then it will not
be updated further unless this option is changed or removed from the
configuration.

Related command-line option: [--revision](#cmdline-revision)

(conf-run-tests)=
[`run-tests`](conf-run-tests)

Type: Boolean, Default value: False

This option only has effect on the projects using CMake.

Most KDE projects use [KDECmakeSettings](https://invent.kde.org/frameworks/extra-cmake-modules/-/blob/e5682c5ca2e3b73e8829cdb81c056070c60efd42/kde-modules/KDECMakeSettings.cmake#L184),
which enables building the tests by default (`BUILD_TESTING` cmake option is set to `ON`).
Running tests still needs to be done manually or by kde-builder with `run-tests` config option enabled.

If set to `true`, kde-builder will ensure the project is configured with
`BUILD_TESTING` option set to `ON`, and after building the project,
test suite will be executed (by running `<make|ninja> test`).

KDE Builder will show a simple report of
the test results. This is useful for developers or those who want to
ensure their system is set up correctly.

Related command-line option: --run-tests, --no-run-tests

(conf-set-env)=
[`set-env`](conf-set-env)

Type: Dictionary

This option accepts a dictionary, where the key is the environment variable to set, and the value is
what you want the variable to be set to.

See [](changing-environment) for more information.

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

Setting this option to `false` allows the kde-builder to
continue execution after an error occurs during the build or install
process.

Related command-line option: [--stop-on-failure](#cmdline-stop-on-failure)

(conf-tag)=
[`tag`](conf-tag)

Type: String

Use this option to download a specific release of a project.

_Note:_ The odds are very good that you _do not want_
to use this option. KDE releases are available in tarball form from the
[KDE download site](https://download.kde.org/).

Related command-line option: --tag \<value\>

(conf-taskset-cpu-list)=
[`taskset-cpu-list`](conf-taskset-cpu-list)

Type: String

This option is used to limit the number of cpu cores used in build/install process.
It is similar to [num-cores](#conf-num-cores), but is more reliable.
The problem with num-cores is that ninja has an issue to ignore it.
See [this ninja issue](https://github.com/ninja-build/ninja/issues/1441) and 
[this discussion on kde forum](https://discuss.kde.org/t/cmake-builds-of-some-kde-projects-make-the-system-unresponsive-by-queuing-way-too-many-jobs/28091).

- If set to empty string, taskset is not used.
- If set to non-empty string, it is treated as an argument string for `taskset --cpu-list`, for example "0-6"
to restrict builds to using the first 6 CPU threads on your machine.
- If set to "auto", it will automatically prepare an argument string. It will reserve some cores for the
system to stay responsive while building. It is convenient if you often change host machine
(or number of processors of virtual machine), because it does not require changing config in that case.

(conf-use-clean-install)=
[`use-clean-install`](conf-use-clean-install)

Type: Boolean, Default value: False

Set this option to `true` in order to have kde-builder
run `make uninstall` directly before running
`make install`.

This can be useful in ensuring that there are not stray old library
files, CMake metadata, etc. that can cause issues in long-lived KDE
installations. However, this only works on build systems that support
`make uninstall`.

Related command-line option: --use-clean-install,
--no-use-clean-install

(options-phase-selection-table)=
## Phase selection options

These options do require empty value (except "filter-out-phases").

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

(options-group-table)=
## Projects selection options

(conf-ignore-projects)=
[`ignore-projects`](conf-ignore-projects)

Scope: global, group

Type: String

Note that when specified in global node,
[--ignore-projects](#cmdline-ignore-projects) cmdline option does
not override this, but instead appends.

Projects named by this option, which would be chosen by kde-builder
due to a [use-projects](#conf-use-projects) option, are instead
skipped entirely. Use this option when you want to build an entire
[kde-projects](#kde-projects-groups) project grouping
_except for_ some specific projects.

The option value does not necessarily have to name the project
directly. Any project that has full consecutive parts of its
[KDE projects projectpath](#kde-projects-groups) match one
of the option values will be ignored, so you can ignore multiple projects
this way.

For example, an option value of \<libs\> would result in both
`kde/kdegraphics/libs` and `playground/libs` being
excluded (though not `kde/kdelibs` since the full part
“kdelibs” is what is compared).

```{tip}
See also [](#example-ignoring-a-project).
```

Related command-line option: [--ignore-projects](#cmdline-ignore-projects)

(conf-use-projects)=
[`use-projects`](conf-use-projects)

Scope: group

Type: String

This option allows you to easily specify many different projects to
build at the same point in [the configuration file](./config-file-overview).

Every identifier passed to this option is internally converted to a
kde-builder project, with a [repository](#conf-repository) option set to the
group's repository combined with the identifier name in order to
set up the final repository to download from. All other options that are
assigned in the group are also copied to the generated projects
unaltered.

The order that projects are defined in this option is important,
because that is also the order that kde-builder will process the
generated projects when updating, building, and installing. All projects
defined in the given group will be handled before kde-builder
moves to the next project after the group.

If you need to change the options for a generated project, simply
declare the project again after it is defined in the group, and set
your options as needed. Although you will change the options set for the
project this way, the project will still be updated and built in the order
set by the group (i.e. you can't reorder the build sequence doing
this).

```{important}
The name to use for the project if you do this is simply the name that
you passed to `use-projects`, with the exception that any `.git` is removed.
```

See the section called [](#groups) and [git-repository-base](#conf-git-repository-base)
for a description of its use and an example.
