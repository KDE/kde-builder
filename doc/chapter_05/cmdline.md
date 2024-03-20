(cmdline-usage)=
# Command Line Usage

kde-builder is designed to be run as follows:

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
kdesrc-build's KDE project entry locates the project in
`extragear/utils/kdesrc-build`. You could specify any of the following
to build kdesrc-build:

```
% kdesrc-build +extragear/utils/kdesrc-build
% kdesrc-build +utils/kdesrc-build
% kdesrc-build +kdesrc-build
```

```{note}
The commands in the previous example preceded the module-name with a
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
This option causes kde-builder to indicate what actions it would take,
without actually really implementing them. This can be useful to make
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
fixed it, and then you want to continue the with building the rest of
initial set of modules.

`--run` module  
Launch the built application.

The full list of command line options is given in the section called
[](#supported-cmdline-params).
