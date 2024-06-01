(advanced-features)=
# Advanced features

(partial-builds)=
## Partially building a module

It is possible to build only pieces from a single KDE module. For
example, you may want to compile only one program from a module.
KDE Builder has features to make this easy. There are several
complementing ways to do this.

(not-compiling)=
### Removing directories from a build

It is possible to download an entire repository but have the build
system leave out a few directories when it does the build. This requires
that the module uses CMake and that the module's build system allows the
directory to remove to be optional.

This is controlled with the [do-not-compile](#conf-do-not-compile)
option.

```{important}
This option requires at least that the build system for the module is
reconfigured after changing it. This is done using the
`kde-builder --reconfigure module` command.
```

```{note}
Possibly outdated info. Curently there is no any active repo under kde/kdebindings.
```

To remove the `python` directory from the kdebindings build process:

```text
module kdebindings
  do-not-compile python
end module
```

```{note}
This function depends on some standard conventions used in most KDE
modules. Therefore it may not work for all programs.
```

(stopping-the-build-early)=
## Stopping the build early

(the-build-continues)=
### Decide the stopping on failures strategy

KDE Builder can update, build and install all modules in the
specified list of modules to build, even if a module fails to build.
This is usually a convenience to allow you to update software packages
even if a simple mistake is made in one of the source repositories
during development that causes the build to break.

However, you may wish KDE Builder to stop what it is doing once a
module fails to build and install. This can help save you time that will
be wasted trying to make progress when modules remaining in the build
list will not be able to successfully build either, especially if you
have not ever successfully built the modules in the list.

The primary method to do this is to use the
[--no-stop-on-failure](#cmdline-stop-on-failure) command line option
when you run kde-builder.

This option can also be set in the [configuration
file](#conf-stop-on-failure) to make it the normal mode of operation.

It is also possible to tell kde-builder at runtime to stop building
*after* completing the current module it is working on. This is as
opposed to interrupting kde-builder using a shortcut like
Ctrl+C, which interrupts kde-builder
immediately, losing the progress of the current module.

```{important}
Interrupting kde-builder during a module install when the
[use-clean-install](#conf-use-clean-install) option is enabled will mean
that the interrupted module will be unavailable until kde-builder is
able to successfully build the module!

If you need to interrupt kde-builder without permitting a graceful
shutdown in this situation, at least try to avoid doing this while
kde-builder is installing a module.
```

(stopping-early-without-stop-on-failure)=
### Stopping kde-builder gracefully when stop-on-failure is false

As mentioned above, it is possible to cause kde-builder to gracefully
shutdown early once it has completed the module it is currently working
on. To do this, you need to send the POSIX `HUP` signal to kde-builder.

You can do this with a command such as `pkill` (on Linux systems) as
follows:

```
$ pkill -HUP kde-builder
```

If done successfully, you will see a message in the kde-builder output
similar to:

```
[build process] recv SIGHUP, will end after this module
```

```{note}
kde-builder may show this message multiple times depending on the
number of individual kde-builder processes that are active. This is
normal and not an indication of an error.
```

Once kde-builder has acknowledged the signal, it will stop processing
after the current module is built and installed. If kde-builder is
still updating source code when the request is received, kde-builder
will stop after the module source code update is complete. Once both the
update and build processes have stopped early, kde-builder will print
its partial results and exit.

(building-successfully)=
## How kde-builder tries to ensure a successful build

(automatic-rebuilds)=
### Automatic rebuilds

There are situations where KDE Builder will automatically attempt to
rebuild the module:

- If you change [configure-flags](#conf-configure-flags) or
  [cmake-options](#conf-cmake-options) for a module, then kde-builder
  will detect that and automatically re-run configure or cmake for that
  module.

- If the buildsystem does not exist (even if kde-builder did not delete
  it) then kde-builder will automatically re-create it. This is useful
  to allow for performing a full
  [--refresh-build](#cmdline-refresh-build) for a specific module
  without having that performed on other modules.

(manual-rebuilds)=
### Manually rebuilding a module

If you make a change to a module's option settings, or the module's
source code changes in a way kde-builder does not recognize, you may
need to manually rebuild the module.

You can do this by simply running `kde-builder --refresh-build module`.

If you would like to have kde-builder automatically rebuild the module
during the next normal build update instead, you can create a special
file. Every module has a build directory. If you create a file called
`.refresh-me` in the build directory for a module, kde-builder will
rebuild the module next time the build process occurs, even if it would
normally perform the faster incremental build.

Rebuild using `.refresh-me` for module kcalc:

```bash
touch ~/kde/build/kcalc/.refresh-me
kde-builder kcalc
```

```{tip}
By default, the build directory is `~/kde/build/module-name/`. If you change
the setting of the [build-dir](#conf-build-dir) option, then use that
instead of `~/kde/build`.
```

(changing-environment)=
## Changing environment variable settings

Normally kde-builder uses the environment that is present when starting
up when running programs to perform updates and builds. This is useful
for when you are running kde-builder from the command line.

However, you may want to change the setting for environment variables
that kde-builder does not provide an option for directly. For
instance, to setup any required environment variables when running
kde-builder on a timer such as Cron. This is possible with the
[set-env](#conf-set-env) option.

Unlike most options, it can be set more than once, and it accepts two
entries, separated by a space. The first one is the name of the
environment variable to set, and the remainder of the line is the value.

Set `DISTRO=BSD` for all modules:

```text
global
  set-env DISTRO BSD
end global
```

(resuming)=
## Resuming builds

(resuming-failed)=
### Resuming a failed or canceled build

You can tell kde-builder to start building from a different module than
it normally would. This can be useful when a set of modules failed, or
if you canceled a build run in the middle. You can control this using
the [--resume-from](#cmdline-resume-from) option and the
[--resume-after](#cmdline-resume-after) option.

Resuming the build starting from kxmlgui:

```bash
kde-builder --resume-from=kxmlgui
```

Resuming the build starting after kxmlgui (in case you manually fixed
the issue and installed the module yourself):

```bash
kde-builder --resume-after=kxmlgui
```

If the last kde-builder build ended with a build failure, you can also
use the [--resume](#cmdline-resume) command line option, which resumes
the last build starting at the module that failed. The source and
metadata updates are skipped as well (but if you need these, it's
generally better to use [--resume-from](#cmdline-resume-from) instead).

(ignoring-modules)=
### Ignoring modules in a build

Similar to the way you can [resume the build from a
module](#resuming-failed), you can instead choose to update and build
everything normally, but ignore a set of modules.

You can do this using the [--ignore-modules](#cmdline-ignore-modules)
option. This option tells kde-builder to ignore all the modules on the
command line when performing the update and build.

Ignoring extragear/multimedia and kdereview during a full run:

```bash
kde-builder --ignore-modules extragear/multimedia kdereview
```

(changing-env-from-cmd-line)=
## Changing options from the command line

(changing-global-opts)=
### Changing global options

You can change the setting of options read from the [configuration
file](../getting-started/configure-data) directly from the command line. This change will
override the configuration file setting, but is only temporary. It only
takes effect as long as it is still present on the command line.

kde-builder allows you to change options named like \<option-name\> by
passing an argument on the command line in the form
`--option-name=value`. kde-builder will recognize whether it does not
know what the option is, and search for the name in its list of option
names. If it does not recognize the name, it will warn you, otherwise it
will remember the value you set it to and override any setting from the
configuration file.

Setting the [source-dir](#conf-source-dir) option to `/dev/null` for
testing:

```bash
kde-builder --pretend --source-dir=/dev/null
```

(changing-module-opts)=
### Changing module options

It is also possible to change options only for a specific module. The
syntax is similar: `--<module>,<option-name>=<value>`.

This change overrides any duplicate setting for the module found in the
[configuration file](../getting-started/configure-data), and applies only while the option
is passed on the command line.

Using a different build directory for the kcalc module:

```
kde-builder --kcalc,build-dir=temp-build
```

(installing-login-session)=
## Installing login session

It is possible to log into the Plasma session built by KDE Builder. This can be used for testing new features.

In your configuration file, enable the [install-login-session](#conf-install-login-session) option. Build the `plasma-workspace`
module. KDE Builder will install the session at the end of the process.

The installation script requires write access to these locations, so you will be asked to enter a sudo password:
- `/usr/local/share/xsessions/`
- `/usr/local/share/wayland-sessions/`
- `/opt/kde-dbus-scripts/`
- `/etc/dbus-1/session.d/`

After that, you can log out, and select the Development session in SDDM session chooser:

![Select the development session in SDDM](/_static/sddm_dev_session_select.png)

Kde-builder will keep track of when it needs to rerun the session installation script. This happens when some of the
files that are handled by installation script are changed. When installation is not needed, it is not run, so it will
not bother you to enter sudo password.
