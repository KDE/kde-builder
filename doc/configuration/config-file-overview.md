(config-file-overview)=
# Overview of kde-builder configuration

(config-file-layout)=
## Layout of the configuration file

(config-file-layout-global)=
### Global configuration

The configuration file starts with the global options, specified like the following:

```yaml
global:
  option-name: option-value
  [...]
```

(config-file-layout-projects)=
### Project configuration

It is then followed by one or more project sections, specified in one of
the following two forms:


```yaml
project project-name:
  option-name: option-value
  [...]
```

```yaml
group group-name:
  repository: kde-projects # or git://host.org/path/to/repo.git
  use-projects:
    - project-names

  # Other options may also be set
  option-name: option-value
  [...]
```

For *project* node, \<project-name\> must be a project from KDE
repository (for example, kdeartwork or kde-wallpapers).
The \<project-name\> can be essentially whatever you'd like,
as long as it does not duplicate any other project name in the
configuration. Keep in mind the source and build directory layout will
be based on the project name if you do not use the
[dest-dir](#conf-dest-dir) option.

For *group* node, the \<group-name\> must correspond with
actual projects in the chosen `repository`. See
[git-repository-base](#conf-git-repository-base) or
[use-projects](#conf-use-projects) for more information.

(config-file-option-values)=
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

```{code-block} yaml
:name: custom-global-option-example
:caption: Introducing your own global option for referencing later in config

global:
  _ver: 6  # ← your custom variable (starting with underscore)
  _kde: ~/kde${_ver}  # ← custom variable can contain another defined variable
  source-dir: ${_kde}/src  # ← note that nested variable (_kde → _ver) is also resolved

override kdepim:
  log-dir: /custom/path/logs${_ver} # ← you can use custom variable just like a standard one
```

(config-file-override-nodes)=
### Overriding configuration

There is a final type of configuration file entry, `override`,
which may be given whatever in `project` or `group` may be used.

```yaml
override project-name:
  option-name: option-value
  [...]
```

An `override` node may have options set for it just like a project
node, and is associated with an existing project. Any options set
in this way will be used to *override* options set for the associated
project.

```{important}
The associated project name *must* match the name given in the `override`
node. Be careful of mis-typing the name.
```

This is useful to allow for declaring an entire `group` full of
projects, all using the same options, and then using `override` nodes to
make individual changes.

`override` nodes can also apply to groups.

In this example we choose to build all projects from the KDE multimedia
software grouping. However, we want to use a different version of the
KMix application (perhaps for testing a bug fix). It works as follows:

```{code-block} yaml
:name: ex-override-node
:caption: Example of using override node

group kde-multimedia-group:
  repository: kde-projects
  use-projects:
    - kde/kdemultimedia
  branch: master

# kmix is a part of kde/kdemultimedia group, even though we never named
# kmix earlier in this file, kde-builder will figure out the change.
override kmix:
  branch: KDE/4.12
```

Now when you run kde-builder, all of the KDE multimedia programs will
be built from the "master" branch of the source repository, but KMix
will be built from the older “KDE/4.12” branch. By using `override` you
didn't have to individually list all the *other* KDE multimedia programs
to give them the right branch option.

(config-file-including)=
## Including other configuration files

Within the configuration file, you may reference other files by using
the `include` keyword with a file, which will act as if the file
referenced had been inserted into the configuration file at that point.

For example, you could have something like this:

```yaml
global:
  ...

include ~/some-file.yaml: ""
```

```{note}
If you don't specify the full path to the file to include, then the file
will be searched for starting from the directory containing the source
file. This works recursively as well.
```

You can use variables in the value of include instruction:

```yaml
global:
  _ver: 6
  source-dir: ~/kde${_ver}/src
  ...
  persistent-data-file: ~/kde${_ver}/persistent-options.json

include ${build-configs-dir}/kde${_ver}.yaml: ""
```

(config-file-common)=
## Commonly used configuration options

The following is a list of commonly-used options. Click on the option to
find out more about it. To see the full list of options, see the section called
[](./conf-options-table).

- [cmake-options](#conf-cmake-options) to define what flags to configure
  a project with using CMake.

- [branch](#conf-branch) to checkout from a branch instead of `master`.

- [install-dir](#conf-install-dir) to set the directory where to install built projects.

- [make-options](#conf-make-options) to pass options to the `make`
  program (such as number of CPUs to use).

- [qt-install-dir](#conf-qt-install-dir) to set the directory where to install built Qt.

- [source-dir](#conf-source-dir) to change the directory where to download the source code.
