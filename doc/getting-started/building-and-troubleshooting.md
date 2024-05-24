(building-and-troubleshooting)=
# Using the kde-builder script

With the configuration data established, now you are ready to run the
script. Even if you still have some tweaking or other reading you wish
to do, it is a good idea to at least load the KDE project metadata.

(loading-kde-builder-metadata)=
## Loading project metadata

From a terminal window, log in to the user you are using to compile KDE
software and execute the script:

```
% kde-builder --metadata-only
```

This command will setup the source directory and connect to the KDE Git
repositories to download the database of KDE git repositories, and the
database of dependency metadata, without making any further changes. It
is useful to run this separately as this metadata is useful for other
kde-builder commands.

(pretend-mode)=
## Previewing what will happen when kde-builder runs

With the project metadata installed, it is possible to preview what
kde-builder will do when launched. This can be done with the
`--pretend` command line option.

```
% ./kde-builder --pretend
```

You should see a message saying that some packages were successfully
built (although nothing was actually built). If there were no
significant problems shown, you can proceed to actually running the
script.

```
% kde-builder
```

This command will download the appropriate source code, build and
install each module in order. Afterwards, you should see output similar
to that in [example_title](#example-build-sequence):

```{code-block}
:name: example-build-sequence
:caption: Example output of a kde-builder run

% kde-builder
Updating kde-build-metadata (to branch master)
Updating sysadmin-repo-metadata (to branch master)

Building libdbusmenu-qt (1/200)
        No changes to libdbusmenu-qt source, proceeding to build.
        Compiling... succeeded (after 0 seconds)
        Installing.. succeeded (after 0 seconds)

Building taglib (2/200)
        Updating taglib (to branch master)
        Source update complete for taglib: 68 files affected.
        Compiling... succeeded (after 0 seconds)
        Installing.. succeeded (after 0 seconds)

Building extra-cmake-modules from <module-set at line 32> (3/200)
        Updating extra-cmake-modules (to branch master)
        Source update complete for extra-cmake-modules: 2 files affected.
        Compiling... succeeded (after 0 seconds)
        Installing.. succeeded (after 0 seconds)

        ...

Building kdevelop from kdev (200/200)
        Updating kdevelop (to branch master)
        Source update complete for kdevelop: 29 files affected.
        Compiling... succeeded (after 1 minute, and 34 seconds)
        Installing.. succeeded (after 2 seconds)

<<<  PACKAGES SUCCESSFULLY BUILT  >>>
Built 200 modules

Your logs are saved in /home/kde-src/kdesrc/log/2018-01-20-07
```

(fixing-build-failures)=
## Resolving build failures

Depending on how many modules you are downloading, it is possible that
kde-builder will not succeed the first time you compile KDE software.
Do not despair!

kde-builder logs the output of every command it runs. By default, the
log files are kept in `~/kdesrc/log`. To see what the caused an error
for a module in the last kde-builder command, usually it is sufficient
to look at `~/kdesrc/log/latest/module-name/error.log`.

```{tip}
Perhaps the easiest way to find out what error caused a module to fail
to build is to search backward with a case-insensitive search, starting
from the end of the file looking for the word `error`. Once that is
found, scroll up to make sure there are no other error messages nearby.
The first error message in a group is usually the underlying problem.
```

In that file, you will see the error that caused the build to fail for
that module. If the file says (at the bottom) that you are missing some
packages, try installing the package (including any appropriate -dev
packages) before trying to build that module again. Make sure that when
you run kde-builder again to pass the
[--reconfigure](#cmdline-reconfigure) option so that kde-builder forces
the module to check for the missing packages again.

Or, if the error appears to be a build error (such as a syntax error,
“incorrect prototype”, “unknown type”, or similar) then it is probably
an error with the KDE source, which will hopefully be resolved within a
few days. If it is not resolved within that time, feel free to mail the
<kde-devel@kde.org> mailing list (subscription may be required first) in
order to report the build failure.

You can find more common examples of things that can go wrong and their
solutions, as well as general tips and strategies to build KDE software
in the [Build from
Source](https://community.kde.org/Guidelines_and_HOWTOs/Build_from_source).

On the other hand, assuming everything went well, you should have a new
KDE install on your computer, and now it is simply a matter of running
it, described in the section [](#installing-login-session).

```{note}
For more information about kde-builder's logging features, please see
the section called [](../features/kde-builder-logging).
```
