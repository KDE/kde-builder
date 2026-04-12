(supported-cmdline-parameters)=
# Supported command-line parameters

## Generic

(cmdline-pretend)=
[`--pretend`](cmdline-pretend) (or `--dry-run` or `-p`)  
Operate in a "dry run" mode. No network accesses are made, no log files
are created, no projects are built, and no other permanent changes to
disk are made. One *important exception* is that if you try to build a
project that comes from the KDE projects, and the repo-metadata hasn't
been downloaded yet, the repo-metadata will be downloaded.

Simple read-only commands (such as reading file information) may still
be run to make the output more relevant (such as correctly simulating
whether source code would be checked out or updated).

The corresponding configuration file option is
[pretend](#conf-pretend).

(cmdline-include-dependencies)=
[`--include-dependencies`](cmdline-include-dependencies) (or `-d`), `--no-include-dependencies` (or `-D`)  
This option causes kde-builder to automatically include other KDE and
Qt projects (modules) in the build, if required, for the projects you have requested
to build on the command line or in your [configuration
file](../getting-started/configure-data).

The projects that are added are as recorded within the KDE repo-metadata
dependencies. See the section called [](#kde-projects-groups).

This option is enabled by default.

The corresponding configuration file option is
[include-dependencies](#conf-include-dependencies).

(cmdline-ignore-projects)=
[`--ignore-projects`](cmdline-ignore-projects) (or `-!`) project \[project ...]  
Do not include the projects passed on the rest of the command line in the
update/build process (this is useful if you want to build most of the
projects in your [configuration file](../getting-started/configure-data) and just skip a
few).

Note that this option does not override
[ignore-projects](#conf-ignore-projects) config option in global section.
Instead, it appends it.

The corresponding configuration file option is
[ignore-projects](#conf-ignore-projects).

(cmdline-run)=
[`--run`](cmdline-run) (or `--start-program`) \[-f\|--fork\] \<program\> \[parameters ...\]  
This option interprets the next item on the command line as a program to
run, and kde-builder will then finish reading the configuration file,
source the `prefix.sh` to apply environment variables, and then execute
the given program.

The "-f", "--fork" option launches the program, and detaches its process from current terminal.

Usage examples:

Launch kate with "-l 5 file1.txt" arguments:
```bash
kde-builder --run kate -l 5 file1.txt
```

Launch kate with "-l 5 file1.txt" arguments, and detach its process from current terminal:
```bash
kde-builder --run -f kate -l 5 file1.txt
```

Launch kate-syntax-highlighter executable (installed by "kate" project) with "--list-themes" argument:
```bash
kde-builder --run kate-syntax-highlighter --list-themes
```

(cmdline-source-when-start-program)=
[`--source-when-start-program`](cmdline-source-when-start-program) \<file\>  
With this option, you can specify a path to shell file, which will be sourced before the project is launched with `--run` option.
For example, you can use it to set `QT_LOGGING_RULES` and `QT_MESSAGE_PATTERN` variables, so you could customize the debug output.

The corresponding configuration file option is
[source-when-start-program](#conf-source-when-start-program).

(cmdline-revision)=
[`--revision`](cmdline-revision) \<id\>  
This option causes kde-builder to checkout a specific numbered revision
for each project, overriding any [branch](#conf-branch),
[tag](#conf-tag), or [revision](#conf-revision) options already set for
these projects.

This option is likely not a good idea, and is only supported for
compatibility with older scripts.

The corresponding configuration file option is
[revision](#conf-revision).

(cmdline-taskset-cpu-list)=
[`--taskset-cpu-list`](cmdline-taskset-cpu-list) \<value\>  
This option is used to limit the number of cpu cores used in build/install process.

The corresponding configuration file option is
[taskset-cpu-list](#conf-taskset-cpu-list).

(cmdline-hold-performance-profile)=
[`--hold-performance-profile`](cmdline-hold-performance-profile), `--no-hold-performance-profile`  
Controls whether kde-builder will request switching the system's power profile to performance mode while building. The mode will switch back once the build is finished.

The corresponding configuration file option is
[hold-performance-profile](#conf-hold-performance-profile).

(cmdline-hold-work-branches)=
[`--hold-work-branches`](cmdline-hold-work-branches), `--no-hold-work-branches`  
This option allows you to skip updating sources for projects that have current branch which name starts with
`work/*` or `mr/*` (for example, `work/your-username/my-awesome-feature`).

This simplifies workflow when you want to work on specific project. If you checkout someone's mr
(see [wiki documentation](https://community.kde.org/Infrastructure/GitLab)), the
branch will be called something like "mr/80", and kde-builder will behave like if you have specified a "no-src" option for that project in the config.

The corresponding configuration file option is
[hold-work-branches](#conf-hold-work-branches).

(cmdline-all-config-projects)=
[`--all-config-projects`](cmdline-all-config-projects)  
This option is used to select all projects defined in user config for kde-builder to operate on.

(cmdline-all-kde-projects)=
[`--all-kde-projects`](cmdline-all-kde-projects)  
This option is used to select all known projects defined in metadata for kde-builder to operate on.

(cmdline-git-push-protocol)=
[`--git-push-protocol`](cmdline-git-push-protocol)  
The corresponding configuration file option is
[git-push-protocol](#conf-git-push-protocol).

(cmdline-install-login-session)=
[`--install-login-session`](cmdline-install-login-session), `--no-install-login-session`  
The corresponding configuration file option is
[install-login-session](#conf-install-login-session).

(cmdline-libpath)=
[`--libpath`](cmdline-libpath) \<path\>  
The corresponding configuration file option is
[libpath](#conf-libpath).

(cmdline-num-cores)=
[`--num-cores`](cmdline-num-cores) \<value\>  
The corresponding configuration file option is
[num-cores](#conf-num-cores).

(cmdline-num-cores-low-mem)=
[`--num-cores-low-mem`](cmdline-num-cores-low-mem) \<value\>  
The corresponding configuration file option is
[num-cores-low-mem](#conf-num-cores-low-mem).

(cmdline-binpath)=
[`--binpath`](cmdline-binpath) \<path\>  
The corresponding configuration file option is
[binpath](#conf-binpath).

(cmdline-branch)=
[`--branch`](cmdline-branch) \<value\>  
The corresponding configuration file option is
[branch](#conf-branch).

(cmdline-branch-group)=
[`--branch-group`](cmdline-branch-group) \<value\>  
The corresponding configuration file option is
[branch-group](#conf-branch-group).

(cmdline-build-dir)=
[`--build-dir`](cmdline-build-dir) \<path\>  
The corresponding configuration file option is
[build-dir](#conf-build-dir).

(cmdline-cmake-generator)=
[`--cmake-generator`](cmdline-cmake-generator) \<value\>  
The corresponding configuration file option is
[cmake-generator](#conf-cmake-generator).

(cmdline-cmake-options)=
[`--cmake-options`](cmdline-cmake-options) \<value\>  
The corresponding configuration file option is
[cmake-options](#conf-cmake-options).

(cmdline-compile-commands-export)=
[`--compile-commands-export`](cmdline-compile-commands-export), `--no-compile-commands-export`  
The corresponding configuration file option is
[compile-commands-export](#conf-compile-commands-export).

(cmdline-compile-commands-linking)=
[`--compile-commands-linking`](cmdline-compile-commands-linking), `--no-compile-commands-linking`  
The corresponding configuration file option is
[compile-commands-linking](#conf-compile-commands-linking).

(cmdline-configure-flags)=
[`--configure-flags`](cmdline-configure-flags) \<value\>  
The corresponding configuration file option is
[configure-flags](#conf-configure-flags).

(cmdline-custom-build-command)=
[`--custom-build-command`](cmdline-custom-build-command) \<value\>  
The corresponding configuration file option is
[custom-build-command](#conf-custom-build-command).

(cmdline-cxxflags)=
[`--cxxflags`](cmdline-cxxflags) \<value\>  
The corresponding configuration file option is
[cxxflags](#conf-cxxflags).

(cmdline-dest-dir)=
[`--dest-dir`](cmdline-dest-dir) \<path\>  
The corresponding configuration file option is
[dest-dir](#conf-dest-dir).

(cmdline-git-user)=
[`--git-user`](cmdline-git-user) \<value\>  
The corresponding configuration file option is
[git-user](#conf-git-user).

(cmdline-directory-layout)=
[`--directory-layout`](cmdline-directory-layout) \<value\>  
The corresponding configuration file option is
[directory-layout](#conf-directory-layout).

(cmdline-libname)=
[`--libname`](cmdline-libname) \<value\>  
The corresponding configuration file option is
[libname](#conf-libname).

(cmdline-log-dir)=
[`--log-dir`](cmdline-log-dir) \<path\>  
The corresponding configuration file option is
[log-dir](#conf-log-dir).

(cmdline-make-install-prefix)=
[`--make-install-prefix`](cmdline-make-install-prefix) \<value\>  
The corresponding configuration file option is
[make-install-prefix](#conf-make-install-prefix).

(cmdline-make-options)=
[`--make-options`](cmdline-make-options) \<value\>  
The corresponding configuration file option is
[make-options](#conf-make-options).

(cmdline-meson-options)=
[`--meson-options`](cmdline-meson-options) \<value\>  
The corresponding configuration file option is
[meson-options](#conf-meson-options).

(cmdline-ninja-options)=
[`--ninja-options`](cmdline-ninja-options) \<value\>  
The corresponding configuration file option is
[ninja-options](#conf-ninja-options).

(cmdline-override-build-system)=
[`--override-build-system`](cmdline-override-build-system) \<value\>  
The corresponding configuration file option is
[override-build-system](#conf-override-build-system).

(cmdline-purge-old-logs)=
[`--purge-old-logs`](cmdline-purge-old-logs), `--no-purge-old-logs`  
The corresponding configuration file option is
[purge-old-logs](#conf-purge-old-logs).

(cmdline-qmake-options)=
[`--qmake-options`](cmdline-qmake-options) \<value\>  
The corresponding configuration file option is
[qmake-options](#conf-qmake-options).

(cmdline-qt-install-dir)=
[`--qt-install-dir`](cmdline-qt-install-dir) \<path\>  
The corresponding configuration file option is
[qt-install-dir](#conf-qt-install-dir).

(cmdline-remove-after-install)=
[`--remove-after-install`](cmdline-remove-after-install) \<value\>  
The corresponding configuration file option is
[remove-after-install](#conf-remove-after-install).

(cmdline-repository)=
[`--repository`](cmdline-repository)  
The corresponding configuration file option is
[repository](#conf-repository).

(cmdline-run-tests)=
[`--run-tests`](cmdline-run-tests), `--no-run-tests`  
The corresponding configuration file option is
[run-tests](#conf-run-tests).

(cmdline-source-dir)=
[`--source-dir`](cmdline-source-dir) \<path\>  
The corresponding configuration file option is
[source-dir](#conf-source-dir).

(cmdline-tag)=
[`--tag`](cmdline-tag) \<value\>  
The corresponding configuration file option is
[tag](#conf-tag).

(cmdline-use-clean-install)=
[`--use-clean-install`](cmdline-use-clean-install), `--no-use-clean-install`  
The corresponding configuration file option is
[use-clean-install](#conf-use-clean-install).

(cmdline-set-project-option-value)=
[`--set-project-option-value`](cmdline-set-project-option-value) \<project-name\>,\<option-name\>,\<option-value\>  
You can use this option to override an option in your [configuration
file](../getting-started/configure-data) for a specific project.

## Resuming and stopping

(cmdline-resume-from)=
[`--resume-from`](cmdline-resume-from) (or `--from` or `-f`) \<project\>  
This option is used to resume the build starting from the given project.
You should not specify other project names on the command line.

```{note}
If you want to avoid source updates when resuming, simply pass
`--no-src` in addition to the other options.
```

See also: [--resume-after](#cmdline-resume-after) and the section called
[](#resuming-failed). You would prefer to use this command line
option if you have fixed the build error and want kde-builder to
complete the build.

(cmdline-resume-after)=
[`--resume-after`](cmdline-resume-after) (or `--after` or `-a`) \<project\>  
This option is used to resume the build starting after the given project.
You should not specify other project names on the command line.

```{note}
If you want to avoid source updates when resuming, simply pass
`--no-src` in addition to the other options.
```

See also: [--resume-from](#cmdline-resume-from) and the section called
[](#resuming-failed). You would prefer to use this command line
option if you have fixed the build error and have also built and
installed the project yourself, and want kde-builder to start again with
the next project.

(cmdline-resume)=
[`--resume`](cmdline-resume)  
This option can be used to run kde-builder after it has had a build
failure.

It resumes the build from the project that failed, using the list of
projects that were waiting to be built before, and disables source and
metadata updates as well. The use case is when a simple mistake or
missing dependency causes the build failure. Once you correct the error
you can quickly get back into building the projects you were building
before, without fiddling with `--resume-from` and `--stop-before`.

(cmdline-resume-refresh-build-first)=
[`--resume-refresh-build-first`](cmdline-resume-refresh-build-first) (or `-R`)  
This option is an alias for using `--resume` and `--refresh-build-first` at the same time.
It is convenient to use when some project failed to build, and you want to refresh build it,
and then continue (re-)building projects after that one, as if it was built successfully in
the first place.

(cmdline-stop-before)=
[`--stop-before`](cmdline-stop-before) (or `--until`) \<project\>  
This option is used to stop the normal build process just *before* a
project would ordinarily be built.

For example, if the normal build list was projectA, projectB, projectC,
then `--stop-before projectB` would cause kde-builder to only build
`projectA`.

(cmdline-stop-after)=
[`--stop-after`](cmdline-stop-after) (or `--to`) \<project\>  
This option is used to stop the normal build process just *after* a
project would ordinarily be built.

For example, if the normal build list was projectA, projectB, projectC,
then `--stop-after projectB` would cause kde-builder to build `projectA`
and `projectB`.

(cmdline-stop-on-failure)=
[`--stop-on-failure`](cmdline-stop-on-failure), `--no-stop-on-failure`  
This option controls if the build will be aborted as soon as a failure
occurs. Default behavior is --stop-on-failure. You may override it if
you wish to still process the rest of the projects in the build, to avoid
wasting time in case the problem is with a single project.

The corresponding configuration file option is
[stop-on-failure](#conf-stop-on-failure).

(cmdline-rebuild-failures)=
[`--rebuild-failures`](cmdline-rebuild-failures)  
Use this option to build only those projects which failed to build on a
previous kde-builder run. This is useful if a significant number of
failures occurred mixed with successful builds. After fixing the issue
causing the build failures you can then easily build only the projects
that failed previously.

```{note}
Note that the list of "previously-failed projects" is reset every time a
kde-builder run finishes with some project failures. However, it is not
reset by a completely successful build, so you can successfully rebuild
a project or two and this flag will still work.
```

## Projects information

(cmdline-query)=
[`--query`](cmdline-query) mode  
This command causes kde-builder to query a parameter of the projects in
the build list (either passed on the command line or read in from the
configuration file), outputting the result to screen (one project per
line).

This option must be provided with a "mode", which may be one of the
following:

- `source-dir` - the full path to where the project's source code is stored.

- `build-dir` - the full path to where the project build process occurs.

- `install-dir` - the full path to where the project will be installed.

- `repopath` - the repository path in the [invent.kde.org](https://invent.kde.org).
   Only for KDE projects.

- `branch` - the resolved git branch that will be used for each project, based
   on the [tag](#conf-tag), [branch](#conf-branch) and [branch-group](#conf-branch-group) settings in effect.

- `group` - the name of group which contains the project. This can be used
   to generate zsh autocompletion cache.

- `build-system` - the name of build system detected for the project. This can be used
   to debug build system auto-detection problems, or when developing tests for specific
   build systems.

- `project-info` - the full project information, including its path, branch, repository,
   build options, and dependencies.

- Any option name that is valid for projects in the [configuration
  file](../configuration/conf-options-table).

For example, the command
`kde-builder --query branch kactivities kdepim` might end up with
output like:

```yaml
kactivities: master
kdepim: master
```

(cmdline-dependency-tree)=
[`--dependency-tree`](cmdline-dependency-tree)  
Prints the tree of the dependencies, generated from the projects specified in command line.
The tree will be recursive, i.e. you could see the dependencies of dependencies.
The output format looks similar to the `tree` utility.
In addition, each line will have information if the dependency will be built, and if case it will, also a branch to be used.

If you want to grep in the output, you can use [--dependency-tree-fullpath](cmdline-dependency-tree-fullpath) instead.

(cmdline-dependency-tree-fullpath)=
[`--dependency-tree-fullpath`](cmdline-dependency-tree-fullpath)  
Prints the tree of the dependencies, generated from the projects specified in command line.
The tree will be recursive, i.e. you could see the dependencies of dependencies.
The output format looks similar to the `find` utility.

It is easier to grep something with this format. However, if you want to visualize the tree, you can use [--dependency-tree](cmdline-dependency-tree) instead.

(cmdline-list-installed)=
[`--list-installed`](cmdline-list-installed)  
Print installed projects and exit. This can be used to generate
autocompletion for the --run option.

## Exclude specific action

(cmdline-no-metadata)=
[`--no-metadata`](cmdline-no-metadata) (or `-M`)  
Skip the metadata update phase. The source updates for the projects themselves will still occur
unless you pass [--no-src](#cmdline-no-src) as well.

This can be useful if you are frequently re-running kde-builder since
the metadata does not change very often. But note that many other
features require the metadata to be available. You might want to
consider running kde-builder with the
[--metadata-only](#cmdline-metadata-only) option one time and then using
this option for subsequent runs.

(cmdline-no-src)=
[`--no-src`](cmdline-no-src) (or `-S`)  
Skips the source update phase. Other phases are included as normal.

The corresponding configuration file option is
[no-src](#conf-no-src).

(cmdline-no-build)=
[`--no-build`](cmdline-no-build)  
Skip the build phase for the build. Internally the install phase
depends on the build phase completing so this is effectively equivalent
to `--src-only`, but the semantics may change in the future (e.g. when
test suites are moved into their own phase).

The corresponding configuration file option is
[no-build](#conf-no-build).

(cmdline-no-install)=
[`--no-install`](cmdline-no-install)  
Skip the install phase from the build. Other phases are included as normal.

The corresponding configuration file option is
[no-install](#conf-no-install).

## Only specific action

(cmdline-metadata-only)=
[`--metadata-only`](cmdline-metadata-only)  
Only perform the metadata download process. kde-builder normally
handles this automatically.

(cmdline-src-only)=
[`--src-only`](cmdline-src-only) (or `-s`)  
Only perform the source update.

(cmdline-build-only)=
[`--build-only`](cmdline-build-only)  
Forces the build process to be performed without updating source code
first. In addition, installation is not performed. (Testing is still
performed if applicable, but this will change in a future release).

The corresponding configuration file option is
[build-only](#conf-build-only).

(cmdline-install-only)=
[`--install-only`](cmdline-install-only)  
If this is the only command-line option, it tries to install all the
projects contained in `log/latest/status-list.log`. If command-line options
are specified after this option, they are all assumed to be projects to
install (even if they did not successfully build on the last run).

The corresponding configuration file option is
[install-only](#conf-install-only).

(cmdline-uninstall)=
[`--uninstall`](cmdline-uninstall)
Skips the update and build phase and immediately attempts to uninstall
the projects given. **NOTE**: This is only supported for buildsystems
that supports the `make uninstall` command (e.g. KDE CMake-based).

The corresponding configuration file option is
[uninstall](#conf-uninstall).

(cmdline-build-system-only)=
[`--build-system-only`](cmdline-build-system-only)  
Interrupts the build process for each project built. The build process
consists of normal setup up to and including running `cmake` or
`configure` (as appropriate), but `make` is not run and no installation
is attempted. This is mostly only useful to get things like
`configure --help` and `cmake-gui` to work. Normally you want
`--reconfigure` or `--refresh-build`.  
This option causes kde-builder to abort building a project just before
the `make` command would have been run. This is supported for
compatibility with older versions only, this effect is not helpful for
the current KDE build system.

The corresponding configuration file option is
[build-system-only](#conf-build-system-only).

(cmdline-install-login-session-only)=
[`--install-login-session-only`](cmdline-install-login-session-only)  
Can be used to only invoke the session installation script, so you can bypass any project update/build phases. 
See [](#installing-login-session) for more information.

## Build behavior

(cmdline-refresh-build)=
[`--refresh-build`](cmdline-refresh-build) (or `-r`)  
Removes the build directory for a project before the build phase starts.
This has the desired side effect of forcing `kde-builder` to
re-configure the project and build it from a "pristine" state with no
existing temporary or intermediate output files. Use this option if you
have problems getting a project to build but realize it will take longer
(possibly much longer) for the build to complete as a result. When in
doubt use this option for the entire `kde-builder` run.

The corresponding configuration file option is
[refresh-build](#conf-refresh-build).

(cmdline-refresh-build-first)=
[`--refresh-build-first`](cmdline-refresh-build-first)  
Enables the `refresh-build` option for the first project appeared in final projects list to build.
Useful in conjunction with `--resume`. See also [`--resume-refresh-build-first`](#cmdline-resume-refresh-build-first).

(cmdline-reconfigure)=
[`--reconfigure`](cmdline-reconfigure)  
Run `cmake` (for KDE projects) or `configure` (for non-cmake projects) again, without
cleaning the build directory.
Usually you actually want `--refresh-build`, but if you are 100% sure
your change to `cmake-options` will not invalidate your current
intermediate output then this can save some time.
You should not normally have to specify
this, as kde-builder will detect when you change the relevant options
and automatically re-run the build setup. This option is implied if
`--refresh-build` is used.

The corresponding configuration file option is
[reconfigure](#conf-reconfigure).

(cmdline-install-dir)=
[`--install-dir`](cmdline-install-dir) \<path\>  
This allows you to change the directory where projects will be installed
to. This option implies [`--reconfigure`](#cmdline-reconfigure), but
using [`--refresh-build`](#cmdline-refresh-build) may still be required.

The corresponding configuration file option is
[install-dir](#conf-install-dir).

(cmdline-generate-clion-project-config)=
[`--generate-clion-project-config`](cmdline-generate-clion-project-config), `--no-generate-clion-project-config`  
Generate a `.idea` directory with configurations for building and
debugging in CLion. This option is disabled by default.

The corresponding configuration file option is
[generate-clion-project-config](#conf-generate-clion-project-config).

(cmdline-generate-vscode-project-config)=
[`--generate-vscode-project-config`](cmdline-generate-vscode-project-config), `--no-generate-vscode-project-config`  
Generate a `.vscode` directory with configurations for building and
debugging in Visual Studio Code. This option is disabled by default.

The corresponding configuration file option is
[generate-vscode-project-config](#conf-generate-vscode-project-config).

(cmdline-generate-qtcreator-project-config)=
[`--generate-qtcreator-project-config`](cmdline-generate-qtcreator-project-config), `--no-generate-qtcreator-project-config`  
Generate Qt Creator project helpers in the source tree. This currently includes the legacy `.qtcreator`
snippets and a `CMakeUserPresets.json` with kde-builder's configure/build settings.
On Qt Creator 20+, the generated preset and its vendor metadata provide full configure/build/install/run
integration. Older versions still require manual run/deploy follow-up. This option is disabled by default.

The corresponding configuration file option is
[generate-qtcreator-project-config](#conf-generate-qtcreator-project-config).

## Script runtime

(cmdline-async)=
[`--async`](cmdline-async), `--no-async`  
Enables or disables the [asynchronous mode](#conf-async), which can
perform the source code updates and project builds at the same time. If
disabled, the update will be performed in its entirety before the build
starts. Disabling this option will slow down the overall process. If you
encounter IPC errors while running kde-builder try disabling it, and
submitting a [bug report](https://bugs.kde.org/). This option is enabled
by default.

The corresponding configuration file option is [async](#conf-async).

(cmdline-color)=
[`--color`](cmdline-color) (or `--colorful-output`), `--no-color` (or `--no-colorful-output`)  
Enable or disable colorful output. By default, this option is enabled
for interactive terminals.

The corresponding configuration file option is [colorful-output](#conf-colorful-output).

(cmdline-debug)=
[`--debug`](cmdline-debug)  
Enables `DEBUG` level for every logger of the kde-builder. See [](#changing-verbosity).

(cmdline-nice)=
[`--nice`](cmdline-nice) (or `--niceness`) \<value\>  
Changes the CPU priority given to `kde-builder` (and all subprocesses used
by `kde-builder`, e.g. `make`). Value should be an integer number
between 0 and 19. 0 is highest priority (because it is the least "nice"),
19 is the lowest priority. This option defaults to 10.

The corresponding configuration file option is [niceness](#conf-niceness).

(cmdline-use-idle-io-priority)=
[`--use-idle-io-priority`](cmdline-use-idle-io-priority), `--no-use-idle-io-priority`  
Changes the *I/O* priority on systems where that is supported. The priority
is set to class "idle".

The corresponding configuration file option is [use-idle-io-priority](#conf-use-idle-io-priority).

(cmdline-rc-file)=
[`--rc-file`](cmdline-rc-file) \<file\>  
Path to the configuration file to use by kde-builder. The default is `kde-builder.yaml` from current working directory (if exists) or otherwise
`~/.config/kde-builder.yaml`.

(cmdline-log-level)=
[`--log-level`](cmdline-log-level) logger-name=LEVEL  
Set the verbosity level of some internal logger. This can be used in order to conveniently debug behavior of kde-builder itself.
Name of the logger should be followed by equal sign, and then followed by name of the level.
Can be used several times in one command.

Example:
```shell
kde-builder wayland --log-level logged-command=INFO --log-level ide_project_configs=DEBUG
```
Available logger names can be seen in the `data/kde-builder-logging.yaml`
file. Level names can be one of "ERROR", "WARNING", "INFO", "DEBUG". See also [](../developer/adding-logger.md).

(cmdline-check-self-updates)=
[`--check-self-updates`](cmdline-check-self-updates), `--no-check-self-updates`  
Controls if kde-builder will perform a check (only once a week)
if its version is outdated compared to the version available in its repository.

The corresponding configuration file option is
[check-self-updates](#conf-check-self-updates).

(cmdline-persistent-data-file)=
[`--persistent-data-file`](cmdline-persistent-data-file) \<file\>  
The corresponding configuration file option is
[persistent-data-file](#conf-persistent-data-file).

## Setup

(cmdline-initial-setup)=
[`--initial-setup`](cmdline-initial-setup)  
Has kde-builder perform the one-time initial setup necessary to prepare
the system for kde-builder to operate, and for the newly-installed KDE
software to run.

This includes:

- Installing known dependencies (on supported Linux distributions)
- Generating kde-builder.yaml config

This option is exactly equivalent to using `--install-distro-packages`
and `--generate-config` at the same time.

(cmdline-install-distro-packages)=
[`--install-distro-packages`](cmdline-install-distro-packages)  
Installs distro packages (on supported Linux distributions) necessary to
prepare the system for kde-builder to operate, and for the
newly-installed KDE software to run.

See also `--initial-setup`

(cmdline-generate-config)=
[`--generate-config`](cmdline-generate-config)  
Generate the kde-builder configuration file.

See also `--initial-setup`

(cmdline-prompt-answer)=
[`--prompt-answer`](cmdline-prompt-answer) \<value\>  
Prevent the interactive prompts, and use the _value_ as the prompt answer. Such prompts can be seen in install-distro-packages step.

(cmdline-self-update)=
[`--self-update`](cmdline-self-update)  
Convenience shortcut for updating kde-builder to the latest revision.
Performs a `git pull` command in the kde-builder installation directory.

(cmdline-setup-qtcreator-kde-kit)=
[`--setup-qtcreator-kde-kit`](cmdline-setup-qtcreator-kde-kit)  
Register or refresh the `KDE Builder` kit in Qt Creator via `sdktool`.
**Only needed for Qt Creator versions older than 20.** Qt Creator 20+ uses the `CMakeUserPresets.json`
generated by [`--generate-qtcreator-project-config`](#cmdline-generate-qtcreator-project-config) directly
and does not require a pre-registered kit.
The kit carries kde-builder's common CMake settings plus the KDE build/run environment, and tries to
auto-detect a matching Qt version, CMake tool, toolchains, and debugger.
Use the [`qtcreator-sdktool-path`](#conf-qtcreator-sdktool-path) and
[`qtcreator-settings-path`](#conf-qtcreator-settings-path) configuration options to override where
`sdktool` and the Qt Creator settings directory are found.

## Script information

(cmdline-version)=
[`--version`](cmdline-version) (or `-v`)  
Display the program version.

(cmdline-help)=
[`--help`](cmdline-help) (or `-h`)  
Only display simple help on this script.

(cmdline-show-info)=
[`--show-info`](cmdline-show-info)  
Displays information about kde-builder and the operating system, that
may prove useful in bug reports or when asking for help in forums or
mailing lists.

(cmdline-show-options-specifiers)=
[`--show-options-specifiers`](cmdline-show-options-specifiers)  
Print the specifier lines (in the format that GetOpts::Long accepts) for
all command line options supported by the script. This may be used by
developers, for example, for generating zsh autocompletion functions.
