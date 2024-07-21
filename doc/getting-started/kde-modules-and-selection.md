(kde-modules-and-selection)=
# Module Organization and selection

(kde-layers)=
## KDE Software Organization

KDE software is split into different components, many of which can be
built by KDE Builder. Understanding this organization will help you
properly select the software modules that you want built.

1.  At the lowest level comes the Qt library, which is a very powerful,
    cross-platform "toolkit" library. KDE is based on Qt, and some of
    the non-KDE libraries required by KDE are also based on Qt.
    KDE Builder can build Qt, or use the one already installed on your
    system if it is a recent enough version.

2.  On top of Qt are required libraries that are necessary for KDE
    software to work. Some of these libraries are not considered part of
    KDE itself due to their generic nature, but are still essential to
    the KDE Platform. These libraries are collected under a `kdesupport`
    module grouping but are not considered part of the "Frameworks"
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
      individual modules, including utilities like Dolphin, games like
      KSudoku, and productivity software released by KDE such as
      Kontact.

    - Finally, there is a collection of software (also collected in
      modules) whose development is supported by KDE resources (such as
      translation, source control, bug tracking, etc.) but is not
      released by KDE as part of Plasma or the Application suite. These
      modules are known as "Extragear".

(selecting-modules)=
## Selecting modules to build

Selecting which of the possible modules to build is controlled by [the
configuration file](../kdesrc-buildrc/kdesrc-buildrc-overview). After the `global` section is a
list of modules to build, bracketed by module ... end module lines. An
example entry for a module is shown below:

```{code-block} text
:name: conf-module-example
:caption:  Example module entry in the configuration file

module kde-builder-git
    # Options for this module go here, example:
    repository kde:kde-builder
    make-options -j4 # Run 4 compiles at a time
end module
```

```{note}
In practice, this module construct is not usually used directly. Instead
most modules are specified via module-sets as described below.
```

When using only `module` entries, KDE Builder builds them in the order
you list, and does not attempt to download any other repositories other
than what you specify directly.

(module-sets)=
## Module Sets

The KDE source code is decomposed into a great number of relatively
small git repositories. To make it easier to manage the large
number of repositories involved in any useful KDE-based install,
KDE Builder supports grouping multiple modules and treating the group
as a "module set".

(module-set-concept)=
### The basic module set concept

