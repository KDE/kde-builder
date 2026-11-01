(supported-envvars)=
# Supported Environment Variables

## Keep standard input open

`KDE_BUILDER_USE_TTY`

If set, this variable forces `kde-builder` not to close its input while
executing system processes. Normally `kde-builder` closes `stdin` since
the `stdout` and `stderr` for its child processes are redirected and
therefore the user would never see an input prompt anyway.

## Enable or disable colorized output

`NO_COLOR`, `FORCE_COLOR`

These environment variables can be used to control whether `kde-builder` should
emit colorized output.

If `FORCE_COLOR` is present and not a non-empty string, output is colorized.

If `NO_COLOR` is present and not a non-empty string, output is not colorized.

`NO_COLOR` takes precedence over `FORCE_COLOR`.

See also:

- [https://no-color.org/](https://no-color.org/)
- [https://force-color.org/](https://force-color.org/)
