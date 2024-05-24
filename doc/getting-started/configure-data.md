(configure-data)=
# Setting the Configuration Data

To use kde-builder, you should have a file in your `~/.config` (or in
`$XDG_CONFIG_HOME`, if set) directory called `kdesrc-buildrc`, which
sets the general options and specifies the modules you would like to
download and build.

```{note}
It is possible to use different configuration files for kde-builder,
which is described in [](../chapter_04/index). If you need to use
multiple configurations, please see that section. Here, we will assume
that the configuration is stored in `~/.config/kdesrc-buildrc`.
```

The easiest way to proceed is to use the `kdesrc-buildrc-kf5-sample`
file as a template, changing global options to match your wants, and
also change the list of modules you want to build.

The default settings should be appropriate to perform a KDE build. Some
settings that you may wish to alter include:

- [install-dir](#conf-install-dir), which changes the destination
  directory that your KDE software is installed to. This defaults to
  `~/kde/usr`, which is a single-user installation.

- [branch-group](#conf-branch-group), which can be used to choose the
  appropriate branch of development for the KDE modules as a whole.
  There are many supported build configurations but you will likely want
  to choose `kf5-qt5` so that kde-builder downloads the latest code
  based on Qt 5 and KDE Frameworks 5.

```{tip}
  kde-builder will use a default branch group if you do not choose one,
  but this default will change over time, so it's better to choose one
  so that the branch group does not change unexpectedly.
```

- [source-dir](#conf-source-dir), to control the directory kde-builder
  uses for downloading the source code, running the build process, and
  saving logs. This defaults to `~/kde/src`.

- [cmake-options](#conf-cmake-options), which sets the options to pass
  to the CMake command when building each module. Typically this is used
  to set between “debug” or “release” builds, to enable (or disable)
  optional features, or to pass information to the build process about
  the location of required libraries.

- [make-options](#conf-make-options), which sets the options used when
  actually running the make command to build each module (once CMake has
  established the build system).

  The most typical option is `-jN`, where \<N\> should be replaced with
  the maximum number of compile jobs you wish to allow. A higher number
  (up to the number of logical CPUs your system has available) leads to
  quicker builds, but requires more system resources.

```{tip}
  kde-builder sets the option `num-cores` to the detected number of
  available processing cores. You can use this value in your own
  configuration file to avoid having to set it manually.
```

```{code-block}
:name: make-options-example
:caption: Configuring Make to use all available CPUs, with exceptions

global
    # This environment variable is automatically used by make, including
    # make commands not run by kde-builder directly, such as Qt's configure
    set-env MAKEFLAGS -j${num-cores}
    …
end global

…

module-set big-module-set
    repository kde-projects
    use-modules calligra
    make-options -j2 # Reduced number of build jobs for just these modules
end module-set
```

```{note}
Some very large Git repositories may swamp your system if you try to
compile with a too many build jobs at one time, especially
repositories like the Qt WebKit and Qt WebEngine repositories. To
maintain system interactivity you may have to reduce the number of
build jobs for specific modules.

[](#make-options-example) gives an example of how to do
this.
```

You may want to select different modules to build, which is described in
the section called [](#selecting-modules).
