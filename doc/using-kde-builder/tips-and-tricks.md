# Tips and Tricks

- Use `kde-builder --rebuild-failures` (potentially with `--no-src`) to
  rebuild projects that failed to build during the last kde-builder run. This
  is particularly useful when a silly local error breaks an important project
  and several dozen dependent projects.

- Use the `--no-stop-on-failure` command-line option (or
  the corresponding configuration file option) to make kde-builder not abort
  after the first project fails to build.

- Either way if you're running kde-builder frequently as part of a
  debug/build/debug cycle, don't forget to throw `--no-src` on the command line
  as appropriate. If the build failed halfway through it is likely that all
  source updates completed, even for projects kde-builder didn't try to build.

- It is possible to build many project types that are not official KDE projects.
  This may be needed for upstream dependencies or simply because you only need
  a project to support your KDE-based workspace or application.

- There are many ways to have kde-builder find the right configuration. If you
  have only a single configuration you want then a ~/.config/kde-builder.yaml might be
  the right call. If you want to support multiple configurations, then you can
  create multiple directories and have a file "kde-builder.yaml" in each
  directory, which kde-builder will find if you run the KDE Builder from that
  directory.

- Don't forget to have kde-builder update itself from git!

- You can use the "branch" and "tag" options to kde-builder to manually choose
  the proper git branch or tag to build. With KDE projects you should not
  normally need this. If even these options are not specific enough, then
  consider the "revision" option, or manage the source code manually and use
  `--no-src` for that project.

- You can refer to option values that have been previously set in your
  kde-builder configuration file, by using the syntax ${option-name}. If this is
  not a standard option, you can name it prefixed with underscore, so kde-builder 
  recognizes it as a user-specific variable.

- Low on disk space? Use the `remove-after-install` option to clean out
  unneeded directories after your build, just don't be surprised when compile
  times go up.

- For KDE-based projects, kde-builder can install a project and all of its
  dependencies, by using the `--include-dependencies` command line option.
  You can also use `--no-include-dependencies` if you just want to build
  a single project this time.

- Use `--resume-from` (or `--resume-after`) to have kde-builder start the
  build from a later project than normal, and `--stop-before` (or
  `--stop-after`) to have kde-builder stop the build at an earlier project than
  normal.

- Use the `ignore-projects` option with your groups if you want to build
  every project in the set *except* for a few specific ones.

- Annoyed by the default directory layout? Consider changing the `directory-layout`
  configuration file option.

- You can use the `custom-build-command` option to setup a custom build tool
  (assumed to be make-compatible). For instance, cmake supports the `ninja`
  tool, and kde-builder can use `ninja` as well via this option.

- You can also wrap kde-builder itself in a script if you want to do things
like unusual pre-build setup, post-install cleanup, etc. This also goes well
with the [`--query`](#cmdline-query) option.

## Troubleshooting

- Is `build-when-unchanged` disabled? Did you try building from a clean build
  directory? If your answer to either is "No" then try using `--refresh-build`
  with your next kde-builder run to force a clean build directory to be used.

- If you've been running a kde-builder-based install for a long time then it
  may be time to clean out the installation directory as well, especially if
  you don't use the [use-clean-install](#conf-use-clean-install) option to run `make uninstall` as
  part of the install process. There's no kde-builder option to blow up your
  installation prefix, but it's not hard to do yourself...
