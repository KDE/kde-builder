# SPDX-FileCopyrightText: 2012, 2013, 2014, 2015, 2017, 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import datetime
import errno
import fileinput
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import textwrap
import traceback

from .build_exception import BuildException
from .debug import Debug
from .debug import KBLogger
from .kde_projects_reader import KDEProjectsReader
from .module.branch_group_resolver import ModuleBranchGroupResolver
from .module.module import Module
from .module_set.kde_projects import ModuleSetKDEProjects
from .options_base import OptionsBase
from .phase_list import PhaseList
from .status_view import StatusView
from .util.util import Util
from .version import Version

logger_buildcontext = KBLogger.getLogger("build-context")


# We derive from Module so that BuildContext acts like the 'global'
# Module, with some extra functionality.
# TODO: Derive from OptionsBase directly and remove get_option override
class BuildContext(Module):
    """
    This contains the information needed about the build context, e.g. list of
    modules, what phases each module is in, the various options, etc.

    It also records information on which modules encountered errors (and what
    error), where to put log files, persistent options that should be available on
    the next run, and basically anything else that falls into the category of state
    management.

    The "global" module

    One interesting thing about this class is that, as a state-managing class, this
    class implements the role of :class:`Module` for the pseudo-module called
    "global" throughout the source code (and whose options are defined in the
    "global" section in the rc-file). It is also a parent to every :class:`Module` in
    terms of the option hierarchy, serving as a fallback source for :class:`Module`'s
    `get_option()` calls for most (though not all!) options.

    Examples:
    ::

         ctx = BuildContext.BuildContext()

         ctx.set_rc_file("/path/to/kdesrc-buildrc")
         fh = ctx.load_rc_file()

         ...

         for modName in selectors:
            ctx.add_module(Module.Module(ctx, modName))

         ...
         module_list = ctx.modules
    """

    # According to XDG spec, if XDG_STATE_HOME is not set, then we should
    # default to ~/.local/state
    xdg_state_home = os.getenv("XDG_STATE_HOME", os.getenv("HOME") + "/.local/state")
    xdg_state_home_short = xdg_state_home.replace(os.getenv("HOME"), "~")  # Replace $HOME with ~

    # According to XDG spec, if XDG_CONFIG_HOME is not set, then we should
    # default to ~/.config
    xdg_config_home = os.getenv("XDG_CONFIG_HOME", os.getenv("HOME") + "/.config")
    xdg_config_home_short = xdg_config_home.replace(os.getenv("HOME"), "~")  # Replace $HOME with ~

    rcfiles = ["./kdesrc-buildrc",
               f"{xdg_config_home}/kdesrc-buildrc",
               f"""{os.getenv("HOME")}/.kdesrc-buildrc"""]
    LOCKFILE_NAME = ".kdesrc-lock"
    PERSISTENT_FILE_NAME = "kdesrc-build-data"
    SCRIPT_VERSION = Version.script_version()

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
        self.global_options_private = {
            "filter-out-phases": "",
            "git-push-protocol": "git",
            "git-repository-base": {"qt6-copy": "https://invent.kde.org/qt/qt/", "_": "fake/"},
            "manual-build": "",
            "manual-update": "",
            "module-definitions-dir": os.environ.get("XDG_STATE_HOME", os.environ["HOME"] + "/.local/state") + "/sysadmin-repo-metadata/module-definitions",
            "repository": "",  # module's git repo
            "set-env": {},  # dict of environment vars to set
            "ssh-identity-file": "",  # If set, is passed to ssh-add.
            "use-modules": ""
        }

        # These options are exposed as cmdline options, but _not from here_.
        # Their more complex specifier is made in `Cmdline` _supported_options().
        self.global_options_with_extra_specifier = {
            "build-when-unchanged": True,
            "colorful-output": True,
            "ignore-modules": "",
            "niceness": "10",  # todo convert to int?
            "pretend": "",
            "refresh-build": "",
        }

        # These options are exposed as cmdline options without parameters, and having the negatable form with "--no-".
        self.global_options_with_negatable_form = {
            "async": True,
            "compile-commands-export": True,  # 2021-02-06 allow to generate compile_commands.json via cmake, for clangd tooling
            "compile-commands-linking": False,  # 2021-02-06 link generated compile_commands.json back to the source directory
            "delete-my-patches": False,  # Should only be set from cmdline
            "delete-my-settings": False,  # Should only be set from cmdline
            "disable-agent-check": False,  # If true we don't check on ssh-agent
            "generate-vscode-project-config": False,
            "include-dependencies": True,
            "install-after-build": True,
            "install-login-session": True,
            "purge-old-logs": True,
            "run-tests": False,  # 1 = make test, upload = make Experimental  # todo why boolean option may have "upload" value?
            "stop-on-failure": True,
            "use-clean-install": False,
            "use-idle-io-priority": False,
            "use-inactive-modules": False,
        }

        # These options are exposed as cmdline options that require some parameter
        self.global_options_with_parameter = {
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
        self.global_options_without_parameter = {
            "build-system-only": "",
            "reconfigure": "",
            "refresh-build-first": "",
            "metadata-only": "",
        }

        # newOpts
        self.modules: list[Module] = []  # list of modules to build
        self.context = self  # Fix link to buildContext (i.e. self)
        self.build_options = {
            "global": {
                **self.global_options_private,
                **self.global_options_with_extra_specifier,
                **self.global_options_without_parameter,
                **self.global_options_with_negatable_form,
                **self.global_options_with_parameter,
            },
            # Module options are stored under here as well, keyed by module.name
        }
        # This one replaces `Module` {phases}
        self.phases = PhaseList()

        self.errors = {
            # A map from module *names* (as in modules[] above) to the
            # phase name at which they failed.
        }
        self.log_paths = {
            # Holds a dict of log path bases as expanded by
            # get_subdir_path (e.g. [source-dir]/log) to the actual log dir
            # *this run*, with the date and unique id added. You must still
            # add the module name to use.
        }
        self.rc_files = BuildContext.rcfiles
        self.rc_file = None
        self.env = {}
        self.persistent_options = {}  # These are kept across multiple script runs
        self.ignore_list = []  # List of KDE project paths to ignore completely
        self.kde_projects_metadata = None  # Enumeration of kde-projects
        self.logical_module_resolver = None  # For branch-group option
        self.status_view: StatusView = StatusView()
        self.projects_db = None  # See get_project_data_reader

        self.options = self.build_options["global"]

    def add_module(self, module: Module) -> None:
        if not module:
            traceback.print_exc()
            raise Exception("No module to push")

        path = None
        if module in self.modules:
            logger_buildcontext.debug("Skipping duplicate module " + module.name)
        elif ((path := module.full_project_path()) and
              any(re.search(rf"(^|/){item}($|/)", path) for item in self.ignore_list)):
            # See if the name matches any given in the ignore list.

            logger_buildcontext.debug(f"Skipping ignored module {module}")
        else:
            logger_buildcontext.debug(f"Adding {module} to module list")
            self.modules.append(module)

    def add_to_ignore_list(self, moduleslist: list[str]) -> None:
        """
        Adds a list of modules to ignore processing on completely.
        Parameters should simply be a list of KDE project paths to ignore,
        e.g. "extragear/utils/kdesrc-build". Partial paths are acceptable, matches
        are determined by comparing the path provided to the suffix of the full path
        of modules being compared.  See :meth:`KDEProjectsReader._project_path_matches_wildcard_search`.

        Existing items on the ignore list are not removed.
        """
        self.ignore_list.extend(moduleslist)

    def setup_operating_environment(self) -> None:
        # Set the process priority
        os.nice(int(self.get_option("niceness")))
        # Set the IO priority if available.
        if self.get_option("use-idle-io-priority"):
            # -p $$ is our PID, -c3 is idle priority
            # 0 return value means success
            if Util.safe_system(["ionice", "-c3", "-p", os.getpid()]) != 0:
                logger_buildcontext.warning(" b[y[*] Unable to lower I/O priority, continuing...")

        # Get ready for logged output.
        Debug().set_log_file(self.get_log_dir_for(self) + "/build-log")

        # # Propagate HTTP proxy through environment unless overridden.
        proxy = self.get_option("http-proxy")
        if proxy and "http_proxy" not in os.environ:
            self.queue_environment_variable("http_proxy", proxy)

    def reset_environment(self) -> None:
        """
        Clears the list of environment variables to set for log_command runs.
        """
        self.env = {}

    def queue_environment_variable(self, key: str, value: str) -> None:
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
        if not value:
            return

        logger_buildcontext.debug(f"\tQueueing g[{key}] to be set to y[{value}]")
        self.env[key] = value

    def commit_environment_changes(self) -> None:
        """
        Applies all changes queued by queue_environment_variable to the actual
        environment irretrievably. Use this before exec()'ing another child, for
        instance.
        """
        for key, value in self.env.items():
            os.environ[key] = value
            logger_buildcontext.debug(f"\tSetting environment variable g[{key}] to g[b[{value}]")

    def prepend_environment_value(self, env_name: str, items: str) -> None:  # pl2py: the items was a list in perl, but it was never used as list. So will type it as str.
        """
        Adds the given library paths to the path already given in an environment
        variable. In addition, detected "system paths" are stripped to ensure
        that we don't inadvertently re-add a system path to be promoted over the
        custom code we're compiling (for instance, when a system Qt is used and
        installed to /usr).

        If the environment variable to be modified has already been queued using
        queue_environment_variable, then that (queued) value will be modified and
        will take effect with the next forked subprocess.

        Otherwise, the current environment variable value will be used, and then
        queued. Either way the current environment will be unmodified afterward.

        Parameters:
            env_name: The name of the environment variable to modify
            items: Prepended to the current environment path, in
                the order given. (i.e. param1, param2, param3 -> param1:param2:param3:existing)
        """

        if env_name in self.env:
            cur_paths = self.env[env_name].split(":")
        elif env_name in os.environ:
            cur_paths = os.environ.get(env_name, "").split(":")
        else:
            cur_paths = []

        # pl2py: this is kde-builder specific code (not from kdesrc-build).
        # Some modules use python packages in their build process. For example, breeze-gtk uses python-cairo.
        # We want the build process to use system installed package rather than installed in virtual environment.
        # We remove the current virtual environment path from PATH, because Cmake FindPython3 module always considers PATH,
        # see https://cmake.org/cmake/help/latest/module/FindPython3.html
        # But note that user still needs to provide these cmake options: -DPython3_FIND_VIRTUALENV=STANDARD -DPython3_FIND_UNVERSIONED_NAMES=FIRST
        if sys.prefix != sys.base_prefix and env_name == "PATH":
            if f"{sys.prefix}/bin" in cur_paths:
                logger_buildcontext.debug(f"\tRemoving python virtual environment path y[{sys.prefix}/bin] from y[PATH], to allow build process to find system python packages outside virtual environment.")
                cur_paths.remove(f"{sys.prefix}/bin")
            else:
                logger_buildcontext.debug(f"\tVirtual environment path y[{sys.prefix}/bin] was already removed from y[PATH].")

        # Filter out entries to add that are already in the environment from
        # the system.
        for path in [item for item in [items] if item in cur_paths]:
            logger_buildcontext.debug(f"\tNot prepending y[{path}] to y[{env_name}] as it appears " + f"to already be defined in y[{env_name}].")

        items = [item for item in [items] if item not in cur_paths]

        env_value = ":".join(items + cur_paths)

        env_value = re.sub(r"^:*", "", env_value)
        env_value = re.sub(r":*$", "", env_value)  # Remove leading/trailing colons
        env_value = re.sub(r":+", ":", env_value)  # Remove duplicate colons

        self.queue_environment_variable(env_name, env_value)

    def take_lock(self) -> bool:
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
        base_dir = self.base_config_directory()
        lockfile = f"{base_dir}/{BuildContext.LOCKFILE_NAME}"

        lockfile_fd = None
        try:
            lockfile_fd = os.open(lockfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except OSError as e:
            error_code = e.errno  # Save for later testing.
        else:
            error_code = 0

        if error_code == errno.EEXIST:
            # Path already exists, read the PID and see if it belongs to a
            # running process.
            try:
                pid_file = open(lockfile, "r")
            except OSError:
                # Lockfile is there but we can't open it?!?  Maybe a race
                # condition but I have to give up somewhere.
                logger_buildcontext.warning(f" WARNING: Can't open or create lockfile r[{lockfile}]")
                return True

            pid = pid_file.read()
            pid_file.close()

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
                lockfile_fd = os.open(lockfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except OSError:
                logger_buildcontext.error(f" r[*] Still unable to lock {lockfile}, proceeding anyways...")
                return True
            # Hope the sysopen worked... fall-through
        elif error_code == errno.ENOTTY:
            # Stupid bugs... normally sysopen will return ENOTTY, not sure who's to blame between
            # glibc and Perl but I know that setting PERLIO=:stdio in the environment "fixes" things.
            pass
        elif error_code != 0:  # Some other error occurred.
            logger_buildcontext.warning(f" r[*]: Error {error_code} while creating lock file (is {base_dir} available?)")
            logger_buildcontext.warning(" r[*]: Continuing the script for now...")

            # Even if we fail it's generally better to allow the script to proceed
            # without being a jerk about things, especially as more non-CLI-skilled
            # users start using kde-builder to build KDE.
            return True

        os.write(lockfile_fd, str(os.getpid()).encode())
        os.close(lockfile_fd)
        return True

    def close_lock(self) -> None:
        """
        Releases the lock obtained by take_lock.
        """
        base_dir = self.base_config_directory()
        lock_file = f"{base_dir}/{BuildContext.LOCKFILE_NAME}"

        try:
            os.unlink(lock_file)
        except Exception as e:
            logger_buildcontext.warning(f" y[*] Failed to close lock: {e}")

    def get_log_dir_for(self, module: Module) -> str:
        """
        This function accepts a Module parameter, and returns the log directory
        for it. You can also pass a BuildContext (including this one) to get the
        default log directory.

        As part of setting up what path to use for the log directory, the
        'latest' symlink will also be setup to point to the returned log
        directory.
        """

        base_log_path = module.get_subdir_path("log-dir")
        if base_log_path not in self.log_paths:
            # No log dir made for this base, do so now.
            log_id = "01"
            date = datetime.datetime.now().strftime("%F")  # ISO 8601 date
            while os.path.exists(f"{base_log_path}/{date}-{log_id}"):
                log_id = str(int(log_id) + 1).zfill(2)
            self.log_paths[base_log_path] = f"{base_log_path}/{date}-{log_id}"

        log_dir = self.log_paths[base_log_path]
        Util.super_mkdir(log_dir)

        # global logs go to basedir directly
        if not isinstance(module, BuildContext):
            log_dir += f"/{module}"

        return log_dir

    def get_log_path_for(self, module: Module, path: str) -> str:
        """
        Constructs the appropriate full path to a log file based on the given
        basename (including extensions). Use this instead of get_log_dir_for when you
        actually intend to create a log, as this function will also adjust the
        'latest' symlink properly.
        """
        base_log_path = module.get_subdir_path("log-dir")
        log_dir = self.get_log_dir_for(module)

        # We create this here to avoid needless empty module directories everywhere
        Util.super_mkdir(log_dir)

        # Provide a directory to make it easy to see the last build for a module's
        # given phase (like cmake, build, install, etc.) without having to find the
        # log dir for the specific kde-builder run.
        Util.super_mkdir(f"{base_log_path}/latest-by-phase/{module}")

        # Add a symlink to the latest run for this module. 'latest' itself is
        # a directory under the base log directory that holds symlinks mapping
        # each module name to the specific log directory most recently used.
        latest_path = f"{base_log_path}/latest"

        # Handle stuff like playground/utils or KDE/kdelibs
        module_name, module_path = os.path.splitext(os.path.basename(module.name))
        if "/" in module.name:
            latest_path += f"/{module_path}"

        Util.super_mkdir(latest_path)

        symlink = f"{latest_path}/{module_name}"
        Util.remake_symlink(log_dir, symlink)

        symlink2 = f"{base_log_path}/latest-by-phase/{module}/{path}"
        Util.remake_symlink(f"{log_dir}/{path}", symlink2)

        return f"{log_dir}/{path}"

    def rc_file(self) -> None:
        """
        Returns rc file in use. Call load_rc_file first.
        """
        return self.rc_file

    def set_rc_file(self, file: str) -> None:
        """
        Forces the rc file to be read from to be that given by the first parameter.
        """
        self.rc_files = [file]
        self.rc_file = None

    @staticmethod
    def warn_legacy_config(file: str) -> None:
        """
        Warns a user if the config file is stored in the old location.
        """
        if file.startswith(os.getenv("HOME")):
            file = re.sub(os.getenv("HOME"), "~", file)
        if file == "~/.kdesrc-buildrc":
            logger_buildcontext.warning(textwrap.dedent(f"""\
            The b[global configuration file] is stored in the old location. It will still be
            processed correctly, however, it's recommended to move it to the new location.
            Please move b[~/.kdesrc-buildrc] to b[{BuildContext.xdg_config_home_short}/kdesrc-buildrc]
            """))

    def load_rc_file(self) -> fileinput.FileInput:
        """
        Returns an open filehandle to the user's chosen rc file. Use set_rc_file
        to choose a file to load before calling this function, otherwise
        load_rc_file will search the default search path. After this function is
        called, rc_file() can be used to determine which file was loaded.

        If unable to find or open the rc file an exception is raised. Empty rc
        files are supported, however.
        """
        rc_files = self.rc_files

        for file in rc_files:
            if os.path.exists(file):
                # fh = open(file, "r")  # does not support current line numbers reading
                # fh = fileinput.input(files=file, mode="r")  # does not support multiple instances
                fh = fileinput.FileInput(files=file, mode="r")  # supports multiple instances, so use this.

                self.rc_file = os.path.abspath(file)
                BuildContext.warn_legacy_config(file)
                return fh

        # No rc found, check if we can use default.
        if len(rc_files) == 1:
            # This can only happen if the user uses --rc-file, so if we fail to
            # load the file, we need to fail to load at all.
            failed_file = rc_files[0]

            logger_buildcontext.error(textwrap.dedent(f"""\
            Unable to open config file {failed_file}
            
            Script stopping here since you specified --rc-file on the command line to
            load {failed_file} manually.  If you wish to run the script with no configuration
            file, leave the --rc-file option out of the command line.
            
            If you want to force an empty rc file, use --rc-file /dev/null
            
            """))
            BuildException.croak_runtime(f"Missing {failed_file}")

        if self.get_option("metadata-only"):
            # If configuration file in default location was not found, and no --rc-file option was used, and metadata-only option was used.

            # In FirstRun user may decide to use --install-distro-packages before --generate-config.
            # --install-distro-packages requires the metadata to be downloaded to read the "disrto-dependencies" from it.
            # After downloading metadata, we normally should change 'last-metadata-update' persistent option value.
            # To store persistent option, we should know persistent-data-file value, and it is read from config.
            # At this moment we know that there is no config at default location, and user did not specified the --rc-file option.
            # And because we do not want to _require_ the config to be available yet, we just will provide dummy config.
            # This way the --metadata-only option could work in both cases: when user has config and when he has not.
            # When he has config (not current case), the persistent option "last-metadata-update" will be set as expected, and after the build process will be stored in persistent file.
            # When he has no config (the current case), we will let the _read_configuration_options function do its work on fake config, then we will return.
            dummy_config = textwrap.dedent("""\
                global
                    persistent-data-file /not/existing/file  # should not exist in file system (so it is not tried to be read, otherwise we should provide a valid json)
                end global
    
                # To suppress warning about no modules in configuration.
                module fake
                end module
                """)

            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
            temp_file.write(dummy_config)
            temp_file_path = temp_file.name
            temp_file.close()

            fh = fileinput.FileInput(files=temp_file_path, mode="r")
            self.rc_file = "/fake/dummy_config"
            return fh
        else:
            # If no configuration and no --rc-file option was used, warn the user and fail.

            logger_buildcontext.error(textwrap.dedent(f"""\
                b[No configuration file is present.]
                
                kde-builder requires a configuration file to select which KDE software modules
                to build, what options to build them with, the path to install to, etc.
                
                When run, kde-builder will use `kdesrc-buildrc' config file located in the
                current working directory. If no such file exists, kde-builder will use
                `{BuildContext.xdg_config_home_short}/kdesrc-buildrc' instead.
                
                You can generate config with b[--generate-config].
                """))
            BuildException.croak_runtime("No configuration available")

    def base_config_directory(self) -> str:
        """
        Returns the base directory that holds the configuration file. This is
        typically used as the directory base for other necessary kde-builder
        execution files, such as the persistent data store and lock file.

        The RC file must have been found and loaded first, obviously.
        """
        rcfile = self.rc_file
        if not rcfile:
            BuildException.croak_internal("Call to base_config_directory before load_rc_file")
        return os.path.dirname(rcfile)

    def modules_in_phase(self, phase: str) -> list[Module]:
        modules_list = [module for module in self.modules if module.phases.has(phase)]
        return modules_list

    def uses_concurrent_phases(self) -> bool:
        # If we have an 'update' phase and any other phase (build / test / install
        # / etc) we should use concurrency if it is available.
        has_update = False
        has_other = False

        for mod in self.modules:
            for phase in mod.phases.phaselist:
                if phase == "update":
                    has_update = True
                else:
                    has_other = True
            if has_update and has_other:
                return True
        return False

    def lookup_module(self, module_name: str):
        """
        Searches for a module with a name that matches the provided parameter,
        and returns its :class:`Module` object. Returns None if no match was found.
        As a special-case, returns the BuildContext itself if the name passed is
        "global", since the BuildContext also is a (in the "is-a" OOP sense)
        :class:`Module`, specifically the 'global' one.
        """
        if module_name == "global":
            return self

        options = [module for module in self.modules if module.name == module_name]
        if not options:
            return None

        if len(options) > 1:
            BuildException.croak_internal(f"Detected 2 or more {module_name} `Module` objects")
        return options[0]

    def mark_module_phase_failed(self, phase: str, module: Module) -> None:
        Util.assert_isa(module, Module)
        self.errors[module.name] = phase

    def failed_modules_in_phase(self, phase: str) -> list[Module]:
        """
        Returns a list of Modules that failed to complete the given phase.
        """
        failures = [module for module in self.modules if self.errors.get(module.name, "") == phase]
        return failures

    def list_failed_modules(self) -> list[Module]:
        """
        Returns a list of modules that had a failure of some sort, in the order the modules
        are listed in our current module list.
        """
        modules = self.modules

        # grepping for failures instead of returning error list directly maintains ordering
        modules = [module for module in modules if module.name in self.errors]
        return modules

    # @override(check_signature=False)
    def get_option(self, key: str) -> str | dict | list | bool:
        """
        Our immediate parent class Module overrides this, but we actually
        want the OptionsBase version to be used instead, until we break the recursive
        use of Module's own get_option calls on our get_option.

        Returns:
             The same types that OptionsBase.get_option returns.
        """
        return OptionsBase.get_option(self, key)

    # @override
    def set_option(self, options: dict) -> None:

        # Special case handling.
        if "filter-out-phases" in options:
            for phase in options["filter-out-phases"].split(" "):
                self.phases.filter_out_phase(phase)
            del options["filter-out-phases"]

        # Our immediate parent class Module overrides this, but we actually
        # want the OptionsBase version to be used instead, because Module's version specifically checks for
        # some options prohibited for it (such as "ignore-modules") but we may want such for BuildContext.
        OptionsBase.set_option(self, options)

        # Automatically respond to various global option changes.
        for key, value in options.items():
            normalized_key = key
            normalized_key = normalized_key.lstrip("#")  # Remove sticky key modifier.
            if normalized_key == "colorful-output":
                Debug().set_colorful_output(value)
            elif normalized_key == "pretend":
                Debug().set_pretending(value)

    # Persistent option handling

    def persistent_option_file_name(self) -> str:
        """
        Returns the name of the file to use for persistent data.
        """
        file = self.get_option("persistent-data-file")

        if file:
            file = file.replace("~", os.getenv("HOME"))
        else:
            config_dir = self.base_config_directory()
            if config_dir == BuildContext.xdg_config_home:
                # Global config is used. Store the data file in XDG_STATE_HOME.
                file = BuildContext.xdg_state_home + "/" + BuildContext.PERSISTENT_FILE_NAME
            else:
                # Local config is used. Store the data file in the same directory.
                file = config_dir + "/." + BuildContext.PERSISTENT_FILE_NAME

            rc_files = self.rc_files
            if len(rc_files) == 1:
                # This can only mean that the user specified an rcfile on the command
                # line and did not set persistent-data-file in their config file. In
                # this case, append the name of the rcfile to the persistent build
                # data file to associate it with that specific rcfile.
                rc_file_path = rc_files[0]
                # ...But only if the specified rcfile isn't one of the default ones,
                # to prevent the user from making an oopsie
                if rc_file_path in BuildContext.rcfiles:
                    logger_buildcontext.warning("The specified rc file is one of the default ones. Ignoring it.")
                else:
                    rc_file_name = os.path.basename(rc_file_path)
                    file = f"{file}-{rc_file_name}"

            # Fallback to legacy data file if it exists and the new one doesn't.
            legacy_data_file = os.getenv("HOME") + "/.kdesrc-build-data"

            if not os.path.exists(file) and os.path.exists(legacy_data_file):
                file = legacy_data_file

            if file == legacy_data_file and not self.get_option("#warned-legacy-data-location"):
                logger_buildcontext.warning(textwrap.dedent(f"""\
                The b[global data file] is stored in the old location. It will still be
                processed correctly, however, it's recommended to move it to the new location.
                Please move b[~/.kdesrc-build-data] to b[{BuildContext.xdg_state_home_short}/kdesrc-build-data]"""))
                self.set_option({"#warned-legacy-data-location": True})
        return file

    def load_persistent_options(self) -> None:
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

        fname = self.persistent_option_file_name()
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

    def store_persistent_options(self) -> None:
        """
        Writes out persistent options to the kdesrc-build-data file.
        The directory used is the same directory that contains the rc file in use.
        """
        if Debug().pretending():
            return

        file_name = self.persistent_option_file_name()
        dir_name = os.path.dirname(file_name)

        if not os.path.isdir(dir_name):
            Util.super_mkdir(dir_name)

        try:
            encoded_json = json.dumps(self.persistent_options, indent=3)
            Path(file_name).write_text(encoded_json)
        except Exception as e:
            logger_buildcontext.error(f"Unable to save persistent module data: b[r[{e}]")
            return

    # @override(check_signature=False)
    def get_persistent_option(self, module_name: str, key=None) -> str | int | None:
        """
        Returns the value of a "persistent" option (normally read in as part of
        startup), or None if there is no value stored.

        Parameters:
            module_name: The module name to get the option for, or "global" if
                not for a module.
                Note that unlike set_option/get_option, no inheritance is done at this
                point so if an option is present globally but not for a module you
                must check both if that's what you want.
            key: The name of the value to retrieve (i.e. the key)

        Return type - for example used in
          int - global last-metadata-update
        """
        persistent_opts = self.persistent_options if hasattr(self, "persistent_options") else []

        # We must check at each level of indirection to avoid
        # "autovivification"
        if module_name not in persistent_opts:
            return
        if key not in persistent_opts[module_name]:
            return
        return persistent_opts[module_name][key]

    # @override(check_signature=False)
    def unset_persistent_option(self, module_name: str, key) -> None:
        """
        Clears a persistent option if set (for a given module and option-name).

        Parameters:
            module_name: The module name to get the option for, or "global" for
                the global options.
            key: The name of the value to clear.

        Returns:
            None
        """

        persistent_opts = self.persistent_options

        if module_name in persistent_opts and key in persistent_opts[module_name]:
            del persistent_opts[module_name][key]

    # @override(check_signature=False)
    def set_persistent_option(self, module_name: str, key, value) -> None:
        """
        Sets a "persistent" option which will be read in for a module when
        kde-builder starts up and written back out at (normal) program exit.

        Parameters:
            module_name: The module name to set the option for, or "global".
            key: The name of the value to set (i.e. key)
            value: The value to store.
        """

        persistent_opts = self.persistent_options

        # Initialize empty dict if nothing defined for this module.
        if module_name not in persistent_opts:
            persistent_opts[module_name] = {}

        persistent_opts[module_name][key] = value

    def get_kde_projects_metadata_module(self) -> Module:
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
            self.kde_projects_metadata = ModuleSetKDEProjects.get_project_metadata_module(self)

        return self.kde_projects_metadata

    def get_project_data_reader(self) -> KDEProjectsReader:
        """
        Returns a KDEProjectsReader module, which has already read in the database and
        is ready to be queried. Note that exceptions can be thrown in the process
        of downloading and parsing the database information, so be ready for that.
        """
        if self.projects_db:
            return self.projects_db

        project_database_module = self.get_kde_projects_metadata_module() or BuildException.croak_runtime(f"kde-projects repository information could not be downloaded: {str(sys.exc_info()[1])}")

        self.projects_db = KDEProjectsReader(project_database_module)
        return self.projects_db

    def effective_branch_group(self) -> str:
        """
        Returns the effective branch group to use for modules. You should not call
        this unless KDE project metadata is available (see
        setKDEProjectsMetadataModule and module_branch_group_resolver).
        """
        branch_group = self.get_option("branch-group") or "kf5-qt5"
        return branch_group

    def module_branch_group_resolver(self) -> ModuleBranchGroupResolver:
        """
        Returns a :class:`Module.BranchGroupResolver` which can be used to efficiently
        determine a git branch to use for a given kde-projects module (when the
        branch-group option is in use), as specified at
        https://community.kde.org/Infrastructure/Project_Metadata.
        """

        if not self.logical_module_resolver:
            metadata_module = self.get_kde_projects_metadata_module()

            if not metadata_module:
                BuildException.croak_internal("Tried to use branch-group, but needed data wasn't loaded!")

            resolver = ModuleBranchGroupResolver(metadata_module.scm().logical_module_groups())
            self.logical_module_resolver = resolver

        return self.logical_module_resolver
