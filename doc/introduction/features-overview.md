(features-overview)=
# Features Overview

KDE Builder features include:

- You can "pretend" to do the operations. If you pass `--pretend` or
  `-p` on the command line, the tool will give a verbose description
  of the commands it is about to execute, without actually executing it.

  For an even more verbose description of what KDE Builder is doing,
  try using the `--debug` option.

- Excellent support for building the Qt library (in case the KDE
  software you are trying to build depends on a recent Qt not available
  in your distribution).

- KDE Builder does not require a GUI present to operate. So, you can
  build KDE software without needing a graphical environment.

- Supports setting default options for all projects (such as the
  compilation settings or the configuration options). Such options can
  normally be changed for specific projects as well.

  Also, KDE Builder will [add standard flags](#kde-builder-std-flags)
  as appropriate to save you the trouble and possible errors from typing
  them yourself.

- KDE Builder can checkout a specific branch or tag
  of a project. You can also ensure that a specific
  [revision](#conf-revision) is checked out of a project.

- KDE Builder can [checkout only portions of a
  project](#partial-builds), for those situations where you only need one
  program from a large project.

- For developers: KDE Builder will [remind you](#ssh-agent-reminder) if
  you use git+ssh:// but ssh-agent is not running, as this will lead to
  repeated password requests from SSH.

- Can [delete the build directory](#deleting-build-dir) of a project
  after its installation to save space at the expense of future
  compilation time.

- The locations for the directories used by KDE Builder are
  configurable (even per project).

- Can use `sudo`, or a different user-specified command to [install
  projects](#root-installation) so that KDE Builder does not need to be
  run as the super user.

- KDE Builder runs [with reduced priority](#build-priority) by default
  to allow you to still use your computer while it is working.

- There is support for [resuming a build](#resuming) from a given
  project. You can even [ignore some projects](#ignoring-projects)
  temporarily for a given build.

- KDE Builder will show the [progress of your build](#build-progress)
  when using CMake, and will always time the build process so you know
  after the fact how long it took.

- Comes built-in with a sane set of default options appropriate for
  building a base KDE single-user installation from the source code.

- Forced full rebuilds, by running `kde-builder` with the
  `--refresh-build` option.

- You can specify various environment values to be used during the
  build, including `DO_NOT_COMPILE` and `CXXFLAGS`.

- Command logging. Logs are dated and numbered so that you always have a
  log of a script run. Also, a special symlink called latest is created
  to always point to the most recent log entry in the log directory.
