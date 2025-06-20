(building-and-troubleshooting)=
# Using the kde-builder tool

With the configuration data established, now you are ready to run the
tool.

(loading-kde-builder-metadata)=
## Loading project metadata

The metadata downloading is handled automatically when needed. But in case
you want to download it manually, run the command:

```bash
kde-builder --metadata-only
```

This command will set up the source directory and download special repository
from invent.kde.org containing data about all KDE projects, their dependencies between each other and from third party projects.
No other changes will be made.

(pretend-mode)=
## Previewing what will happen when kde-builder runs

With the project metadata installed, it is possible to preview what
kde-builder will do when launched. This can be done with the
`--pretend` command line option.

```bash
kde-builder kcalc --pretend
```

You should see a message saying that some projects were successfully
built (although nothing was actually built). If there were no
significant problems shown, you can proceed to actually running the
script.

```bash
kde-builder kcalc
```

This command will download the appropriate source code, build and
install each project in order. Afterwards, you should see output similar
to that in [example_title](#example-build-sequence):

```{code-block}
:name: example-build-sequence
:caption: Example output of a kde-builder run

$ kde-builder kcalc
Updating repo-metadata
         Fetching remote changes to sysadmin-repo-metadata
         Merging sysadmin-repo-metadata changes from branch master

Holding performance profile

Building frameworks/extra-cmake-modules (1/26)
        Fetching remote changes to extra-cmake-modules
        Merging extra-cmake-modules changes from branch master
        No changes to extra-cmake-modules source code, but proceeding to build anyway.
        Compiling... succeeded (after 2 seconds)
        Installing extra-cmake-modules succeeded (after 2 seconds)

Building libraries/plasma-wayland-protocols (2/26)
        Fetching remote changes to plasma-wayland-protocols
        Merging plasma-wayland-protocols changes from branch master
        No changes to plasma-wayland-protocols source code, but proceeding to build anyway.
        Compiling... succeeded (after 0 seconds)
        Installing plasma-wayland-protocols succeeded (after 2 seconds)

Building frameworks/kconfig (3/26)
        Fetching remote changes to kconfig
        Merging kconfig changes from branch master
        Source update complete for kconfig: 1 commit pulled.
        Compiling... succeeded (after 2 seconds)
        Note: -- 3 -- compile warnings
        Installing kconfig succeeded (after 2 seconds)

        ...

Building utilities/kcalc (26/26)
        Fetching remote changes to kcalc
        Merging kcalc changes from branch master
        No changes to kcalc source code, but proceeding to build anyway.
        Compiling... succeeded (after 1 minute and 34 seconds)
        Installing kcalc succeeded (after 2 seconds)

<<<  PROJECTS SUCCESSFULLY BUILT  >>>
Built 26 projects

:-)
Your logs are saved in /home/username/kde/log/2024-10-20_07
```

(fixing-build-failures)=
## Resolving build failures

KDE Builder logs the output of every command it runs. By default, the
log files are kept in `~/kde/log`. To see what caused an error
for a project in the last kde-builder command, usually it is sufficient
to look at `~/kde/log/latest/project-name/error.log`.

```{tip}
Perhaps the easiest way to find out what error caused a project to fail
to build is to search backward with a case-insensitive search, starting
from the end of the file looking for the word `error`. Once that is
found, scroll up to make sure there are no other error messages nearby.
The first error message in a group is usually the underlying problem.
```

In that file, you will see the error that caused the build to fail for
that project. If the file says (at the bottom) that you are missing some
packages, try installing the package (including any appropriate -dev
packages) before trying to build that project again. Make sure that when
you run kde-builder again to pass the
[--reconfigure](#cmdline-reconfigure) option so that kde-builder forces
the project to check for the missing packages again.

Or, if the error appears to be a build error (such as a syntax error,
"incorrect prototype", "unknown type", or similar) then it is probably
an error with the KDE source, which will hopefully be resolved within a
few days. If it is not resolved within that time, feel free to mail the
<kde-devel@kde.org> mailing list (subscription may be required first) in
order to report the build failure.

On the other hand, assuming everything went well, you should have a new
KDE installation on your computer, and now it is simply a matter of running
it, described in the section [](#installing-login-session).

```{note}
For more information about KDE Builder's logging features, please see
the section called [](#kde-builder-logging).
```
