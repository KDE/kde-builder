(appendix-modules)=
# KDE modules and source code organization

(module-concept)=
## The “Module”

KDE groups its software into “modules” of various size. This was
initially a loose grouping of a few large modules, but with the
introduction of the [Git](https://git-scm.com/)-based [source code
repositories](https://commits.kde.org/), these large modules were
further split into many smaller modules.

kde-builder uses this module concept as well. In essence, a “module” is
a grouping of code that can be downloaded, built, tested, and installed.

(single-modules)=
### Individual modules

It is easy to set kde-builder to build a single module. The following
listing is an example of what a declaration for a Git-based module would
look like in [the configuration file](../chapter_04/kdesrc-buildrc).

```
module kdefoo
    cmake-options -DCMAKE_BUILD_TYPE=Debug
end module
```

```{tip}
This is a Git-based module since it doesn't use a
[repository](#conf-repository) option. Also, the `cmake-options` option
is listed as an example only, it is not required.
```

(module-groups)=
### Groups of related modules

Now most KDE source modules are Git-based KDE, and are normally combined
into groups of modules.

kde-builder therefore supports groups of modules as well, using [module
sets](#module-sets). An example:

```
module-set base-modules
    repository kde-projects
    use-modules kde-runtime kde-workspace kde-baseapps
end module-set
```

```{tip}
You can leave the module set name (\<base-modules\> in this case) empty
if you like. This `repository` setting tells kde-builder where to
download the source from, but you can also use a `git://` URL.
```

One special feature of the “`repository` `kde-projects`” is that
kde-builder will automatically include any Git modules that are grouped
under the modules you list (in the KDE Project database).

(module-branch-groups)=
### Module “branch groups”

Taking the concept of a [group of modules](#module-groups) further, the
KDE developers eventually found that synchronizing the names of the Git
branches across a large number of repositories was getting difficult,
especially during the development push for the new KDE Frameworks for Qt 5.

So the concept of “branch groups” was developed, to allow users and
developers to select one of only a few groups, and allow the script to
automatically select the appropriate Git branch.

kde-builder supports this feature as of version 1.16-pre2, via the
[branch-group](#conf-branch-group) option.

branch-group can be used in the configuration file as follows:

```{code-block}
:name: ex-branch-group
:caption: Example of using branch-group

global
    # Select KDE Frameworks 5 and other Qt5-based apps
    branch-group kf5-qt5

    # Other global options here ...
end global

module-set
    # branch-group only works for kde-projects
    repository kde-projects

    # branch-group is inherited from the one set globally, but could
    # specified here.

    use-modules kdelibs kde-workspace
end module-set

# kdelibs's branch will be "frameworks"
# kde-workspace's branch will be "master" (as of August 2013)
```

In this case the same `branch-group` gives different branch names for
each Git module.

This feature requires some data maintained by the KDE developers in a
Git repository named `kde-build-metadata`, however this module will be
included automatically by kde-builder (though you may see it appear in
the script output).

```{tip}
KDE modules that do not have a set branch name for the branch group you
choose will default to an appropriate branch name, as if you had not
specified `branch-group` at all.
```
