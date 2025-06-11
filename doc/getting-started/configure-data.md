(configure-data)=
# Editing the configuration file

In the previous page, it was [described](#generate-rcfile) how to generate the configuration file.
The default location is in `~/.config/kde-builder.yaml`.

The default settings should be appropriate to perform a KDE build. Some
settings that you may wish to alter include:

- [branch-group](#conf-branch-group), which can be used to choose the
  appropriate branch of development for the KDE projects as a whole.
  There are many supported build configurations, but you will likely want
  to choose `kf6-qt6` so that KDE Builder downloads the latest code
  based on Qt 6 and KDE Frameworks 6.

```{tip}
  KDE Builder will use a default branch group if you do not choose one,
  but this default will change over time, so it's better to choose one
  so that the branch group does not change unexpectedly.
```

- [source-dir](#conf-source-dir), to control the directory KDE Builder
  uses for downloading the source code. This defaults to `~/kde/src`.

- [install-dir](#conf-install-dir), which changes the destination
  directory that your KDE software is installed to. This defaults to
  `~/kde/usr`, which is a single-user installation.

- [cmake-options](#conf-cmake-options), which sets the options to pass
  to the CMake command when building each project. Typically, this is used
  to set between "debug" or "release" builds, to enable (or disable)
  optional features, or to pass information to the build process about
  the location of required libraries.

```{tip}
KDE Builder sets the option `num-cores` to the detected number of
available processing cores. You can use this value in your own
configuration file to avoid having to set it manually.
```

```{code-block} yaml
:name: make-options-example
:caption: Configuring Make to use all available CPUs, with exceptions

global:
  # This environment variable is automatically used by make, including
  # make commands not run by KDE Builder directly, such as Qt's configure
  set-env:
    MAKEFLAGS: -j${num-cores}
  …

…

group big-group:
  repository: kde-projects
  use-projects:
    - calligra
  make-options: -j2 # Reduced number of build jobs for just these projects
```

```{note}
Some very large Git repositories may swamp your system if you try to
compile with a too many build jobs at one time, especially
repositories like the Qt WebEngine repository. To
maintain system interactivity you may have to reduce the number of
build jobs for specific projects.

[](#make-options-example) gives an example of how to do
this.
```
