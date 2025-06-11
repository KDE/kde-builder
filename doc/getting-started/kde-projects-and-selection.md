(kde-projects-and-selection)=
# Project Organization and selection

(kde-layers)=
## KDE Software Organization

KDE software is split into different components, many of which can be
built by KDE Builder. Understanding this organization will help you
properly select the projects that you want built.

1.  At the lowest level comes the Qt library, which is a very powerful,
    cross-platform "toolkit" library. KDE is based on Qt, and some of
    the non-KDE libraries required by KDE are also based on Qt.
    KDE Builder can build Qt, or use the one already installed on your
    system if it is a recent enough version.

2.  On top of Qt are required libraries that are necessary for KDE
    software to work. Some of these libraries are not considered part of
    KDE itself due to their generic nature, but are still essential to
    the KDE Platform. These libraries are collected under a `kf6-support`
    project grouping but are not considered part of the "Frameworks"
    libraries.

3.  On top of these essential libraries come the [KDE
    Frameworks](https://community.kde.org/Frameworks), sometimes
    abbreviated as KF, which are essential libraries for the KDE Plasma
    desktop, KDE Applications, and other third-party software.

4.  On top of the Frameworks, come several different things:

    - "Third-party" applications. These are applications that use the
      KDE Frameworks or are designed to run under KDE Plasma but are not
      authored by or in association with the KDE project.

    - Plasma, which is a full "workspace" desktop environment. This is
      what users normally see when they "log-in to KDE".

    - The KDE Application suite. This is a collection of useful software
      included with the Platform and Plasma Desktop, grouped into
      individual projects, including utilities like Dolphin, games like
      KSudoku, and productivity software released by KDE such as
      Kontact.

    - Finally, there is a collection of software (also collected in
      projects) whose development is supported by KDE resources (such as
      translation, source control, bug tracking, etc.) but is not
      released by KDE as part of Plasma or the Application suite. These
      projects are known as "Extragear".

(selecting-projects)=
## Selecting projects to build

Selecting which of the possible projects to build is controlled by [the
configuration file](../configuration/config-file-overview). After the `global` section is a
list of projects to build. An example entry for a project is shown below:

```{code-block} yaml
:name: conf-project-example
:caption:  Example project entry in the configuration file

project dummy-project:
  repository: kde:sysadmin/dummy
  make-options: -j4 # Run 4 compiles at a time
```

```{note}
In practice, this project construct is not usually used directly. Instead
most projects are specified via groups as described below.
```

Note that the order in which `project` entries are appeared in config does matter.
If KDE Builder cannot understand project dependencies, for example, when projects are third-party and not described,
and you select several such projects in the command line, KDE Builder will build them in the order
you list them in config.

(groups)=
## Groups

The KDE source code is decomposed into a great number of relatively
small git repositories. To make it easier to manage the large
number of repositories involved in any useful KDE-based install,
KDE Builder supports grouping multiple projects and treating the group
as a "group".

(group-concept)=
### The basic group concept

By using a group, you can quickly declare many projects, as if you'd typed out a separate project
nodes for each one. Every option contained in the group is copied to every project
generated in this fashion.

```{code-block} yaml
:name: example-using-groups
:caption: Using groups

global:
  git-repository-base: kde-git kde:

project qt:
  # Options removed for brevity

group kde-support-libs:
  repository: kde-git
  use-projects:
    - automoc
    - attica
    - akonadi

# Other projects as necessary...
project kdesupport:
  ...
```

In the example above, a brief group is
shown. When KDE Builder encounters this group, it acts as if, for
every project given in `use-projects`, that an individual project has been
declared.

In addition, other options can be passed in a group, which are
copied to every new project that is created this way. By using group,
it is possible to quickly declare many projects that are all based on
the same repository URL. In addition, it is possible to give groups
a name (as shown in the example), which allows you to quickly refer to
the entire group of projects from the command line.

See also [git-repository-base](#conf-git-repository-base) option.

(groups-kde)=
### Special Support for KDE groups

The group support described so far is general to any
projects. For the KDE repositories, KDE Builder includes additional
features to make things easier for users and developers. This support is enabled
by not overriding `repository` option - when its default value `kde-projects`
is applied.

With that value, KDE Builder can do dependency resolution of
KDE-specific projects, and in addition automatically include projects into
the build even if only indirectly specified.

```{code-block} yaml
:name: example-using-kde-groups
:caption: Using kde-projects groups

# When not specified, `repository: kde-projects` is used

# Only adds a project for juk (the kde/kdemultimedia/juk repo)
group juk-set:
  use-projects:
    - juk

# Adds all projects that are in kde/multimedia/*, including juk,
# but no other dependencies
group multimedia-set:
  use-projects:
    - kde/multimedia

# Adds all projects that are in kde/multimedia/*, and all kde-projects
# dependencies from outside of kde/kdemultimedia
group multimedia-deps-set:
  use-projects:
    - kde/multimedia
  include-dependencies: true

# All projects created out of these three groups are automatically put in
# proper dependency order, regardless of the setting for include-dependencies
```

All groups use [use-projects](#conf-use-projects) option.

(kde-projects-groups)=
## The official KDE project database

KDE projects in invent.kde.org are placed in groups, for example kdegraphics.
KDE Builder can understand these groups, using [groups](#groups)
with a `repository` option set to `kde-projects`.

KDE Builder will recognize that the `kde-projects` repository requires
special handling, and adjust the build process appropriately. Among
other things, KDE Builder will:

- Download the latest repository metadata (the repo which is a database about all other projects).

- Try to find a project with the name given in the group's
  `use-projects` setting in that database.

- For every project that is found, KDE Builder will lookup the
  appropriate repository in the database, based upon the
  [branch-group](#conf-branch-group) setting in effect. If a repository
  exists and is active for the branch group, KDE Builder will
  automatically use that to download or update the source code.

The following example shows how to use the KDE project database to
install the Phonon multimedia library.

```{code-block} yaml
group media-support:
  # This option must be kde-projects to use the project database.
  repository: kde-projects

  # This option chooses what projects to look for in the database.
  use-projects:
    - phonon/phonon
    - phonon-gstreamer
    - phonon-vlc
```

```{tip}
`phonon/phonon` is used since (with the current project database)
KDE Builder would otherwise have to decide between the group of
projects called "phonon" or the individual project named "phonon".
Currently KDE Builder would pick the former, which would build many
more backends than needed.
```

The following example is perhaps more realistic, and shows a feature
only available with the KDE project database: Building all of the KDE
graphics applications with only a single declaration.

```{code-block} yaml
group kdegraphics:
  # This option must be kde-projects to use the project database.
  repository: kde-projects

  # This option chooses what projects to look for in the database.
  use-projects:
    - kdegraphics/libs
    - kdegraphics/*
```

There are two important abilities demonstrated here:

1.  KDE Builder allows you to specify projects that are descendents of a
    given project, without building the parent project, by using the
    syntax `project-name/*`. It is actually required in this case since
    the base project, kdegraphics, is marked as inactive so that it is
    not accidentally built along with its children projects. Specifying
    the descendent projects allows KDE Builder to skip around the
    disabled project.

2.  KDE Builder will also not add a given project to the build list more
    than once. This allows us to manually set `kdegraphics/libs` to
    build first, before the rest of `kdegraphics`, without trying to
    build `kdegraphics/libs` twice. This used to be required for proper
    dependency handling, and today remains a fallback option in case the
    KDE project database is missing dependency metadata.

(ignoring-project-projects)=
## Filtering out KDE project projects

You might decide that you'd like to build all programs within a KDE
project grouping *except* for a given program.

For instance, the `kdeutils` group includes a program named
kremotecontrol. If your computer does not have the proper hardware to
receive the signals sent by remote controls then you may decide that
you'd rather not download, build, and install kremotecontrol every time
you update `kdeutils`.

You can achieve this by using the [ignore-projects](#conf-ignore-projects)
configuration option. Alternatively, you can use [--ignore-projects](#cmdline-ignore-projects) option in the command line
in case you want to [ignore](#ignoring-projects) some projects just once.

```{code-block} yaml
:name: example-ignoring-a-project
:caption: Example for ignoring a kde-project project in a group

group utils:
  # This option chooses what projects to look for in the database.
  use-projects:
    - kdeutils

  # This option "subtracts out" projects from the projects chosen by use-projects, above.
  ignore-projects:
    - kremotecontrol

group graphics:
  # This option chooses what projects to look for in the database.
  use-projects:
    - extragear/graphics

  # This option "subtracts out" projects from the projects chosen by use-projects, above.
  # In this case, *both* extragear/graphics/kipi-plugins and
  # extragear/graphics/kipi-plugins/kipi-plugins-docs are ignored
  ignore-projects:
    - extragear/graphics/kipi-plugins
```