By using a module set, you can quickly declare many git modules to be
downloaded and built, as if you'd typed out a separate module
declaration for each one. The [repository](#conf-repository) option is
handled specially to setup where each module is downloaded from, and
every other option contained in the module set is copied to every module
generated in this fashion.

```{code-block} text
:name: example-using-module-sets
:caption: Using module sets

global
    git-repository-base kde-git kde:
end global

module qt
    # Options removed for brevity
end module

module-set kde-support-libs
    repository kde-git
    use-modules automoc attica akonadi
end module-set

# Other modules as necessary...
module kdesupport
end module
```

In the example above, a brief module set is
shown. When KDE Builder encounters this module set, it acts as if, for
every module given in `use-modules`, that an individual module has been
declared, with its `repository` equal to the module-set's `repository`
followed immediately by the given module name.

In addition, other options can be passed in a module set, which are
copied to every new module that is created this way. By using module-set,
it is possible to quickly declare many modules that are all based on
the same repository URL. In addition, it is possible to give module-sets
a name (as shown in the example), which allows you to quickly refer to
the entire group of modules from the command line.

(module-sets-kde)=
### Special Support for KDE module sets

The module set support described so far is general to any
modules. For the KDE repositories, KDE Builder includes additional
features to make things easier for users and developers. This support is
enabled by specifying `kde-projects` as the `repository` for the module
set.

KDE Builder normally only builds the modules you have listed in your
configuration file, in the order you list them. But with a
`kde-projects` module set, KDE Builder can do dependency resolution of
KDE-specific modules, and in addition automatically include modules into
the build even if only indirectly specified.

```{code-block} text
:name: example-using-kde-module-sets
:caption: Using kde-projects module sets

# Only adds a module for juk (the kde/kdemultimedia/juk repo)
module-set juk-set
    repository kde-projects
    use-modules juk
end module-set

# Adds all modules that are in kde/multimedia/*, including juk,
# but no other dependencies
module-set multimedia-set
    repository kde-projects
    use-modules kde/multimedia
end module-set

# Adds all modules that are in kde/multimedia/*, and all kde-projects
# dependencies from outside of kde/kdemultimedia
module-set multimedia-deps-set
    repository kde-projects
    use-modules kde/multimedia
    include-dependencies true
end module-set

# All modules created out of these three module sets are automatically put in
# proper dependency order, regardless of the setting for include-dependencies
```

```{tip}
This `kde-projects` module set construct is the main method of declaring
which modules you want to build.
```

All module sets use the [repository](#conf-repository) and
[use-modules](#conf-use-modules) options.
[`kde-projects`](#kde-projects-module-sets) module sets have a
predefined `repository` value, but other types of module sets also will
use the [git-repository-base](#conf-git-repository-base) option.

(kde-projects-module-sets)=
## The official KDE module database

KDE projects in invent.kde.org are placed in groups, for example kdegraphics.
KDE Builder can understand these groups, using [module sets](#module-sets)
with a `repository` option set to `kde-projects`.

KDE Builder will recognize that the `kde-projects` repository requires
special handling, and adjust the build process appropriately. Among
other things, KDE Builder will:

- Download the latest repository metadata (the repo which is a database about all other projects).

- Try to find a module with the name given in the module set's
  `use-modules` setting in that database.

- For every module that is found, KDE Builder will lookup the
  appropriate repository in the database, based upon the
  [branch-group](#conf-branch-group) setting in effect. If a repository
  exists and is active for the branch group, KDE Builder will
  automatically use that to download or update the source code.

The following example shows how to use the KDE module database to
install the Phonon multimedia library.

```{code-block}
module-set media-support
    # This option must be kde-projects to use the module database.
    repository kde-projects

    # This option chooses what modules to look for in the database.
    use-modules phonon/phonon phonon-gstreamer phonon-vlc
end module-set
```

```{tip}
`phonon/phonon` is used since (with the current project database)
KDE Builder would otherwise have to decide between the group of
projects called “phonon” or the individual project named “phonon”.
Currently KDE Builder would pick the former, which would build many
more backends than needed.
```

The following example is perhaps more realistic, and shows a feature
only available with the KDE module database: Building all of the KDE
graphics applications with only a single declaration.

```{code-block}
module-set kdegraphics
    # This option must be kde-projects to use the module database.
    repository kde-projects

    # This option chooses what modules to look for in the database.
    use-modules kdegraphics/libs kdegraphics/*
end module-set
```

There are two important abilities demonstrated here:

1.  KDE Builder allows you to specify modules that are descendents of a
    given module, without building the parent module, by using the
    syntax `module-name/*`. It is actually required in this case since
    the base module, kdegraphics, is marked as inactive so that it is
    not accidentally built along with its children modules. Specifying
    the descendent modules allows KDE Builder to skip around the
    disabled module.

2.  KDE Builder will also not add a given module to the build list more
    than once. This allows us to manually set `kdegraphics/libs` to
    build first, before the rest of `kdegraphics`, without trying to
    build `kdegraphics/libs` twice. This used to be required for proper
    dependency handling, and today remains a fallback option in case the
    KDE project database is missing dependency metadata.

(ignoring-project-modules)=
## Filtering out KDE project modules

You might decide that you'd like to build all programs within a KDE
module grouping *except* for a given program.

For instance, the `kdeutils` group includes a program named
kremotecontrol. If your computer does not have the proper hardware to
receive the signals sent by remote controls then you may decide that
you'd rather not download, build, and install kremotecontrol every time
you update `kdeutils`.

You can achieve this by using the [ignore-modules](#conf-ignore-modules)
configuration option. Alternatively, you can use [--ignore-modules](#cmdline-ignore-modules) option in the command line
in case you want to [ignore](#ignoring-modules) some modules just once.

```{code-block} text
:name: example-ignoring-a-module
:caption: Example for ignoring a kde-project module in a group

module-set utils
    repository kde-projects

    # This option chooses what modules to look for in the database.
    use-modules kdeutils

    # This option "subtracts out" modules from the modules chosen by use-modules, above.
    ignore-modules kremotecontrol
end module-set

module-set graphics
    repository kde-projects

    # This option chooses what modules to look for in the database.
    use-modules extragear/graphics

    # This option "subtracts out" modules from the modules chosen by use-modules, above.
    # In this case, *both* extragear/graphics/kipi-plugins and
    # extragear/graphics/kipi-plugins/kipi-plugins-docs are ignored
    ignore-modules extragear/graphics/kipi-plugins
end module-set
```
