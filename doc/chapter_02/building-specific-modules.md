(building-specific-modules)=
# Building specific modules

Rather than building every module all the time, you may only want to
build a single module, or other small subset. Rather than editing your
configuration file, you can simply pass the names of modules or module
sets to build to the command line.

```{code-block} none
:name: example-subset-build
:caption: Example output of a kde-builder specific module build

% kde-builder --include-dependencies dolphin
Updating kde-build-metadata (to branch master)
Updating sysadmin-repo-metadata (to branch master)

Building extra-cmake-modules from frameworks-set (1/79)
        Updating extra-cmake-modules (to branch master)
        No changes to extra-cmake-modules source, proceeding to build.
        Running cmake...
        Compiling... succeeded (after 0 seconds)
        Installing.. succeeded (after 0 seconds)

Building phonon from phonon (2/79)
        Updating phonon (to branch master)
        No changes to phonon source, proceeding to build.
        Compiling... succeeded (after 0 seconds)
        Installing.. succeeded (after 0 seconds)

Building attica from frameworks-set (3/79)
        Updating attica (to branch master)
        No changes to attica source, proceeding to build.
        Compiling... succeeded (after 0 seconds)
        Installing.. succeeded (after 0 seconds)

        ...

Building dolphin from base-apps (79/79)
        Updating dolphin (to branch master)
        No changes to dolphin source, proceeding to build.
        Compiling... succeeded (after 0 seconds)
        Installing.. succeeded (after 0 seconds)

<<<  PACKAGES SUCCESSFULLY BUILT  >>>
Built 79 modules

Your logs are saved in /home/kde-src/kdesrc/log/2018-01-20-07
```

In this case, although only the \<dolphin\> application was specified,
the `--include-dependencies` flag caused kde-builder to include the
dependencies listed for \<dolphin\> (by setting the
[include-dependencies](#conf-include-dependencies) option).

```{note}
The dependency resolution worked in this case only because \<dolphin\>
happened to be specified in a `kde-projects`-based module set (in this
example, named `base-apps`). See the section called [](#module-sets-kde).
```
