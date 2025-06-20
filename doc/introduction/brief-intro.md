(brief-intro)=
# A brief introduction to kde-builder

(whatis-kde-builder)=
## What is KDE Builder

KDE Builder is a tool to help the KDE community install
KDE software from its git source repositories, and continue to update
that software afterwards. It is particularly intended to support those
who need to test and develop of KDE software,
including users testing bugfixes and developers working on new features.

The KDE Builder tool can be configured to maintain a single
individual project, a full Plasma desktop with KDE application set, or
somewhere in between.

To get started, see [](../getting-started/index), or continue reading for
more details on how KDE Builder works and what is covered in this
documentation.

(kb-operation)=
## KDE Builder operation

KDE Builder works by using the tools available to the user at the
command line, using the same interfaces available to the user. When
KDE Builder is run, the following sequence is followed:

1.  KDE Builder reads in the [command line](../cmdline/cmdline-usage) and
    [configuration file](../getting-started/configure-data), to determine what to build,
    compile options to use, where to install, etc.

2.  KDE Builder performs a source update for each
    project. The update continues until all projects
    have been updated. Projects that fail to update normally do not stop
    the build – you will be notified at the end which projects did not
    update.

3.  Projects that were successfully updated are built, have their test
    suite run, and are then installed. To reduce the overall time spent,
    kde-builder will by default start building the code as soon as the
    first project has completed updating, and allow the remaining updates
    to continue behind the scenes.
