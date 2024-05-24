(brief-intro)=
# A brief introduction to kde-builder

(whatis-kde-builder)=
## What is kde-builder?

kde-builder is a script to help the KDE community install
[KDE](https://www.kde.org/) software from its
[Git](https://git-scm.com/) source repositories, and continue to update
that software afterwards. It is particularly intended to support those
who need to supporting testing and development of KDE software,
including users testing bugfixes and developers working on new features.

The kde-builder script can be configured to maintain a single
individual module, a full Plasma desktop with KDE application set, or
somewhere in between.

To get started, see [](../getting-started/index), or continue reading for
more detail on how kde-builder works and what is covered in this
documentation.

(operation-in-a-nutshell)=
## kde-builder operation “in a nutshell”

kde-builder works by using the tools available to the user at the
command-line, using the same interfaces available to the user. When
kde-builder is run, the following sequence is followed:

1.  kde-builder reads in the [command line](../cmdline/cmdline-usage) and
    [configuration file](../getting-started/configure-data), to determine what to build,
    compile options to use, where to install, etc

2.  kde-builder performs a source update for each
    [module](#module-concept). The update continues until all modules
    have been updated. Modules that fail to update normally do not stop
    the build – you will be notified at the end which modules did not
    update.

3.  Modules that were successfully updated are built, have their test
    suite run, and are then installed. To reduce the overall time spent,
    kde-builder will by default start building the code as soon as the
    first module has completed updating, and allow the remaining updates
    to continue behind the scenes.

```{tip}
A *very good* overview of how KDE modules are built, including
informative diagrams, is provided on [an online article discussing KDE's
Krita
application](https://www.davidrevoy.com/article193/guide-building-krita-on-linux-for-
cats). This workflow is what kde-builder automates for all KDE modules.
```
