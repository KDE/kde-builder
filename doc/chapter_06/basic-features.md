(basic-features)=
# Basic kde-builder features

(using-qt)=
## qt support

kde-builder supports building the Qt toolkit used by KDE software as a
convenience to users. This support is handled by a special module named
qt.

```{note}
Qt is developed under a separate repository from KDE software located at
<http://code.qt.io/cgit/qt/>.
```

In order to build Qt, you should make sure that the
[qt-install-dir](#conf-qt-install-dir) option is set to the directory
you'd like to install Qt to, as described in the section called [](../getting-started/configure-data).

You should then ensure that the qt module is added to your
`.kdesrc-buildrc`, before any other modules in the file. If you are
using the sample configuration file, you can simply uncomment the
existing qt module entry.

Now you should verify the [repository](#conf-repository) option and
[branch](#conf-branch) options are set appropriately:

1.  The first option is to build Qt using a mirror maintained on the KDE
    source repositories (no other changes are applied, it is simply a
    clone of the official source). This is highly recommended due to
    occasional issues with cloning the full Qt module from its official
    repository.

    You can set the `repository` option for the qt module to `kde:qt` to
    use this option.

2.  Otherwise, to build the standard Qt, set your `repository` option to
    `git://gitorious.org/qt/qt.git`. Note that you may experience
    problems performing the initial clone of Qt from this repository.

In both cases, the branch option should be set to `master` (unless you'd
like to build a different branch).

(kde-builder-std-flags)=
## Standard flags added by kde-builder

Nota Bene: this section does not apply to modules for which you have
configured a custom toolchain, using e.g.
[cmake-toolchain](#conf-cmake-toolchain).

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

(build-priority)=
## Changing kde-builder's build priority

Programs can run with different priority levels on Operating Systems,
including Linux and BSD. This allows the system to allocate time for the
different programs in accordance with how important they are.

kde-builder will normally allocate itself a low priority so that the
rest of the programs on your system are unaffected and can run normally.
Using this technique, kde-builder will use extra CPU when it is
available.

kde-builder will still maintain a high enough priority level so that it
runs before routine batch processes and before CPU donation programs
such as [Seti@Home](http://setiathome.ssl.berkeley.edu/).

To alter kde-builder so that it uses a higher (or lower) priority level
permanently, then you need to adjust the [niceness](#conf-niceness)
setting in the [configuration file](../getting-started/configure-data). The
[niceness](#conf-niceness) setting controls how “nice” kde-builder is
to other programs. In other words, having a higher
[niceness](#conf-niceness) gives kde-builder a lower priority. So to
give kde-builder a higher priority, reduce the
[niceness](#conf-niceness) (and vice versa). The
[niceness](#conf-niceness) can go from 0 (not nice at all, highest
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

```
% kde-builder --nice=15
```
Or, you can edit the [configuration file](../getting-started/configure-data) to make the
change permanent:

```
niceness 15
```

```{tip}
The [niceness](#conf-niceness) option only affects the usage of the
computer's processor(s). One other major affect on computer performance
relates to how much data input or output (I/O) a program uses. In order
to control how much I/O a program can use, modern Linux operating
systems support a similar tool called ionice. kde-builder supports
ionice, (but only to enable or disable it completely) using the
[use-idle-io-priority](#conf-use-idle-io-priority) option, since
kde-builder version 1.12.
```

(root-installation)=
## Installation as the superuser

You may wish to have kde-builder run the installation with super user
privileges. This may be for the unrecommended system-wide installation.
This is also useful when using a recommended single user KDE build,
however. This is because some modules (especially kdebase) install
programs that will briefly need elevated permissions when run. They are
not able to achieve these permission levels unless they are installed
with the elevated permissions.

You could simply run kde-builder as the super user directly, but this
is not recommended, since the program has not been audited for that kind
of use. Although it should be safe to run the program in this fashion,
it is better to avoid running as the super user when possible.

To take care of this, kde-builder provides the
[make-install-prefix](#conf-make-install-prefix) option. You can use
this option to specify a command to use to perform the installation as
another user. The recommended way to use this command is with the Sudo
program, which will run the install command as the super user.

For example, to install all modules using Sudo, you could do something
like this:

```
global
  make-install-prefix sudo
  # Other options
end global
```

To use [make-install-prefix](#conf-make-install-prefix) for only a
single module, this would work:

```
module some-module-name
  make-install-prefix sudo
end module
```

(build-progress)=
## Showing the progress of a module build

This feature is always available, and is automatically enabled when
possible. What this does is display an estimated build progress while
building a module; that way you know about how much longer it will take
to build a module.
