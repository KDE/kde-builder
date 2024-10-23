(supported-envvars)=
# Supported Environment Variables

`HOME`  
Used for tilde-expansion of file names, and is the default base for the
source, build, and installation directories.

`PATH`  
This environment variable controls the default search path for
executables. You can use the `binpath` configuration file option to add
to this variable (e.g. for running from `cron`(8)).

`LC_`\*  
Environment variables starting with LC\_ control the locale used by
`kde-builder`. Although `kde-builder` is still not localizable at this
point, many of the commands it uses are. `kde-builder` normally sets
`LC_ALL`=C for commands that it must examine the output of, but you can
manually do this as well. If setting `LC_ALL`=C fixes a `kde-builder`
problem please submit a bug report.

`SSH_AGENT_PID`  
This environment variable is checked to see if `ssh-agent`(1) is
running, but only if `kde-builder` determines that you are checking out
a project that requires an SSH login (but you should know this as no
project requires this by default).

`KDE_BUILDER_USE_TTY`  
If set, this variable forces `kde-builder` not to close its input while
executing system processes. Normally `kde-builder` closes `stdin` since
the `stdout` and `stderr` for its child processes are redirected and
therefore the user would never see an input prompt anyway.

others  
Many programs are used by `kde-builder` in the course of its execution,
including `git`(1), `make`(1), and `cmake`(1). Each of these programs
may have their own response to environment variables being set.
`kde-builder` will pass environment variables that are set when it is
run onto these processes. You can ensure certain environment variables
(e.g. `CC` or `CXX`) are set by using the [set-env](#conf-set-env) configuration file
option.
