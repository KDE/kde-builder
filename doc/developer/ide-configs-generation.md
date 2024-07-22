# Generation of IDE project configuration

Here are the notes about how some IDE configuration works, and why we did generation one way or another.

## CLion

### Toolchain

[CLion Toolchain documentation](https://www.jetbrains.com/help/clion/how-to-create-toolchain-in-clion.html#cmake-toolchain)

Specifies the C and C++ compilers, cmake path, build tool path (ninja, make) and debugger path (gdb, lldb).  
It is not project-specific, and so we do not want to configure a toolchain for each project - otherwise there will be a lot of them visible in selection list.  

It can source a shell script to define environment. The environment is applied to _everything_: configure, build, and run/debug.

Cmake profiles (see below) name specific toolchain they use, so we ask user to create a toolchain named "KDE Builder Toolchain", and we use that name in cmake 
profile that we generate.

### CMake Profiles

[CLion CMake profiles documentation](https://www.jetbrains.com/help/clion/cmake-profile.html)

Defines toolchain name to use, cmake configure options, build directory, and environment variables.

The environment variables you specify in the profile affect CMake generation and build, but not the binary launch.

If project has CMakePresets.json, in CMake Profiles there will be read-only profiles shown based on presets. Thankfully, they are disabled by default, so we 
should not care of them.

Currently, it is not possible to source the script in cmake profiles. See 
[this](https://youtrack.jetbrains.com/issue/CPP-25319/Modify-environment-with-script-before-running-CMake) issue.

So we currently cannot just point to kde-builder.env. We inject each variable manually.

### Run/Debug configuration

[CLion Run/debug configurations documentation](https://www.jetbrains.com/help/clion/run-debug-configuration.html)

We replicate the behavior of kde-builder when using --run. KDE Builder launches from install directory, and sources prefix.sh from build directory and file 
from source-when-start-program option.

Currently, it is not possible to source several scripts, see
[this](https://youtrack.jetbrains.com/issue/CPP-39528/Add-ability-to-use-several-env-files-in-CLion-Run-Debug-configurations) issue.
And so, because the content of prefix.sh is predictable, we inject variables from there manually, and we point to the source-when-start-program file 
for sourcing.

The syntax of variables in JetBrains IDEs is limited, and currently does not support expansion like in shell, see
[this](https://youtrack.jetbrains.com/issue/IJPL-158293/Add-ability-to-use-shell-expansion-with-a-default-value-in-environment-variables-for-run-configurations) issue.
So I currently just use all possible paths for such variables. I.e. for `${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}` I use 
`$XDG_DATA_DIRS$:/usr/local/share/:/usr/share/`.

In the target, we select "All targets", because kde-builder does not specify a target when building, and this implicitly means all targets. 
