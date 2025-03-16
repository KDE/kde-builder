(cmdline-usage)=
# Command Line Usage

KDE Builder is designed to be run as follows:

kde-builder \[--options\] \[projects to build...\]

If no projects to build are specified on the command line, then
kde-builder will build all projects defined in its configuration file,
in the order listed in that file (although this can be modified by
various configuration file options).

(cmdline-usage-projects)=
## Specifying projects to build

In general, specifying projects to build is as simple as passing their
project name as you defined it in the configuration file. You can also
pass projects that are part of a group, either as named on
[use-projects](#conf-use-projects), or the name of the entire group
itself.

In the specific case of groups based against the [KDE project
database](#kde-projects-groups), kde-builder will expand project
name components to determine the exact project you want. For example,
repo-metadata's KDE project entry locates the project in
`extragear/utils/kcalc`. You could specify any of the following
to build kcalc:

```bash
kde-builder +kde/kdeutils/kcalc
kde-builder +kdeutils/kcalc
kde-builder +kcalc
```

```{note}
The commands in the example above preceded the project name with a
`+`. This forces the project name to be interpreted as a project from the
KDE project database, even if that project hasn't been defined in your
configuration file.
```

Be careful about specifying very generic projects (e.g.
`extragear/utils` by itself), as this can lead to a large amount of
projects being built. You should use the `--pretend` option before
building a new group to ensure it is only building the projects you
want.

(cmdline-commonly-used-options)=
## Commonly used command line options

`--pretend` (or `-p`)  
This option causes KDE Builder to indicate what actions it would take,
without actually executing them. This can be useful to make
sure that the projects you think you are building will actually get
built.

`--no-src` (or `-S`)  
This option skips the source update process. You might use it if you
have very recently updated the source code (perhaps you did it manually
or recently ran kde-builder) but still want to rebuild some projects.

`--no-include-dependencies` (or `-D`)  
Only process the selected projects, skipping their dependencies. Useful
when you have changed only selected projects, and you are sure you do not
need to rebuild the others.

`--refresh-build` (or `-r`)  
This option forces kde-builder to build the given projects from an
absolutely fresh start point. Any existing build directory for that
project is removed and it is rebuilt. This option is useful if you have
errors building a project, and sometimes is required when Qt or KDE
libraries change.

`--resume-from` project  
Skips projects until just before the given project, then operates as
normal. Useful when the previous build failed on specific project, you
fixed it, and then you want to continue the building with the rest of
initial set of projects.

`--run` executable_name  
Launch the built application.

The full list of command line options is given in the section called
[](#supported-cmdline-params).

## Exit status

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

## Signals

kde-builder supports `SIGHUP`, which if received will cause
kde-builder to exit after the current projects for the build thread (and
update thread, if still active) have completed.
