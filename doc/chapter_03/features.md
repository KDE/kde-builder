(features-overview)=
# Feature Overview

kdesrc-build features include:

- You can “pretend” to do the operations. If you pass `--pretend` or
  `-p` on the command line, the script will give a verbose description
  of the commands it is about to execute, without actually executing it.
  However if you've never run kdesrc-build, you would want to run the
  `kdesrc-build --metadata-only` command first in order for `--pretend`
  to work.

```{tip}
  For an even more verbose description of what kdesrc-build is doing,
  try using the `--debug` option.
```

- kdesrc-build allows you to checkout modules quickly. If the module you
  are checking out has already been checked out previously, then
  kdesrc-build will download only commits that are not yet on your
  computer.

```{tip}
  There is generally no need for any special preparation to perform the
  initial checkout of a Git module, as the entire Git repository must be
  downloaded anyways, so it is easy for the server to determine what to
  send.
```

  This is faster for you, and helps to ease the load on the kde.org
  anonymous Git servers.

- Another speedup is provided by starting the build process for a module
  as soon as the source code for that module has been downloaded.
  (Available since version 1.6)

- Excellent support for building the Qt library (in case the KDE
  software you are trying to build depends on a recent Qt not available
  in your distribution).

- kdesrc-build does not require a GUI present to operate. So, you can
  build KDE software without needing a graphical environment.

- Supports setting default options for all modules (such as the
  compilation settings or the configuration options). Such options can
  normally be changed for specific modules as well.

  Also, kdesrc-build will [add standard flags](#kdesrc-build-std-flags)
  as appropriate to save you the trouble and possible errors from typing
  them yourself. Nota Bene: this does not apply when a (custom)
  toolchain is configured through e.g.:
  [cmake-toolchain](#conf-cmake-toolchain)

- kdesrc-build can checkout a specific [branch or tag](#using-branches)
  of a module. You can also ensure that a specific
  [revision](#conf-revision) is checked out of a module.

- kdesrc-build can automatically switch a source directory to checkout
  from a different repository, branch, or tag. This happens
  automatically when you change an option that changes what the
  repository URL should be, but you must use the
  [--src-only](#cmdline-src-only) option to let kdesrc-build know that
  it is acceptable to perform the switch.

- kdesrc-build can [checkout only portions of a
  module](#partial-builds), for those situations where you only need one
  program from a large module.

- For developers: kdesrc-build will [remind you](#ssh-agent-reminder) if
  you use git+ssh:// but ssh-agent is not running, as this will lead to
  repeated password requests from SSH.

- Can [delete the build directory](#deleting-build-dir) of a module
  after its installation to save space at the expense of future
  compilation time.

- The locations for the directories used by kdesrc-build are
  configurable (even per module).

- Can use Sudo, or a different user-specified command to [install
  modules](#root-installation) so that kdesrc-build does not need to be
  run as the super user.

- kdesrc-build runs [with reduced priority](#build-priority) by default
  to allow you to still use your computer while kdesrc-build is working.

- Has support for using KDE's [tags and branches](#using-branches).

- There is support for [resuming a build](#resuming) from a given
  module. You can even [ignore some modules](#ignoring-modules)
  temporarily for a given build.

- kdesrc-build will show the [progress of your build](#build-progress)
  when using CMake, and will always time the build process so you know
  after the fact how long it took.

- Comes built-in with a sane set of default options appropriate for
  building a base KDE single-user installation from the anonymous source
  repositories.

- Tilde-expansion for your configuration options. For example, you can
  specify:

```
install-dir ~/kde/usr
```

- Automatically sets up a build system, with the source directory not
  the same as the build directory, in order to keep the source directory
  pristine.

- You can specify global options to apply to every module to check out,
  and you can specify options to apply to individual modules as well.

- Forced full rebuilds, by running kdesrc-build with the
  `--refresh-build` option.

- You can specify various environment values to be used during the
  build, including `DO_NOT_COMPILE` and `CXXFLAGS`.

- Command logging. Logs are dated and numbered so that you always have a
  log of a script run. Also, a special symlink called latest is created
  to always point to the most recent log entry in the log directory.
