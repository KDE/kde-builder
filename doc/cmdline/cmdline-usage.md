(cmdline-usage)=
# Command Line Usage

KDE Builder is designed to be run as follows:

kde-builder \[--options\] \[modules to build...\]

If no modules to build are specified on the command line, then
kde-builder will build all modules defined in its configuration file,
in the order listed in that file (although this can be modified by
various configuration file options).

(cmdline-usage-modules)=
## Specifying modules to build

In general, specifying modules to build is as simple as passing their
module name as you defined it in the configuration file. You can also
pass modules that are part of a module set, either as named on
[use-modules](#conf-use-modules), or the name of the entire module set
itself, if you have given it a name.

In the specific case of module sets based against the [KDE project
database](#kde-projects-module-sets), kde-builder will expand module
name components to determine the exact module you want. For example,
repo-metadata's KDE project entry locates the project in
`extragear/utils/kcalc`. You could specify any of the following
to build kcalc:

```bash
kde-builder +kde/kdeutils/kcalc
kde-builder +kdeutils/kcalc
kde-builder +kcalc
```

```{note}
The commands in the example above preceded the module-name with a
`+`. This forces the module name to be interpreted as a module from the
KDE project database, even if that module hasn't been defined in your
configuration file.
```

Be careful about specifying very generic projects (e.g.
`extragear/utils` by itself), as this can lead to a large amount of
modules being built. You should use the `--pretend` option before
building a new module set to ensure it is only building the modules you
want.

(cmdline-commonly-used-options)=
## Commonly used command line options

`--pretend` (or `-p`)  
This option causes KDE Builder to indicate what actions it would take,
without actually executing them. This can be useful to make
sure that the modules you think you are building will actually get
built.

`--no-src`  
This option skips the source update process. You might use it if you
have very recently updated the source code (perhaps you did it manually
or recently ran kde-builder) but still want to rebuild some modules.

`--no-include-dependencies` (or `-D`)  
Only process the selected modules, skipping their dependencies. Useful
when you have changed only selected modules, and you are sure you do not
need to rebuild the others.

`--refresh-build` (or `-r`)  
This option forces kde-builder to build the given modules from an
absolutely fresh start point. Any existing build directory for that
module is removed and it is rebuilt. This option is useful if you have
errors building a module, and sometimes is required when Qt or KDE
libraries change.

`--resume-from` module  
Skips modules until just before the given module, then operates as
normal. Useful when the previous build failed on specific module, you
fixed it, and then you want to continue the building with the rest of
initial set of modules.

`--run` executable_name  
Launch the built application.

The full list of command line options is given in the section called
[](#supported-cmdline-params).

## Exit status

**0**  
Success

**1**  
Normally this means some part of the update, build or install process
failed, but is also used for any abnormal program end not otherwise
covered below.

**5**  
A signal was received that killed `kde-builder`, but it attempted to
perform normal closedown.

**8**  
Unknown option was passed on the command line.

**99**  
An exception was raised that forced `kde-builder` to abort early.

## Signals

kde-builder supports `SIGHUP`, which if received will cause
kde-builder to exit after the current modules for the build thread (and
update thread, if still active) have completed.
