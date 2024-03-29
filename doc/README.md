# kde-builder Documentation

## kde-builder Tricks

These are some kde-builder tricks that probably should be documented with the
[KDE Community Wiki page](https://community.kde.org/Get_Involved/development#Set_up_kdesrc-build)
but for now they're at least worth nothing here:

- Use `kde-builder --rebuild-failures` (potentially with `--no-src`) to
  rebuild modules that failed to build during the last kde-builder run. This
  is particularly useful when a silly local error breaks an important module
  and several dozen dependent modules.

- Use the `--no-stop-on-failure` command-line option (or
  the corresponding configuration file option) to make kde-builder not abort
  after the first module fails to build.

- Either way if you're running kde-builder frequently as part of a
  debug/build/debug cycle, don't forget to throw `--no-src` on the command line
  as appropriate.  If the build failed halfway through it is likely that all
  source updates completed, even for modules kde-builder didn't try to build.

- It is possible to build many module types that are not official KDE projects.
  This may be needed for upstream dependencies or simply because you only need
  a module to support your KDE-based workspace or application.

- There are many ways to have kde-builder find the right configuration. If you
  have only a single configuration you want then a ~/.kdesrc-buildrc might be
  the right call. If you want to support multiple configurations, then you can
  create multiple directories and have a file "kdesrc-buildrc" in each
  directory, which kde-builder will find if you run the script from that
  directory.

- Don't forget to have kde-builder update itself from git!

- You can use the 'branch' and 'tag' options to kde-builder to manually choose
  the proper git branch or tag to build. With KDE modules you should not
  normally need this. If even these options are not specific enough, then
  consider the 'revision' option, or manage the source code manually and use
  `--no-src` for that module.

- You can refer to option values that have been previously set in your
  kde-builder configuration file, by using the syntax ${option-name}. There's
  no need for the option to be recognized by kde-builder, so you can set
  user-specific variables this way.

- Low on disk space? Use the `remove-after-install` option to clean out
  unneeded directories after your build, just don't be surprised when compile
  times go up.

- Need help setting up environment variables to run your shiny new desktop?
  kde-builder offers a sample ~/.xsession setup (which is supported by many
  login managers), which can be used by enabling the `install-session-driver`
  option.

- For KDE-based modules, kde-builder can install a module and all of its
  dependencies, by using the `--include-dependencies` command line option.
  You can also use `--no-include-dependencies` if you just want to build
  a single module this time.

- Use `--resume-from` (or `--resume-after`) to have kde-builder start the
  build from a later module than normal, and `--stop-before` (or
  `--stop-after`) to have kde-builder stop the build at an earlier module than
  normal.

- Use the `ignore-modules` option with your module sets if you want to build
  every module in the set *except* for a few specific ones.

- Annoyed by the default directory layout? Consider changing the `directory-layout`
  configuration file option.

- kde-builder supports building from behind a proxy, for all you corporate
  types trying to get the latest-and-greatest desktop. Just make sure your
  compilation toolchain is up to the challenge....

- You can use the `custom-build-command` option to setup a custom build tool
  (assumed to be make-compatible). For instance, cmake supports the `ninja`
  tool, and kde-builder can use `ninja` as well via this option.

- You can also wrap kde-builder itself in a script if you want to do things
like unusual pre-build setup, post-install cleanup, etc. This also goes well
with the [`--query`][query] option.

### Troubleshooting

- Is `build-when-unchanged` disabled? Did you try building from a clean build
  directory? If your answer to either is "No" then try using `--refresh-build`
  with your next kde-builder run to force a clean build directory to be used.

- If you've been running a kde-builder-based install for a long time then it
  may be time to clean out the installation directory as well, especially if
  you don't use the [use-clean-install][] option to run `make uninstall` as
  part of the install process. There's no kde-builder option to blow up your
  installation prefix, but it's not hard to do yourself...

[use-clean-install]: https://docs.kde.org/trunk5/en/kdesrc-build/kdesrc-build/conf-options-table.html#conf-use-clean-install
[query]: https://docs.kde.org/trunk5/en/kdesrc-build/kdesrc-build/supported-cmdline-params.html#cmdline-query
