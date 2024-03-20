(kdesrc-buildrc-overview)=
# Overview of kde-builder configuration

To use the script, you must have a file in your home directory called
`.kdesrc-buildrc`, which describes the modules you would like to
download and build, and any options or configuration parameters to use
for these modules.

(kdesrc-buildrc-layout)=
## Layout of the configuration file

(kdesrc-buildrc-layout-global)=
### Global configuration

The configuration file starts with the global options, specified like
the following:

```
global
    option-name option-value
    [...]
end global
```

(kdesrc-buildrc-layout-modules)=
### Module configuration

It is then followed by one or more module sections, specified in one of
the following two forms:

- 
```
module module-name
  option-name option-value
  [...]
end module
```
-
```
module-set module-set-name
  repository kde-projects or git://host.org/path/to/repo.git
  use-modules module-names

  # Other options may also be set
  option-name option-value
  [...]
end module-set
```

```{important}
Note that the second form, module sets, *only works for Git-based
modules*.
```

For Git modules, \<module-name\> must be a module from the KDE Git
repository (for example, kdeartwork or kde-wallpapers).

For Git modules, the module name can be essentially whatever you'd like,
as long as it does not duplicate any other module name in the
configuration. Keep in mind the source and build directory layout will
be based on the module name if you do not use the
[dest-dir](#conf-dest-dir) option.

However, for Git *module sets* the \<module-names\> must correspond with
actual git modules in the chosen `repository`. See
[git-repository-base](#conf-git-repository-base) or
[use-modules](#conf-use-modules) for more information.

(kdesrc-buildrc-option-values)=
### Processing of option values

In general, the entire line contents after the \<option-name\> is used
as the \<option-value\>.

One modification that kde-builder performs is that a sequence
"`${name-of-option}`" is replaced with the value of that option from the
global configuration. This allows you to reference the value of existing
options, including options already set by kde-builder.

To see an example of this in use, see [](#make-options-example).

You can also introduce your own non-standard global variables for
referencing them further in the config. To do this, your option name
should be prepended with underscore symbol. Example:

```{code-block}
:name: custom-global-option-example
:caption: Introducing your own global option for referencing later in config

global
  _ver 6  # ← your custom variable (starting with underscore)
  _kde ~/kde${_ver}  # ← custom variable can contain another defined variable
  source-dir ${_kde}/src  # ← note that nested variable (_kde → _ver) is also resolved
end global

options kdepim
  log-dir /custom/path/logs${_ver} # ← you can use custom variable just like a standard
end options
```

(kdesrc-buildrc-options-groups)=
### “options” modules

There is a final type of configuration file entry, `options` groups,
which may be given wherever a `module` or `module-set` may be used.

```
options module-name
  option-name option-value
  [...]
end options
```

An `options` group may have options set for it just like a module
declaration, and is associated with an existing module. Any options set
these way will be used to *override* options set for the associated
module.

```{important}
The associated module name *must* match the name given in the `options`
declaration. Be careful of mis-typing the name.
```

This is useful to allow for declaring an entire `module-set` worth of
modules, all using the same options, and then using `options` groups to
make individual changes.

`options` groups can also apply to named module sets. This allows expert
users to use a common configuration file (which includes `module-set`
declarations) as a baseline, and then make changes to the options used
by those module-sets in configuration files that use the `include`
command to reference the base configuration.

In this example we choose to build all modules from the KDE multimedia
software grouping. However we want to use a different version of the
KMix application (perhaps for testing a bug fix). It works as follows:

```{code-block}
:name: ex-options-group
:caption: Example of using options

module-set kde-multimedia-set
  repository kde-projects
  use-modules kde/kdemultimedia
  branch master
end module-set

# kmix is a part of kde/kdemultimedia group, even though we never named
# kmix earlier in this file, kde-builder will figure out the change.
options kmix
  branch KDE/4.12
end options
```

Now when you run kde-builder, all of the KDE multimedia programs will
be built from the “master” branch of the source repository, but KMix
will be built from the older “KDE/4.12” branch. By using `options` you
didn't have to individually list all the *other* KDE multimedia programs
to give them the right branch option.

```{note}
Note that this feature is only available in kde-builder from version
1.16, or using the development version of kde-builder after 2014-01-12.
```

(kdesrc-buildrc-including)=
## Including other configuration files

Within the configuration file, you may reference other files by using
the `include` keyword with a file, which will act as if the file
referenced had been inserted into the configuration file at that point.

For example, you could have something like this:

```
global
    include ~/common-kde-builder-options

    # Insert specific options here.

end global
```

```{note}
If you don't specify the full path to the file to include, then the file
will be searched for starting from the directory containing the source
file. This works recursively as well.
```

You can use variables in the value of include instruction:

```
global
  _ver 6
  source-dir ~/kde${_ver}/src
  ...
  persistent-data-file ~/kde${_ver}/persistent-options.json
end global

include ~/kde6/src/kde-builder/data/build-include/kf${_ver}-qt${_ver}.ksb
```

(kdesrc-buildrc-common)=
## Commonly used configuration options

The following is a list of commonly-used options. Click on the option to
find out more about it. To see the full list of options, see the section called
[](./conf-options-table).

- [cmake-options](#conf-cmake-options) to define what flags to configure
  a module with using CMake.

- [branch](#conf-branch), to checkout from a branch instead of `master`.

- [configure-flags](#conf-configure-flags) to define what flags to
  configure Qt with.

- [install-dir](#conf-install-dir), to set the directory to install KDE
  to.

- [make-options](#conf-make-options), to pass options to the Make
  program (such as number of CPUs to use).

- [qt-install-dir](#conf-qt-install-dir), to set the directory to
  install Qt to.

- [source-dir](#conf-source-dir), to change where to download the source
  code to.


