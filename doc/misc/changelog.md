# Changelog

2024-10-27
: Added `meson-options` option.

2024-10-18
: Switched to yaml format for configuration file.

2024-09-23
: Removed option `no-tests`.

2024-07-28
: Added option `generate-qtcreator-project-config` for the CLion IDE project generation.

2024-07-14
: Added option `generate-clion-project-config` for the CLion IDE project generation.

2024-05-29
: Launching the built binaries which names are different from their module name no longer require specifying --exec in --run.

2024-05-24
: Added option `install-login-session`. Removed options `install-session-driver` and `install-environment-driver`.

2024-05-22
: Added options `refresh-build-first` and `resume-refresh-build-first`.

2024-05-01
: The list of missing optional packages is now printed from the cmake configure command.

2024-04-19
: Renamed config option `git-desired-protocol` to `git-push-protocol`.

2024-04-14
: Separated project-wide "Debug()" logger into separate loggers.

2024-03-27
: Added `source-when-start-program` option.

2024-02-28
: Released kde-builder. All the implementation and features are synced in both kdesrc-build and kde-builder.
This point is marked with the commit "MEGA RELEASE" in git history of both projects.
