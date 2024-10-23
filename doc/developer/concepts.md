# Concepts

Some basic concepts are assumed throughout for brevity.

## Projects

kde-builder uses the "project" as the most granular level of buildable
software. Each project has a name, unique in the list of all projects.
Each project can have a specific source control system plugin (git,
KDE's git, etc.) and a build system plugin (qmake, CMake, KDE's
CMake, autotools, etc.)

## Build Phases

A project's build process progresses through build phases, which are often
optional.

The normal progression is:

- Update
- Uninstall (not normally seen)
- Build system setup and configuration
- Build
- Testsuite (if enabled)
- Install

The update phase can happen concurrently with other projects' build/install
phases, under the theory that the build phase is usually CPU-heavy so it makes
sense to start on subsequent network (IO-heavy) updates while the build
progresses.

## Build Context

To group global settings and status together that exist across individual
projects, a "build context" is used, shared across the entire application.

Each project can refer to the global build context.

## Configuration file (rc-file)

kde-builder uses a configuration file (usually abbreviated the `rc-file`) to
store:

- The list of projects to build
- The dependency order in which to build projects (the order seen in the rc-file)
- The build or configuration options to use by default or on a per-project basis

When kde-builder is run, it will use `kde-builder.yaml` located in the current
working directory. If this file is not present, the global rc-file at
`~/.config/kde-builder.yaml`
(`$XDG_CONFIG_HOME/kde-builder.yaml`, if `XDG_CONFIG_HOME`
environment variable is set) is used instead.

## Command line

kde-builder uses the command line (seen as "cmdline" in the source and commit
logs) to override the list of projects to build (nearly always still requiring
that any projects built are visible from the rc-file). The command line is also
used to override various options (such as skipping source update phases),
control output verbosity and so on.

In theory every option in the rc-file can be set from the cmdline, and cmdline
entries override and mask any options used by default or read from an rc-file.

## Groups

With the adoption of git, KDE exploded to having hundreds of repositories. It
would be annoying and error-prone to try to manually update the rc-file with
the list of projects to build and the proper ordering.

Because of this, kde-builder supports grouping projects into "groups" of
projects that have common options and a common repository URL prefix, as if the
user had manually entered those projects one by one.

NOTE: This is controlled by the `git-repository-base` option to set the URL
prefix, the `repository` option to choose one of the defined bases, and the
`use-projects` option to list project names.

### KDE groups

To support the KDE repositories in particular, a special group repository
is defined, `kde-projects`. Use of this repository enables some extra magic
in the projects that are ultimately defined from such a group, including
automagic dependency handling and inclusion of projects based on a virtual KDE
project structure.

NOTE: Inclusion of projects is **separate** from dependency handling, which is
also supported!

## Pretend mode

The user can pass a `--pretend` cmdline flag to have kde-builder not
actually undertake the more time or resource intensive actions, so that the
user can see what kde-builder would do and tweak their cmdline until it looks
correct, and then remove the --pretend flag from there.

This significantly influences the design of the kde-builder code, both in action and
output.

## Logs and build output

All build commands are logged to a file (see `log_command` in `Util`).
This is both to declutter the terminal output and to enable troubleshooting
after a build failure.

The logs are generally kept in a separate directory for each separate run of
kde-builder. A "latest" symlink is created for each project name, which points
to the last instance of a script run.

If a build ends in a failure, an error.log symlink is created in the specific
log directory for that project, which points to the specific build phase output
file where the build was determined to have failed.

Sometimes there is no log though (e.g. an internal kde-builder failure outside
of log_command)!

Some users prefer to have TTY output. For now the --debug cmdline option is
useful for that, but --debug has a significant amount of other changes as well.

# Basic flow

For each invocation, kde-builder generically goes through the following
steps:

- Read the cmdline to determine global options, list of project *selectors*
(projects are defined later) and potentially alternate rc-files to use.
- Opens the selected rc-file (chosen on cmdline or based on `$PWD`) and reads
in the list of projects and groups in the rc-file along with the options
chosen for each.
- Ensures that the repository metadata is available (containing
dependency information and the virtual project path hierarchy)
- If project selectors are available from the cmdline, creates the build list by
expanding those selectors into the appropriate projects from the rc-file. If no
selectors, uses all groups and projects from the rc-file.
  * Either mode can involve resolving dependencies for KDE-based projects.
- Forks additional children to serve as a way to perform updates and build in
separate processes so that they may proceed concurrently. Once ready, performs
these two steps concurrently:
  - Updates each project in order
  - Performs remaining project build steps in order (waiting for the update if
  needed).
- When all update/build processes are done, displays the results to the user.
