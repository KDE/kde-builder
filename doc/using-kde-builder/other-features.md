(other-features)=
# Other kde-builder features

(changing-verbosity)=
## Changing the amount of output from kde-builder

kde-builder has several loggers, which you can configure to control the amount of output they generate.

Loggers' default severity levels and formatters are defined in the `data/kde-builder-logging.yaml`.

To override specific loggers values, copy `data/kde-builder-logging.yaml` config to the `~/.config/kde-builder-logging.yaml`
or to the current working directory. Alternatively, instead of copying file, you can just create a yaml file with only overridden values
in the mentioned locations.

For example, to change `application` logger to `DEBUG` level, the file will look like this:
```yaml
loggers:
  application:
    level: DEBUG
```

The order of loggers configs are read is the following:  
1. kde-builder applies the default configuration from `data/kde-builder-logging.yaml` (located in the kde-builder root directory).  
2. If the `./kde-builder-logging.yaml` file is found (from the current working directory), it overrides the default configuration.  
3. If the file was not found in previous step, then if the `~/.config/kde-builder-logging.yaml` file is found, it overrides the default configuration.

```{note}
To temporary set all loggers to `DEBUG` level, use [`--debug`](#cmdline-debug) command line option.
```

This is a table of loggers severity levels. The lower level you choose, the more info will be printed.

| Python logger levels |
|:--------------------:|
|    CRITICAL (50)     |
|      ERROR (40)      |
|     WARNING (30)     |
|      INFO (20)       |
|      DEBUG (10)      |
|      NOTSET (0)      |

(kde-builder-color)=
## Color output

When being run from Konsole or a different terminal, kde-builder will
normally display with colorized text.

You can disable this by using the `--no-color` on the command line, or
by setting the [colorful-output](#conf-colorful-output) option in the
[configuration file](../getting-started/configure-data) to `false`.

Disabling color output in the configuration file:

```yaml
global:
  colorful-output: false
```

(deleting-build-dir)=
## Removing unneeded directories after a build

Are you short on disk space but still want to run a bleeding-edge KDE
checkout? kde-builder can help reduce your disk usage when building KDE
from git.

```{note}
Be aware that building KDE does take a lot of space. There are several
major space-using pieces when using kde-builder:
```

1.  The actual source checkout can take up a fair amount of space. The
    default projects take up about 1.6 gigabytes of on-disk space. You
    can reduce this amount by making sure that you are only building as
    many projects as you actually want. kde-builder will not delete
    source code from disk even if you delete the entry from the
    [configuration file](../getting-started/configure-data), so make sure that you go and
    delete unused source checkouts from the source directory. Note that
    the source files are downloaded from the Internet, you *should not*
    delete them if you are actually using them, at least until you are
    done using kde-builder.

    Also, if you already have a Qt installed by your distribution (and
    the odds are good that you do), you probably do not need to install
    the qt6-set group. That will shave about 200 megabytes off of the
    on-disk source size.

```{note}
Todo: Outdated info. Mentions the size for the kdebase project. And check the statements about "fake build dir".
```

2.  kde-builder will create a separate build directory to build the
    source code in. Sometimes kde-builder will have to copy a source
    directory to create a fake build directory. When this happens,
    space-saving symlinks are used, so this should not be a hassle on
    disk space. The build directory will typically be much larger than
    the source directory for a project. For example, the build directory
    for kdebase is about 1050 megabytes, whereas kdebase's source is
    only around 550 megabytes.

    Luckily, the build directory is not required after a project has
    successfully been built and installed. kde-builder can
    automatically remove the build directory after installing a project,
    see the examples below for more information. Note that taking this
    step will make it impossible for kde-builder to perform the
    time-saving incremental builds.

3.  Finally, there is disk space required for the actual installation of
    KDE, which does not run from the build directory. This typically
    takes less space than the build directory. It is harder to get exact
    figures however.

How do you reduce the space requirements of KDE? One way is to use the
proper compiler flags, to optimize for space reduction instead of for
speed. Another way, which can have a large effect, is to remove
debugging information from your KDE build.

```{warning}
You should be very sure you know what you are doing before deciding to
remove debugging information. Running bleeding-edge software means you
are running software which is potentially much more likely to crash than
a stable release. If you are running software without debugging
information, it can be very hard to create a good bug report to get your
bug resolved, and you will likely have to re-enable debugging
information for the affected application and rebuild to help a developer
fix the crash. So, remove debugging information at your own risk!
```

Removing the build directory after installation of a project. The source
directory is still kept, and debugging is enabled:

```yaml
global:
  configure-flags: --enable-debug
  remove-after-install: builddir # Remove build directory after install
```

Removing the build directory after installation, without debugging
information, with size optimization.

```yaml
global:
  cxxflags: -Os # Optimize for size
  configure-flags: --disable-debug
  remove-after-install: builddir # Remove build directory after install
```

## Updating kde-builder

Once in a while you will want to update kde-builder to get its latest changes.
To do so, just run:

```bash
kde-builder --self-update
```
