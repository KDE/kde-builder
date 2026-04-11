(building-qt)=
# Building Qt

KDE Builder supports building the Qt toolkit used by KDE software as a
convenience to users. This support is handled by a special group
named `qt6-set`. It is defined [here](https://invent.kde.org/sysadmin/repo-metadata/-/blob/master/build-configs/qt6.yaml?ref_type=heads).

```{note}
Qt is developed under a separate repository from KDE software located at
<https://code.qt.io/cgit/qt/>.
```

In order to build Qt, you should make sure that the
[qt-install-dir](#conf-qt-install-dir) option is set to the directory
you'd like to install Qt to, as described in the section called [](../getting-started/configure-data).

Now check if you are using default build configs. This is done by this config line:

```yaml
include ${build-configs-dir}/kde6.yaml: ""
```

If this is the case, you are on a safe side.

If for some reason you are not using default build configs, then you should ensure that
the `qt6-set` group is added to your `kde-builder.yaml` _before_ any other projects in the file.
Then you should verify that the [repository](#conf-repository) option and
[branch](#conf-branch) options are set appropriately.

The `repository` option if set to "qt6-copy", is to build Qt using a mirror maintained on the KDE
source repositories (no other changes are applied, it is simply a
clone of the official source). This is highly recommended due to
occasional issues with cloning the full Qt framework from its official
repository.

You can find out available branches [here](https://invent.kde.org/qt/qt/qtbase/-/branches).

Most likely, you would want to exclude qtwebengine from building, as it has significant build requirements.
To do this, add it to "ignore-projects" in your config:

```yaml
global:
  ignore-projects:
    - qtwebengine
```

Now you can just run the following command:

```bash
kde-builder qt6-set
```
