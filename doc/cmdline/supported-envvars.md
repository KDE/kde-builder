(supported-envvars)=
# Supported Environment Variables

`KDE_BUILDER_USE_TTY`  
If set, this variable forces `kde-builder` not to close its input while
executing system processes. Normally `kde-builder` closes `stdin` since
the `stdout` and `stderr` for its child processes are redirected and
therefore the user would never see an input prompt anyway.
