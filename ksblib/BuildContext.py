# SPDX-FileCopyrightText: 2012, 2013, 2014, 2015, 2017, 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import traceback
from io import StringIO
from pathlib import Path
import json
import re
import fileinput
import datetime
import errno
# from overrides import override

from .Debug import Debug, kbLogger
from .PhaseList import PhaseList
from .Module.Module import Module
from .Module.BranchGroupResolver import Module_BranchGroupResolver
# from . import Updater::KDEProjectMetadata
from .Version import Version
from .StatusView import StatusView
from .KDEProjectsReader import KDEProjectsReader

from .OptionsBase import OptionsBase
from .ModuleSet.KDEProjects import ModuleSet_KDEProjects
from .BuildException import BuildException
from .Util.Util import Util

logger_buildcontext = kbLogger.getLogger("build-context")


# We derive from Module so that BuildContext acts like the 'global'
# Module, with some extra functionality.
# TODO: Derive from OptionsBase directly and remove getOption override
class BuildContext(Module):
    """
    This contains the information needed about the build context, e.g. list of
    modules, what phases each module is in, the various options, etc.

    It also records information on which modules encountered errors (and what
    error), where to put log files, persistent options that should be available on
    the next run, and basically anything else that falls into the category of state
    management.

    The 'global' module

    One interesting thing about this class is that, as a state-managing class, this
    class implements the role of :class:`Module` for the pseudo-module called
    'global' throughout the source code (and whose options are defined in the
    'global' section in the rc-file). It is also a parent to every :class:`Module` in
    terms of the option hierarchy, serving as a fallback source for :class:`Module`'s
    `getOption()` calls for most (though not all!) options.

    Examples:
    ::

         ctx = BuildContext.BuildContext()

         ctx.setRcFile('/path/to/kdesrc-buildrc')
         fh = ctx.loadRcFile()

         ...

         for modName in selectors:
            ctx.addModule(Module.Module(ctx, modName))

         ...
         moduleList = ctx.moduleList()
    """

    # According to XDG spec, if XDG_STATE_HOME is not set, then we should
    # default to ~/.local/state
    xdgStateHome = os.getenv("XDG_STATE_HOME", os.getenv("HOME") + "/.local/state")
    xdgStateHomeShort = xdgStateHome.replace(os.getenv("HOME"), "~")  # Replace $HOME with ~

    # According to XDG spec, if XDG_CONFIG_HOME is not set, then we should
    # default to ~/.config
    xdgConfigHome = os.getenv("XDG_CONFIG_HOME", os.getenv("HOME") + "/.config")
    xdgConfigHomeShort = xdgConfigHome.replace(os.getenv("HOME"), "~")  # Replace $HOME with ~

    rcfiles = ["./kdesrc-buildrc",
               f"{xdgConfigHome}/kdesrc-buildrc",
               f"""{os.getenv("HOME")}/.kdesrc-buildrc"""]
    LOCKFILE_NAME = ".kdesrc-lock"
    PERSISTENT_FILE_NAME = "kdesrc-build-data"
    SCRIPT_VERSION = Version.scriptVersion()

    def __init__(self):
        Module.__init__(self, None, "global")

        # There doesn't seem to be a great way to get this from CMake easily but we can
        # reason that if there's a /usr/lib64 (and it's not just a compat symlink),
        # there will likely end up being a ${install-dir}/lib64 once kde-builder gets
        # done installing it
        self.libname = "lib"
        if os.path.isdir("/usr/lib64") and not os.path.islink("/usr/lib64"):
            self.libname = "lib64"
        if os.path.isdir("/usr/lib/x86_64-linux-gnu"):
            self.libname = "lib/x86_64-linux-gnu"

        # These options are used for internal state, they are _not_ exposed as cmdline options
        self.GlobalOptions_private = {
            "filter-out-phases": "",
            "git-push-protocol": "git",
            "git-repository-base": {"qt6-copy": "https://invent.kde.org/qt/qt/", "_": "fake/"},
            "manual-build": "",
            "manual-update": "",
            "module-definitions-dir": os.environ.get("XDG_STATE_HOME", os.environ["HOME"] + "/.local/state") + "/sysadmin-repo-metadata/module-definitions",
            "repository": "",  # module's git repo
            "set-env": {},  # Hash of environment vars to set
            "ssh-identity-file": "",  # If set, is passed to ssh-add.
            "use-modules": ""
        }

        # These options are exposed as cmdline options, but _not from here_.
        # Their more complex specifier is made in ksb::Cmdline _supportedOptions().
        self.GlobalOptions_with_extra_specifier = {
            "build-when-unchanged": True,
            "colorful-output": True,
            "ignore-modules": "",
            "niceness": "10",  # todo convert to int?
            "pretend": "",
            "refresh-build": "",
        }

        # These options are exposed as cmdline options without parameters, and having the negatable form with "--no-".
        self.GlobalOptions_with_negatable_form = {
            "async": True,
            "compile-commands-export": True,  # 2021-02-06 allow to generate compile_commands.json via cmake, for clangd tooling
            "compile-commands-linking": False,  # 2021-02-06 link generated compile_commands.json back to the source directory
            "delete-my-patches": False,  # Should only be set from cmdline
            "delete-my-settings": False,  # Should only be set from cmdline
            "disable-agent-check": False,  # If true we don't check on ssh-agent
            "generate-vscode-project-config": False,
            "include-dependencies": True,
            "install-after-build": True,
            "install-environment-driver": True,  # Setup ~/.config/kde-env-*.sh for login scripts
            "install-session-driver": False,  # Above, + ~/.xsession
            "purge-old-logs": True,
            "run-tests": False,  # 1 = make test, upload = make Experimental  # todo why boolean option may have "upload" value?
            "stop-on-failure": True,
            "use-clean-install": False,
            "use-idle-io-priority": False,
            "use-inactive-modules": False,
        }

        # These options are exposed as cmdline options that require some parameter
        self.GlobalOptions_with_parameter = {
            "binpath": "",
            "branch": "",
            "branch-group": "",  # Overrides branch, uses JSON data.
            "build-dir": os.getenv("HOME") + "/kde/build",
            "cmake-generator": "",
            "cmake-options": "",
            "cmake-toolchain": "",
            "configure-flags": "",
            "custom-build-command": "",
            "cxxflags": "-pipe",
            "directory-layout": "flat",
            "dest-dir": '${MODULE}',  # single quotes used on purpose!
            "do-not-compile": "",
            "http-proxy": "",  # Proxy server to use for HTTP.
            "install-dir": os.getenv("HOME") + "/kde/usr",
            "libname": self.libname,
            "libpath": "",
            "log-dir": os.getenv("HOME") + "/kde/log",
            "make-install-prefix": "",  # Some people need sudo
            "make-options": "",
            "ninja-options": "",
            "num-cores": "",  # Used for build constraints
            "num-cores-low-mem": "2",  # Needs to be a string, not int
            "override-build-system": "",
            "persistent-data-file": "",
            "qmake-options": "",
            "qt-install-dir": "",
            "remove-after-install": "none",  # { none, builddir, all }
            "revision": "",
            "source-dir": os.getenv("HOME") + "/kde/src",
            "source-when-start-program": "/dev/null",
            "tag": "",
        }

        # These options are exposed as cmdline options without parameters
        self.GlobalOptions_without_parameter = {
            "build-system-only": "",
            "reconfigure": "",
            "metadata-only": "",
        }

        # newOpts
        self.modules = []
        self.context = self  # Fix link to buildContext (i.e. self)
        self.build_options = {
            "global": {
                **self.GlobalOptions_private,
                **self.GlobalOptions_with_extra_specifier,
                **self.GlobalOptions_without_parameter,
                **self.GlobalOptions_with_negatable_form,
                **self.GlobalOptions_with_parameter,
            },
            # Module options are stored under here as well, keyed by module->name()
        }
        # This one replaces ksb::Module::{phases}
        self.phases = PhaseList()

        self.errors = {
            # A map from module *names* (as in modules[] above) to the
            # phase name at which they failed.
        }
        self.logPaths = {
            # Holds a hash table of log path bases as expanded by
            # getSubdirPath (e.g. [source-dir]/log) to the actual log dir
            # *this run*, with the date and unique id added. You must still
            # add the module name to use.
        }
        self.rcFiles = BuildContext.rcfiles
        self.rcFile = None
        self.env = {}
        self.persistent_options = {}  # These are kept across multiple script runs
        self.ignore_list = []  # List of KDE project paths to ignore completely
        self.kde_projects_metadata = None  # Enumeration of kde-projects
        self.logical_module_resolver = None  # For branch-group option
        self.status_view = StatusView()
        self.projects_db = None  # See getProjectDataReader

        self.options = self.build_options["global"]

        Util.assert_isa(self, Module)
        Util.assert_isa(self, BuildContext)

    # @override
    def phases(self, phases=None):
        """
        Gets the :class:`PhaseList` for this context, and optionally sets it first to
        the :class:`PhaseList` passed in.
        """
        if phases:
            if not isinstance(phases, PhaseList):
                raise AssertionError("Invalid type, expected PhaseList")
            self.phases = phases
        return self.phases

    def addModule(self, module: Module) -> None:
        if not module:
            traceback.print_exc()
            raise Exception("No module to push")

        path = None
        if module in self.modules:
            logger_buildcontext.debug("Skipping duplicate module " + module.name)
        elif ((path := module.fullProjectPath()) and
              any(re.search(rf"(^|/){item}($|/)", path) for item in self.ignore_list)):
            # See if the name matches any given in the ignore list.

            logger_buildcontext.debug(f"Skipping ignored module {module}")
        else:
            logger_buildcontext.debug(f"Adding {module} to module list")
            self.modules.append(module)

    def moduleList(self) -> list[Module]:
        """
        Returns a list of the modules to build
        """
        return self.modules

    def addToIgnoreList(self, moduleslist: list) -> None:
        """
        Adds a list of modules to ignore processing on completely.
        Parameters should simply be a list of KDE project paths to ignore,
        e.g. 'extragear/utils/kdesrc-build'. Partial paths are acceptable, matches
        are determined by comparing the path provided to the suffix of the full path
        of modules being compared.  See :meth:`KDEProjectsReader._projectPathMatchesWildcardSearch`.

        Existing items on the ignore list are not removed.
        """
        self.ignore_list.extend(moduleslist)

    def setupOperatingEnvironment(self) -> None:
        # Set the process priority
        os.nice(int(self.getOption("niceness")))
        # Set the IO priority if available.
        if self.getOption("use-idle-io-priority"):
            # -p $$ is our PID, -c3 is idle priority
            # 0 return value means success
            if Util.safe_system(["ionice", "-c3", "-p", os.getpid()]) != 0:
                logger_buildcontext.warning(" b[y[*] Unable to lower I/O priority, continuing...")

        # Get ready for logged output.
        Debug().setLogFile(self.getLogDirFor(self) + "/build-log")

        # # Propagate HTTP proxy through environment unless overridden.
        proxy = self.getOption("http-proxy")
        if proxy and "http_proxy" not in os.environ:
            self.queueEnvironmentVariable("http_proxy", proxy)

    def resetEnvironment(self) -> None:
        """
        Clears the list of environment variables to set for log_command runs.
        """
        Util.assert_isa(self, BuildContext)
        self.env = {}

    def queueEnvironmentVariable(self, key: str, value: str) -> None:
        """
        Adds an environment variable and value to the list of environment
        variables to apply for the next subprocess execution.

        Note that these changes are /not/ reflected in the current environment,
        so if you are doing something that requires that kind of update you
        should do that yourself (but remember to have some way to restore the old
        value if necessary).

        In order to keep compatibility with the old 'setenv' sub, no action is
        taken if the value is not equivalent to boolean true.
        """
        Util.assert_isa(self, BuildContext)

        if not value:
            return

        logger_buildcontext.debug(f"\tQueueing g[{key}] to be set to y[{value}]")
        self.env[key] = value

    def commitEnvironmentChanges(self) -> None:
        """
        Applies all changes queued by queueEnvironmentVariable to the actual
        environment irretrievably. Use this before exec()'ing another child, for
        instance.
        """
        Util.assert_isa(self, BuildContext)

        for key, value in self.env.items():
            os.environ[key] = value
            logger_buildcontext.debug(f"\tSetting environment variable g[{key}] to g[b[{value}]")

    def prependEnvironmentValue(self, envName: str, items: str) -> None:  # pl2py: the items was a list in perl, but it was never used as list. So will type it as str.
        """
        Adds the given library paths to the path already given in an environment
        variable. In addition, detected "system paths" are stripped to ensure
        that we don't inadvertently re-add a system path to be promoted over the
        custom code we're compiling (for instance, when a system Qt is used and
        installed to /usr).

        If the environment variable to be modified has already been queued using
        queueEnvironmentVariable, then that (queued) value will be modified and
        will take effect with the next forked subprocess.

        Otherwise, the current environment variable value will be used, and then
        queued. Either way the current environment will be unmodified afterward.

        Parameters:
            envName: The name of the environment variable to modify
            items: Prepended to the current environment path, in
                the order given. (i.e. param1, param2, param3 -> param1:param2:param3:existing)
        """

        if envName in self.env:
            curPaths = self.env[envName].split(":")
        elif envName in os.environ:
            curPaths = os.environ.get(envName, "").split(":")
        else:
            curPaths = []

        # pl2py: this is kde-builder specific code (not from kdesrc-build).
        # Some modules use python packages in their build process. For example, breeze-gtk uses python-cairo.
        # We want the build process to use system installed package rather than installed in virtual environment.
        # We remove the current virtual environment path from PATH, because Cmake FindPython3 module always considers PATH,
        # see https://cmake.org/cmake/help/latest/module/FindPython3.html
        # But note that user still needs to provide these cmake options: -DPython3_FIND_VIRTUALENV=STANDARD -DPython3_FIND_UNVERSIONED_NAMES=FIRST
        if sys.prefix != sys.base_prefix and envName == "PATH":
            if f"{sys.prefix}/bin" in curPaths:
                logger_buildcontext.debug(f"\tRemoving python virtual environment path y[{sys.prefix}/bin] from y[PATH], to allow build process to find system python packages outside virtual environment.")
                curPaths.remove(f"{sys.prefix}/bin")
            else:
                logger_buildcontext.debug(f"\tVirtual environment path y[{sys.prefix}/bin] was already removed from y[PATH].")

        # Filter out entries to add that are already in the environment from
        # the system.
        for path in [item for item in [items] if item in curPaths]:
            logger_buildcontext.debug(f"\tNot prepending y[{path}] to y[{envName}] as it appears " + f"to already be defined in y[{envName}].")

        items = [item for item in [items] if item not in curPaths]

        envValue = ":".join(items + curPaths)

        envValue = re.sub(r"^:*", "", envValue)
        envValue = re.sub(r":*$", "", envValue)  # Remove leading/trailing colons
        envValue = re.sub(r":+", ":", envValue)  # Remove duplicate colons

        self.queueEnvironmentVariable(envName, envValue)

    def takeLock(self) -> bool:
        """
        Tries to take the lock for our current base directory, which currently is
        what passes for preventing people from accidentally running kde-builder
        multiple times at once. The lock is based on the base directory instead
        of being global to allow for motivated and/or brave users to properly
        configure kde-builder to run simultaneously with different
        configurations.

        Returns:
             Boolean success flag.
        """
        Util.assert_isa(self, BuildContext)
        baseDir = self.baseConfigDirectory()
        lockfile = f"{baseDir}/{BuildContext.LOCKFILE_NAME}"

        LOCKFILE = None
        try:
            LOCKFILE = os.open(lockfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except OSError as e:
            errorCode = e.errno  # Save for later testing.
        else:
            errorCode = 0

        if errorCode == errno.EEXIST:
            # Path already exists, read the PID and see if it belongs to a
            # running process.
            try:
                pidFile = open(lockfile, "r")
            except OSError:
                # Lockfile is there but we can't open it?!?  Maybe a race
                # condition but I have to give up somewhere.
                logger_buildcontext.warning(f" WARNING: Can't open or create lockfile r[{lockfile}]")
                return True

            pid = pidFile.read()
            pidFile.close()

            if pid:
                # Recent kde-builder; we wrote a PID in there.
                pid = pid.removesuffix("\n")

                # See if something's running with this PID.
                # pl2py note: in pl kill returns if successfully sent signal; in py kill returns nothing and raises ProcessLookupError if no process found
                try:
                    os.kill(int(pid), 0)

                    # Something *is* running, likely kde-builder.  Don't use error,
                    # it'll scan for $!
                    print(Debug().colorize(" r[*y[*r[*] kde-builder appears to be running.  Do you want to:\n"))
                    print(Debug().colorize("  (b[Q])uit, (b[P])roceed anyways?: "))

                    choice = input() or ""
                    choice = choice.removesuffix("\n")

                    if choice.lower() != "p":
                        print(Debug().colorize(" y[*] kde-builder run canceled."))
                        return False

                    # We still can't grab the lockfile, let's just hope things
                    # work out.
                    logger_buildcontext.warning(" y[*] kde-builder run in progress by user request.")
                    return True
                except (OSError, ProcessLookupError):
                    pass
                    # If we get here, then the program isn't running (or at least not
                    # as the current user), so allow the flow of execution to fall
                    # through below and unlink the lockfile.

            # No pid found, optimistically assume the user isn't running
            # twice.
            logger_buildcontext.warning(" y[WARNING]: stale kde-builder lockfile found, deleting.")
            os.unlink(lockfile)

            try:
                LOCKFILE = os.open(lockfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except OSError:
                logger_buildcontext.error(f" r[*] Still unable to lock {lockfile}, proceeding anyways...")
                return True
            # Hope the sysopen worked... fall-through
        elif errorCode == errno.ENOTTY:
            # Stupid bugs... normally sysopen will return ENOTTY, not sure who's to blame between
            # glibc and Perl but I know that setting PERLIO=:stdio in the environment "fixes" things.
            pass
        elif errorCode != 0:  # Some other error occurred.
            logger_buildcontext.warning(f" r[*]: Error {errorCode} while creating lock file (is {baseDir} available?)")
            logger_buildcontext.warning(" r[*]: Continuing the script for now...")

            # Even if we fail it's generally better to allow the script to proceed
            # without being a jerk about things, especially as more non-CLI-skilled
            # users start using kde-builder to build KDE.
            return True

        os.write(LOCKFILE, str(os.getpid()).encode())
        os.close(LOCKFILE)
        return True

    def closeLock(self) -> None:
        """
        Releases the lock obtained by takeLock.
        """
        Util.assert_isa(self, BuildContext)
        baseDir = self.baseConfigDirectory()
        lockFile = f"{baseDir}/{BuildContext.LOCKFILE_NAME}"

        try:
            os.unlink(lockFile)
        except Exception as e:
            logger_buildcontext.warning(f" y[*] Failed to close lock: {e}")

    def getLogDirFor(self, module: Module) -> str:
        """
        This function accepts a Module parameter, and returns the log directory
        for it. You can also pass a BuildContext (including this one) to get the
        default log directory.

        As part of setting up what path to use for the log directory, the
        'latest' symlink will also be setup to point to the returned log
        directory.
        """

        baseLogPath = module.getSubdirPath("log-dir")
        if baseLogPath not in self.logPaths:
            # No log dir made for this base, do so now.
            log_id = "01"
            date = datetime.datetime.now().strftime("%F")  # ISO 8601 date
            while os.path.exists(f"{baseLogPath}/{date}-{log_id}"):
                log_id = str(int(log_id) + 1).zfill(2)
            self.logPaths[baseLogPath] = f"{baseLogPath}/{date}-{log_id}"

        logDir = self.logPaths[baseLogPath]
        Util.super_mkdir(logDir)

        # global logs go to basedir directly
        if not isinstance(module, BuildContext):
            logDir += f"/{module}"

        return logDir

    def getLogPathFor(self, module: Module, path: str) -> str:
        """
        Constructs the appropriate full path to a log file based on the given
        basename (including extensions). Use this instead of getLogDirFor when you
        actually intend to create a log, as this function will also adjust the
        'latest' symlink properly.
        """
        baseLogPath = module.getSubdirPath("log-dir")
        logDir = self.getLogDirFor(module)

        # We create this here to avoid needless empty module directories everywhere
        Util.super_mkdir(logDir)

        # Provide a directory to make it easy to see the last build for a module's
        # given phase (like cmake, build, install, etc.) without having to find the
        # log dir for the specific kde-builder run.
        Util.super_mkdir(f"{baseLogPath}/latest-by-phase/{module}")

        # Add a symlink to the latest run for this module. 'latest' itself is
        # a directory under the base log directory that holds symlinks mapping
        # each module name to the specific log directory most recently used.
        latestPath = f"{baseLogPath}/latest"

        # Handle stuff like playground/utils or KDE/kdelibs
        moduleName, modulePath = os.path.splitext(os.path.basename(module.name))
        if "/" in module.name:
            latestPath += f"/{modulePath}"

        Util.super_mkdir(latestPath)

        symlink = f"{latestPath}/{moduleName}"
        Util.remake_symlink(logDir, symlink)

        symlink2 = f"{baseLogPath}/latest-by-phase/{module}/{path}"
        Util.remake_symlink(f"{logDir}/{path}", symlink2)

        return f"{logDir}/{path}"

    def rcFile(self):
        """
        Returns rc file in use. Call loadRcFile first.
        """
        return self.rcFile

    def setRcFile(self, file: str) -> None:
        """
        Forces the rc file to be read from to be that given by the first parameter.
        """
        self.rcFiles = [file]
        self.rcFile = None

    @staticmethod
    def warnLegacyConfig(file: str) -> None:
        """
        Warns a user if the config file is stored in the old location.
        """
        if file.startswith(os.getenv("HOME")):
            file = re.sub(os.getenv("HOME"), "~", file)
        if file == "~/.kdesrc-buildrc":
            logger_buildcontext.warning(textwrap.dedent(f"""\
            The b[global configuration file] is stored in the old location. It will still be
            processed correctly, however, it's recommended to move it to the new location.
            Please move b[~/.kdesrc-buildrc] to b[{BuildContext.xdgConfigHomeShort}/kdesrc-buildrc]
            """))

    def loadRcFile(self) -> fileinput.FileInput:
        """
        Returns an open filehandle to the user's chosen rc file. Use setRcFile
        to choose a file to load before calling this function, otherwise
        loadRcFile will search the default search path. After this function is
        called, rcFile() can be used to determine which file was loaded.

        If unable to find or open the rc file an exception is raised. Empty rc
        files are supported, however.
        """
        rcFiles = self.rcFiles

        for file in rcFiles:
            if os.path.exists(file):
                # fh = open(file, "r")  # does not support current line numbers reading
                # fh = fileinput.input(files=file, mode="r")  # does not support multiple instances
                fh = fileinput.FileInput(files=file, mode="r")  # supports multiple instances, so use this.

                self.rcFile = os.path.abspath(file)
                BuildContext.warnLegacyConfig(file)
                return fh

        # No rc found, check if we can use default.
        if len(rcFiles) == 1:
            # This can only happen if the user uses --rc-file, so if we fail to
            # load the file, we need to fail to load at all.
            failedFile = rcFiles[0]

            logger_buildcontext.error(textwrap.dedent(f"""\
            Unable to open config file {failedFile}
            
            Script stopping here since you specified --rc-file on the command line to
            load {failedFile} manually.  If you wish to run the script with no configuration
            file, leave the --rc-file option out of the command line.
            
            If you want to force an empty rc file, use --rc-file /dev/null
            
            """))
            BuildException.croak_runtime(f"Missing {failedFile}")

        if self.getOption("metadata-only"):
            # If configuration file in default location was not found, and no --rc-file option was used, and metadata-only option was used.

            # In FirstRun user may decide to use --install-distro-packages before --generate-config.
            # --install-distro-packages requires the metadata to be downloaded to read the "disrto-dependencies" from it.
            # After downloading metadata, we normally should change 'last-metadata-update' persistent option value.
            # To store persistent option, we should know persistent-data-file value, and it is read from config.
            # At this moment we know that there is no config at default location, and user did not specified the --rc-file option.
            # And because we do not want to _require_ the config to be available yet, we just will provide dummy config.
            # This way the --metadata-only option could work in both cases: when user has config and when he has not.
            # When he has config (not current case), the persistent option "last-metadata-update" will be set as expected, and after the build process will be stored in persistent file.
            # When he has no config (the current case), we will let the _readConfigurationOptions function do its work on fake config, then we will return.
            dummyConfig = textwrap.dedent("""\
                global
                    persistent-data-file /not/existing/file  # should not exist in file system (so it is not tried to be read, otherwise we should provide a valid json)
                end global
    
                # To suppress warning about no modules in configuration.
                module fake
                end module
                """)

            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
            temp_file.write(dummyConfig)
            temp_file_path = temp_file.name
            temp_file.close()

            fh = fileinput.FileInput(files=temp_file_path, mode="r")
            self.rcFile = "/fake/dummy_config"
            return fh
        else:
            # If no configuration and no --rc-file option was used, warn the user and fail.

            logger_buildcontext.error(textwrap.dedent(f"""\
                b[No configuration file is present.]
                
                kde-builder requires a configuration file to select which KDE software modules
                to build, what options to build them with, the path to install to, etc.
                
                When run, kde-builder will use `kdesrc-buildrc' config file located in the
                current working directory. If no such file exists, kde-builder will use
                `{BuildContext.xdgConfigHomeShort}/kdesrc-buildrc' instead.
                
                You can generate config with b[--generate-config].
                """))
            BuildException.croak_runtime("No configuration available")

    def baseConfigDirectory(self) -> str:
        """
        Returns the base directory that holds the configuration file. This is
        typically used as the directory base for other necessary kde-builder
        execution files, such as the persistent data store and lock file.

        The RC file must have been found and loaded first, obviously.
        """
        Util.assert_isa(self, BuildContext)
        rcfile = self.rcFile
        if not rcfile:
            BuildException.croak_internal("Call to baseConfigDirectory before loadRcFile")
        return os.path.dirname(rcfile)

    def modulesInPhase(self, phase: str) -> list:
        modules_list = [module for module in self.moduleList() if module.phases.has(phase)]
        return modules_list

    def usesConcurrentPhases(self) -> bool:
        # If we have an 'update' phase and any other phase (build / test / install
        # / etc) we should use concurrency if it is available.
        has_update = False
        has_other = False

        for mod in self.moduleList():
            for phase in mod.phases.phases():
                if phase == "update":
                    has_update = True
                else:
                    has_other = True
            if has_update and has_other:
                return True
        return False

    def lookupModule(self, moduleName: str):
        """
        Searches for a module with a name that matches the provided parameter,
        and returns its :class:`Module` object. Returns None if no match was found.
        As a special-case, returns the BuildContext itself if the name passed is
        'global', since the BuildContext also is a (in the "is-a" OOP sense)
        :class:`Module`, specifically the 'global' one.
        """
        if moduleName == "global":
            return self

        options = [module for module in self.moduleList() if module.name == moduleName]
        if not options:
            return None

        if len(options) > 1:
            BuildException.croak_internal(f"Detected 2 or more {moduleName} ksb::Module objects")
        return options[0]

    def markModulePhaseFailed(self, phase: str, module: Module) -> None:
        Util.assert_isa(module, Module)
        self.errors[module.name] = phase

    def failedModulesInPhase(self, phase: str) -> list:
        """
        Returns a list of Modules that failed to complete the given phase.
        """
        failures = [module for module in self.moduleList() if self.errors.get(module.name, "") == phase]
        return failures

    def listFailedModules(self) -> list[Module]:
        """
        Returns a list of modules that had a failure of some sort, in the order the modules
        are listed in our current module list.
        """
        modules = self.moduleList()

        # grepping for failures instead of returning error list directly maintains ordering
        modules = [module for module in modules if module.name in self.errors]
        return modules

    # @override(check_signature=False)
    def getOption(self, key: str) -> str | dict | list | bool:
        """
        Our immediate parent class Module overrides this, but we actually
        want the OptionsBase version to be used instead, until we break the recursive
        use of Module's own getOption calls on our getOption.

        Returns:
             The same types that OptionsBase.getOption returns.
        """
        return OptionsBase.getOption(self, key)

    # @override
    def setOption(self, options: dict) -> None:

        # Special case handling.
        if "filter-out-phases" in options:
            for phase in options["filter-out-phases"].split(" "):
                self.phases.filterOutPhase(phase)
            del options["filter-out-phases"]

        # Our immediate parent class Module overrides this, but we actually
        # want the OptionsBase version to be used instead, because Module's version specifically checks for
        # some options prohibited for it (such as "ignore-modules") but we may want such for BuildContext.
        OptionsBase.setOption(self, options)

        # Automatically respond to various global option changes.
        for key, value in options.items():
            normalizedKey = key
            normalizedKey = normalizedKey.lstrip("#")  # Remove sticky key modifier.
            if normalizedKey == "colorful-output":
                Debug().setColorfulOutput(value)
            elif normalizedKey == "pretend":
                Debug().setPretending(value)

    # Persistent option handling

    def persistentOptionFileName(self) -> str:
        """
        Returns the name of the file to use for persistent data.
        """
        file = self.getOption("persistent-data-file")

        if file:
            file = file.replace("~", os.getenv("HOME"))
        else:
            configDir = self.baseConfigDirectory()
            if configDir == BuildContext.xdgConfigHome:
                # Global config is used. Store the data file in XDG_STATE_HOME.
                file = BuildContext.xdgStateHome + "/" + BuildContext.PERSISTENT_FILE_NAME
            else:
                # Local config is used. Store the data file in the same directory.
                file = configDir + "/." + BuildContext.PERSISTENT_FILE_NAME

            rcFiles = self.rcFiles
            if len(rcFiles) == 1:
                # This can only mean that the user specified an rcfile on the command
                # line and did not set persistent-data-file in their config file. In
                # this case, append the name of the rcfile to the persistent build
                # data file to associate it with that specific rcfile.
                rcFilePath = rcFiles[0]
                # ...But only if the specified rcfile isn't one of the default ones,
                # to prevent the user from making an oopsie
                if rcFilePath in BuildContext.rcfiles:
                    logger_buildcontext.warning("The specified rc file is one of the default ones. Ignoring it.")
                else:
                    rcFileName = os.path.basename(rcFilePath)
                    file = f"{file}-{rcFileName}"

            # Fallback to legacy data file if it exists and the new one doesn't.
            legacyDataFile = os.getenv("HOME") + "/.kdesrc-build-data"

            if not os.path.exists(file) and os.path.exists(legacyDataFile):
                file = legacyDataFile

            if file == legacyDataFile and not self.getOption("#warned-legacy-data-location"):
                logger_buildcontext.warning(textwrap.dedent(f"""\
                The b[global data file] is stored in the old location. It will still be
                processed correctly, however, it's recommended to move it to the new location.
                Please move b[~/.kdesrc-build-data] to b[{BuildContext.xdgStateHomeShort}/kdesrc-build-data]"""))
                self.setOption({"#warned-legacy-data-location": True})
        return file

    def loadPersistentOptions(self) -> None:
        """
        Reads in all persistent options from the file where they are kept
        (kdesrc-build-data) for use in the program.

        The directory used is the same directory that contains the rc file in use.
        """

        # pl2py note: this was commented there.
        # We need to keep persistent data with the context instead of with the
        # applicable modules since otherwise we might forget to write out
        # persistent data for modules we didn't build in this run. So, we just
        # store it all.
        #
        # Layout of this data:
        #  self.persistent_options = {
        #    'module-name': {
        #      option: value,
        #      # for each option/value pair
        #    },
        #    # for each module
        #  }
        self.persistent_options = {}

        fname = self.persistentOptionFileName()
        if not os.path.exists(fname):
            return

        persistent_data = Path(fname).read_text()

        # persistent_data should be a JSON object which we can store directly as a
        # dict.
        persistent_options = json.loads(persistent_data)
        e = "json exception"
        if not isinstance(persistent_options, dict):
            logger_buildcontext.error(f"Failed to read persistent module data: r[b[{e}]")
            return
        self.persistent_options = persistent_options

    def storePersistentOptions(self) -> None:
        """
        Writes out persistent options to the kdesrc-build-data file.
        The directory used is the same directory that contains the rc file in use.
        """
        if Debug().pretending():
            return

        fileName = self.persistentOptionFileName()
        dir_name = os.path.dirname(fileName)

        if not os.path.isdir(dir_name):
            Util.super_mkdir(dir_name)

        try:
            encodedJSON = json.dumps(self.persistent_options, indent=3)
            Path(fileName).write_text(encodedJSON)
        except Exception as e:
            logger_buildcontext.error(f"Unable to save persistent module data: b[r[{e}]")
            return

    # @override(check_signature=False)
    def getPersistentOption(self, moduleName: str, key=None) -> str | int | None:
        """
        Returns the value of a "persistent" option (normally read in as part of
        startup), or None if there is no value stored.

        Parameters:
            moduleName: The module name to get the option for, or 'global' if
                not for a module.
                Note that unlike setOption/getOption, no inheritance is done at this
                point so if an option is present globally but not for a module you
                must check both if that's what you want.
            key: The name of the value to retrieve (i.e. the key)

        Return type - for example used in
          int - global last-metadata-update
        """
        persistent_opts = self.persistent_options if hasattr(self, "persistent_options") else []

        # We must check at each level of indirection to avoid
        # "autovivification"
        if moduleName not in persistent_opts:
            return
        if key not in persistent_opts[moduleName]:
            return
        return persistent_opts[moduleName][key]

    # @override(check_signature=False)
    def unsetPersistentOption(self, moduleName: str, key) -> None:
        """
        Clears a persistent option if set (for a given module and option-name).

        Parameters:
            moduleName: The module name to get the option for, or 'global' for
                the global options.
            key: The name of the value to clear.

        Returns:
            None
        """

        persistent_opts = self.persistent_options

        if moduleName in persistent_opts and key in persistent_opts[moduleName]:
            del persistent_opts[moduleName][key]

    # @override(check_signature=False)
    def setPersistentOption(self, moduleName: str, key, value) -> None:
        """
        Sets a "persistent" option which will be read in for a module when
        kde-builder starts up and written back out at (normal) program exit.

        Parameters:
            moduleName: The module name to set the option for, or 'global'.
            key: The name of the value to set (i.e. key)
            value: The value to store.
        """

        persistent_opts = self.persistent_options

        # Initialize empty hash ref if nothing defined for this module.
        if moduleName not in persistent_opts:
            persistent_opts[moduleName] = {}

        persistent_opts[moduleName][key] = value

    def getKDEProjectsMetadataModule(self) -> Module:
        """
        Returns the :class:`Module` (which has a 'metadata' scm type) that is used for
        kde-project metadata, so that other modules that need it can call into it if
        necessary.

        Also, may return None if the metadata is unavailable or has not yet
        been set by setKDEProjectsMetadataModule (this method does not
        automatically create the needed module).
        """
        # Initialize if not set
        if not self.kde_projects_metadata:
            self.kde_projects_metadata = ModuleSet_KDEProjects.getProjectMetadataModule(self)

        return self.kde_projects_metadata

    def getProjectDataReader(self) -> KDEProjectsReader:
        """
        Returns a KDEProjectsReader module, which has already read in the database and
        is ready to be queried. Note that exceptions can be thrown in the process
        of downloading and parsing the database information, so be ready for that.
        """
        if self.projects_db:
            return self.projects_db

        projectDatabaseModule = self.getKDEProjectsMetadataModule() or BuildException.croak_runtime(f"kde-projects repository information could not be downloaded: {str(sys.exc_info()[1])}")

        self.projects_db = KDEProjectsReader(projectDatabaseModule)
        return self.projects_db

    def effectiveBranchGroup(self) -> str:
        """
        Returns the effective branch group to use for modules. You should not call
        this unless KDE project metadata is available (see
        setKDEProjectsMetadataModule and moduleBranchGroupResolver).
        """
        branchGroup = self.getOption("branch-group") or "kf5-qt5"
        return branchGroup

    def moduleBranchGroupResolver(self) -> Module_BranchGroupResolver:
        """
        Returns a :class:`Module.BranchGroupResolver` which can be used to efficiently
        determine a git branch to use for a given kde-projects module (when the
        branch-group option is in use), as specified at
        https://community.kde.org/Infrastructure/Project_Metadata.
        """

        if not self.logical_module_resolver:
            metadataModule = self.getKDEProjectsMetadataModule()

            if not metadataModule:
                BuildException.croak_internal("Tried to use branch-group, but needed data wasn't loaded!")

            resolver = Module_BranchGroupResolver(metadataModule.scm().logicalModuleGroups())
            self.logical_module_resolver = resolver

        return self.logical_module_resolver

    def statusViewer(self) -> StatusView:
        return self.status_view
