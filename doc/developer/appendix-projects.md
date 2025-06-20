(appendix-projects)=
# KDE projects and source code organization

(single-projects)=
## Individual projects

It is easy to set kde-builder to build a single project. The following
listing is an example of what a declaration for a project would
look like in [the configuration file](../configuration/config-file-overview).

```text
project kdefoo:
  cmake-options: -DCMAKE_BUILD_TYPE=Debug
```

```{tip}
This is a git-based project since it doesn't use a
[repository](#conf-repository) option. Also, the `cmake-options` option
is listed as an example only, it is not required.
```

(project-groups)=
## Groups of related projects

Now most KDE source projects are git-based KDE, and are normally combined
into groups of projects.

kde-builder therefore supports groups of projects as well, using [groups](#groups). An example:

```yaml
group base-projects:
  repository: kde-projects
  use-projects:
    - kde-runtime
    - kde-workspace
    - kde-baseapps
```

```{tip}
This `repository` setting tells kde-builder where to
download the source from, but you can also use a `git://` URL.
```

One special feature of the "repository: kde-projects" is that
kde-builder will automatically include any projects that are grouped
under the projects you list (in the KDE Project database).

(project-branch-groups)=
## Project "branch groups"

Taking the concept of a [group of projects](#project-groups) further, the
KDE developers eventually found that synchronizing the names of the git
branches across a large number of repositories was getting difficult,
especially during the development push for the new KDE Frameworks for Qt 5.

So the concept of "branch groups" was developed, to allow users and
developers to select one of only a few groups, and allow the kde-builder to
automatically select the appropriate git branch.

branch-group can be used in the configuration file as follows:

```{code-block} yaml
:name: ex-branch-group
:caption: Example of using branch-group

global:
  # Select KDE Frameworks 6 and other Qt6-based apps
  branch-group: kf6-qt6

  # Other global options here ...

group name:
  # branch-group only works for kde-projects
  repository: kde-projects

  # branch-group is inherited from the one set globally, but could
  # be specified here.

  use-projects:
    - kdelibs
    - kde-workspace

# kdelibs's branch will be "frameworks"
# kde-workspace's branch will be "master" (as of August 2013)
```

In this case the same `branch-group` gives different branch names for
each project.

This feature requires some data maintained by the KDE developers in a
git repository named `repo-metadata`, however this project will be
included automatically by kde-builder (though you may see it appear in
the script output).

```{tip}
KDE projects that do not have a set branch name for the branch group you
choose will default to an appropriate branch name, as if you had not
specified `branch-group` at all.
```
