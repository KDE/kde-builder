(basic-features)=
# Basic kde-builder features

(building-qt)=
## Building Qt

KDE Builder supports building the Qt toolkit used by KDE software as a
convenience to users. This support is handled by a special group
named `qt6-set`. It is defined [here](https://invent.kde.org/sysadmin/repo-metadata/-/blob/master/build-configs/qt6.yaml?ref_type=heads).

```{note}
Qt is developed under a separate repository from KDE software located at
<https://code.qt.io/cgit/qt/>.
```

In order to build Qt, you should make sure that the
[qt-install-dir](#conf-qt-install-dir) option is set to the directory
you'd like to install Qt to, as described in the section called [](../getting-started/configure-data).

Now check if you are using default build configs. This is done by this config line:

```yaml
include ${build-configs-dir}/kde6.yaml: ""
```

If this is the case, you are on a safe side.

If for some reason you are not using default build configs, then you should ensure that
the `qt6-set` group is added to your `kde-builder.yaml` _before_ any other projects in the file.
Then you should verify that the [repository](#conf-repository) option and
[branch](#conf-branch) options are set appropriately.

The `repository` option if set to "qt6-copy", is to build Qt using a mirror maintained on the KDE
source repositories (no other changes are applied, it is simply a
clone of the official source). This is highly recommended due to
occasional issues with cloning the full Qt framework from its official
repository.

You can find out available branches [here](https://invent.kde.org/qt/qt/qtbase/-/branches).

Most likely, you would want to exclude qtwebengine from building, as it has significant build requirements.
To do this, add it to "ignore-projects" in your config:

```yaml
global:
  ignore-projects:
    - qtwebengine
```

Now you can just run the following command:

```bash
kde-builder qt6-set
```

(kde-builder-std-flags)=
## Standard flags added by kde-builder

To save you time, kde-builder adds some standard paths to your
environment for you:

- The path to the KDE and Qt libraries is added to the `LD_LIBRARY_PATH`
  variable automatically. This means that you do not need to edit
  [libpath](#conf-libpath) to include them.

- The path to the KDE and Qt development support programs are added to
  the `PATH` variable automatically. This means that you do not need to
  edit [binpath](#conf-binpath) to include them.

- The path to the KDE-provided pkg-config is added automatically to
  `PKG_CONFIG_PATH`. This means that you do not need to use
  [set-env](#conf-set-env) to add these.


Note that this does not apply if you are using custom toolchain file, for example with [cmake-toolchain](#conf-cmake-toolchain).

(build-priority)=
## Changing kde-builder's build priority

Programs can run with different priority levels on Operating Systems,
including Linux and BSD. This allows the system to allocate time for the
different programs in accordance with how important they are.

kde-builder will normally allocate itself a low priority so that the
rest of the programs on your system are unaffected and can run normally.
Using this technique, kde-builder will use extra CPU when it is
available.

To alter kde-builder so that it uses a higher (or lower) priority level
permanently, then you need to adjust the [niceness](#conf-niceness)
setting in the [configuration file](../getting-started/configure-data). The
[niceness](#conf-niceness) setting controls how "nice" kde-builder is
to other programs. In other words, having a higher
niceness gives kde-builder a lower priority. So to
give kde-builder a higher priority, reduce the
niceness (and vice versa). The niceness can go from 0 (not nice at all, highest
priority) to 20 (super nice, lowest priority).

You can also temporarily change the priority for kde-builder by using
the [--nice](#cmdline-nice) [command line option](../cmdline/cmdline-usage). The value
to the option is used exactly the same as for
[niceness](#conf-niceness).

```{note}
It is possible for some programs run by the super user to have a
negative nice value, with a correspondingly even higher priority for
such programs. Setting a negative (or even 0) [niceness](#conf-niceness)
for kde-builder is not a great idea, as it will not help run time
significantly, but will make your computer seem very sluggish should you
still need to use it.
```

To run kde-builder with a niceness of 15 (a lower priority than
normal):

```bash
kde-builder --nice=15
```
Or you can edit the [configuration file](../getting-started/configure-data) to make the
change permanent:

```yaml
niceness: "15"
```

```{tip}
The [niceness](#conf-niceness) option only affects the usage of the
computer's processor(s). One other major affect on computer performance
relates to how much data input or output (I/O) a program uses. In order
to control how much I/O a program can use, modern Linux operating
systems support a similar tool called ionice. kde-builder supports
ionice, (but only to enable or disable it completely) using the
[use-idle-io-priority](#conf-use-idle-io-priority) option.
```

(root-installation)=
## Installation as the superuser

You may wish to have kde-builder run the installation with super user
privileges. This may be for the unrecommended system-wide installation.
This is also useful when using a recommended single user KDE build,
however. This is because some projects install
programs that will briefly need elevated permissions when run. They are
not able to achieve these permission levels unless they are installed
with the elevated permissions.

To take care of this, kde-builder provides the
[make-install-prefix](#conf-make-install-prefix) option. You can use
this option to specify a command to use to perform the installation as
another user. The recommended way to use this command is with the sudo
program, which will run the install command as the super user.

For example, to install all projects using sudo, you could do something
like this:

```yaml
global:
  make-install-prefix: sudo
  # Other options
```

To use [make-install-prefix](#conf-make-install-prefix) for only a
single project, this would work:

```yaml
project some-project-name:
  make-install-prefix: sudo
```

(build-progress)=
## Showing the progress of a project build

This feature is always available, and is automatically enabled when
possible. What this does is display an estimated build progress while
building a project. That way you know about how much longer it will take
to build a project.
