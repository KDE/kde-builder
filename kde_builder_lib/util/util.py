# SPDX-FileCopyrightText: 2012, 2013, 2015, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2020 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import base64
import codecs
import hashlib
from io import StringIO
import logging
import os.path
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import textwrap
from typing import Callable
from typing import TYPE_CHECKING

import setproctitle

from kde_builder_lib.build_exception import BuildException
from kde_builder_lib.debug import Debug
from kde_builder_lib.debug import KBLogger

if TYPE_CHECKING:
    from ..module.module import Module

if sys.platform == "darwin":
    import multiprocess as multiprocessing
else:
    import multiprocessing

logger_logged_cmd = KBLogger.getLogger("logged-command")
logger_util = KBLogger.getLogger("util")


class Util:
    """
    Useful utilities, which are exported into the calling module's namespace by default.
    """

    @staticmethod
    def list_has(list_ref: list, value):
        """
        Function to work around a Perl language limitation.
        Parameters:
            list_ref: The list to search. ALWAYS.
            value: The value to search for.
        Returns:
             True if the value is in the list
        No need to use it in Python. We can just use `if "value" in list_ref`.
        """
        return value in list_ref

    @staticmethod
    def locate_exe(prog: str, preferred: list[str] | None = None):
        """
        Function to return the path to the given executable based on
        either the given paths or the current PATH.
        E.g.:
        ::

            locate_exe("make") -> "/usr/bin/make"
            locate_exe("make", "foo", "bar") -> /foo/make
            If the executable is not found None is returned.

        This assumes that the module environment has already been updated since
        binpath doesn't exactly correspond to os.environ["PATH"].
        """

        if preferred is None:
            preferred = []

        # If it starts with a / the path is already absolute.
        if re.match(r"^/", prog):
            return prog

        paths = preferred if preferred else os.environ.get("PATH").split(":")
        for path in paths:
            if os.access(f"{path}/{prog}", os.X_OK):
                return f"{path}/{prog}"
        return None

    @staticmethod
    def assert_isa(obj, class_name):
        """
        Throws an exception if the first parameter is not an object at all, or if
        it is not an object of the type given by the second parameter (which
        should be a string of the class name). There is no return value.
        """
        if not isinstance(obj, class_name):
            BuildException.croak_internal(f"{obj} is not of type {class_name}, but of type " + type(obj))
        return obj

    @staticmethod
    def assert_in(val, list_ref):
        """
        Throws an exception if the first parameter is not included in the
        provided list of possible alternatives.
        Parameters:
            val: The value to check.
            list_ref: List of alternatives.
        """
        if val not in list_ref:
            BuildException.croak_runtime(f"{val} is not a permissible value for its argument")

        return val

    @staticmethod
    def safe_unlink(path):
        """
        Function to unlink the given symlink if global-pretend isn't set.
        """
        if Debug().pretending():
            logger_util.pretend(f"\tWould have unlinked {path}.")
            return 1  # Return true
        return os.unlink(path)

    @staticmethod
    def safe_system(cmd_list: list[str]) -> int:
        """
        Function to execute the system call on the given list if the pretend
        global option is not set.

        Returns:
             The shell error code, so 0 means success, non-zero means failure.
        """
        if not Debug().pretending():
            logger_util.debug("\tExecuting g['" + "' '".join(cmd_list) + "'")
            return subprocess.run(cmd_list).returncode

        logger_util.pretend("\tWould have run g['" + "' '".join(cmd_list) + "'")
        return 0  # Return true (success code)

    @staticmethod
    def p_chdir(directory):
        """
        Is exactly like "chdir", but it will also print out a message saying that
        we're switching to the directory when debugging.
        """
        logger_util.debug(f"\tcd g[{directory}]")

        try:
            os.chdir(directory)
        except OSError as e:
            if Debug().pretending():
                return 1
            BuildException.croak_runtime(f"Could not change to directory {directory}: {e}")

    @staticmethod
    def super_mkdir(pathname):
        """
        Creates a directory, including any parent directories that may also need
        created. Does nothing in pretend mode (but it does remember that it would
        have created the path to avoid message spam).

        Throws an exception on failure. See Path.
        """

        if not hasattr(Util, "createdPaths"):
            Util.createdPaths = {}

        if Debug().pretending():
            if pathname not in Util.createdPaths and not os.path.exists(pathname):
                logger_util.pretend(f"\tWould have created g[{pathname}]")
            Util.createdPaths[pathname] = True
            return True
        else:
            Path(pathname).mkdir(parents=True, exist_ok=True)
            return True if os.path.exists(pathname) else False

    @staticmethod
    def file_digest_md5(file_name):
        """
        Calculates the MD5 digest of a file already on-disk. The digest is
        returned as a hex string digest as from md5.hexdigest

        Parameters:
             file_name: File name to read

        Returns:
            hex string MD5 digest of file.
        An exception is thrown if an error occurs reading the file.
        """
        md5 = hashlib.md5()
        with open(file_name, "rb") as file:
            while True:
                chunk = file.read(8192)
                if not chunk:
                    break
                md5.update(chunk)
        return md5.hexdigest()

    @staticmethod
    def disable_locale_message_translation():
        """
        This function is intended to disable the message translation catalog
        settings in the program environment, so that any child processes executed
        will have their output untranslated (and therefore scrapeable).

        As such this should only be called for a forked child about to exec as
        there is no easy way to undo this within the process.
        """
        # Ensure that program output is untranslated by setting 'C' locale.
        # We're really trying to affect the LC_MESSAGES locale category, but
        # LC_ALL is a catch-all for that (so needs to be unset if set).
        #
        # Note that the ONLY SUPPORTED way to pass file names, command-line
        # args, etc. to commands is under the UTF-8 encoding at this point, as
        # that is the only sane way for this en_US-based developer to handle
        # the task.

        os.environ["LC_MESSAGES"] = "C"
        if "LC_ALL" in os.environ:
            os.environ["LANG"] = os.environ["LC_ALL"]  # This is lower-priority "catch all"
            del os.environ["LC_ALL"]

    @staticmethod
    def filter_program_output(filter_func: Callable | None, program: str, *args) -> list[str]:
        """
        Returns a list of output lines from a program. Use this only if you expect
        that the output after filtering will be short.

            def filter(arg):
                if arg.upper():
                    return True
            output = filter_program_output(filter, "git", "describe", "HEAD")

        Parameters:
            filter_func: function to use as a filter (this function  will
                be passed a line at a time and should return True if the line should be
                returned). If no filtering is desired pass None.
            program: The program to run (either full path or something
                accessible in PATH).
            *args: All remaining arguments are passed to the program.
        """

        if filter_func is None:
            def filter_func(_):
                return True  # Default to all lines

        logger_util.debug(f"""\tSlurping '{program}' '{"' '".join(args)}'""")

        # Check early for whether an executable exists.
        if not Util.locate_exe(program):
            BuildException.croak_runtime(f"Can't find {program} in PATH!")

        # todo Originally, the Util.disable_locale_message_translation() was applied to the subprocess, check if it is needed
        p = subprocess.run([program, *args], shell=False, capture_output=True)
        exit_code = p.returncode
        child_output = p.stdout.decode()

        if "\0" in child_output:
            child_outputs = [item + "\0" for item in child_output.split("\0") if item]  # pl2py: for our git command terminated with --null
        else:
            child_outputs = child_output.split("\n")
            child_outputs = child_outputs[:-1] if child_outputs[-1] == "" else child_outputs  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it. # pl2py split
            child_outputs = list(map(lambda x: x + "\n", child_outputs))

        lines = [line for line in child_outputs if filter_func(line)]

        if exit_code:
            # other errors might still be serious but don't need a backtrace
            if Debug().pretending():
                logger_util.debug(f"{program} gave error exit code {exit_code}")
            else:
                logger_util.warning(f"{program} gave error exit code {exit_code}")
        return lines

    @staticmethod
    def prettify_seconds(elapsed: int):
        """
        Function to return a string suitable for displaying an elapsed time,
        (like a stopwatch) would. The first parameter is the number of seconds
        elapsed.
        """

        calculated = {}
        elapsed = int(elapsed)

        calculated["seconds"] = elapsed % 60
        elapsed = int(elapsed / 60)

        calculated["minutes"] = elapsed % 60
        elapsed = int(elapsed / 60)

        calculated["hours"] = elapsed % 24
        elapsed = int(elapsed / 24)

        calculated["days"] = elapsed

        str_list = []
        for text in ["days", "hours", "minutes", "seconds"]:
            value = calculated[text]
            if value == 1:  # Make singular
                text = re.sub(r"s$", "", text)

            if text == "seconds":
                str_list.append(f"{value} {text}")

        # Add "and " in front of last element if there was more than one.
        if len(str_list) > 1:
            str_list.append("and " + str_list.pop(0))

        return_str = ", ".join(str_list)
        return return_str

    @staticmethod
    def _set_error_logfile(module, logfile) -> None:
        """
        Function to mark a file as being the error log for a module. This also
        creates a symlink in the module log directory for easy viewing.
        Parameters:
            module: The module in question.
            logfile: The filename in the log directory of the error log.
        """
        if not logfile:
            return

        logdir = module.get_log_dir()

        if module.has_sticky_option("error-log-file"):
            logger_util.error(f"{module} already has error log set, tried to set to r[b[{logfile}]")
            return

        module.set_option({"#error-log-file": f"{logdir}/{logfile}"})
        logger_util.debug(f"Logfile for {module} is {logfile}")

        # Setup symlink in the module log directory pointing to the appropriate
        # file.  Make sure to remove it first if it already exists.
        if os.path.islink(f"{logdir}/error.log"):
            os.unlink(f"{logdir}/error.log")

        if os.path.exists(f"{logdir}/error.log"):
            # Maybe it was a regular file?
            logger_util.error("r[b[ * Unable to create symlink to error log file]")
            return

        if os.path.exists(logdir):  # pl2py: in unit test, the log dir is not created. In perl symlinking just does not care and proceeds, but in python the exception is thrown. So we make this check.
            os.symlink(f"{logfile}", f"{logdir}/error.log")

    @staticmethod
    def run_logged_command(module: Module, filename: str, callback_ref: Callable | None, command: list[str]) -> int:
        """
        Common code for log_command and UtilLoggedSubprocess
        """
        logger_logged_cmd.info(f"run_logged_command(): Module {module}, Command: " + " ".join(command))

        if re.match(r"\.log$", filename) or re.match(r"/", filename):
            BuildException.croak_internal(f"Pass only base filename for {module}/{filename}")
        logpath = module.get_log_path(f"{filename}.log")

        # Fork a child, with its stdout connected to CHILD.
        pipe_read, pipe_write = os.pipe()
        pid = os.fork()

        if pid:
            # Parent
            os.close(pipe_write)

            dec = codecs.getincrementaldecoder('utf8')()  # We need incremental decoder, because our pipe may be split in half of multibyte character, see https://stackoverflow.com/a/62027284/7869636

            if not callback_ref and logger_logged_cmd.isEnabledFor(logging.DEBUG):
                with open(logpath, "w") as f_logpath:  # pl2py: they have written both to file and to pipe from child. We instead just write to pipe from child, and write to file from here
                    # If no other callback given, pass to debug() if debug-mode is on.
                    while True:
                        line = dec.decode(os.read(pipe_read, 4096))
                        if not line:
                            break
                        if line.strip():
                            print(line.strip())
                        f_logpath.write(line)  # pl2py: actually write to file, which was done by tee in child in perl

            if callback_ref:
                with open(logpath, "w") as f_logpath:  # pl2py: they have written both to file and to pipe from child. We instead just write to pipe from child, and write to file from here
                    while True:
                        line = dec.decode(os.read(pipe_read, 4096))
                        if not line:
                            break
                        callback_ref(line)  # Note that line may contain several lines (a string containing "\n")
                        f_logpath.write(line)  # pl2py: actually write to file, which was done by tee in child in perl

            _, return_code = os.waitpid(pid, 0)
            try:
                os.close(pipe_read)
            except OSError as e:
                BuildException.croak_internal(f"syscall failed waiting on log_command to finish: {e}")

            # kernel stuff went OK but the child gave a failing exit code
            if return_code != 0:
                logger_util.debug(f"{module} command logged to {logpath} gave non-zero exit: {return_code}")
                return return_code
            return 0
        else:
            # Child. Note here that we need to avoid running our exit cleanup
            # handlers in here. For that we need sys.exit.

            setproctitle.setproctitle("kde-builder run_logged_command: " + " ".join(command))

            # Apply altered environment variables.
            module.context.commit_environment_changes()

            signal.signal(signal.SIGPIPE, signal.SIG_IGN)

            def sigint_handler(signum, frame):
                sys.stdout.close()  # This should be a pipe
                sys.stderr.close()
                sys.exit(signal.SIGINT)

            signal.signal(signal.SIGINT, sigint_handler)

            # Redirect STDIN to /dev/null so that the handle is open but fails when
            # being read from (to avoid waiting forever for e.g. a password prompt
            # that the user can't see.

            if "KDESRC_BUILD_USE_TTY" not in os.environ:
                with open("/dev/null", "r") as dev_null:
                    os.dup2(dev_null.fileno(), 0)

            if callback_ref or logger_logged_cmd.isEnabledFor(logging.DEBUG):
                # pl2py: in perl here they created another pipe to tee command. It connected stdout of child to tee stdin, and the tee have written to file.
                # I (Andrew Shark) will instead catch the output there from parent and write to file from there.
                os.close(1)
                os.dup2(pipe_write, 1)  # pl2py : redirect the stdout of child to the pipe
            else:
                try:
                    f_logpath = open(logpath, "w")
                    os.close(1)  # close stdout
                    os.dup2(f_logpath.fileno(), 1)  # open stdout, that will be the logpath file
                except OSError as e:
                    logger_util.error(f"Error {e} opening log to {logpath}!")

            # Call internal function, name given by $command[1]
            if command[0] == "kde-builder":
                # No colors!
                Debug().set_colorful_output(False)
                logger_util.debug(f"Calling {command[1]}")

                cmd = command[1]
                del command[0:2]  # Remove first two elements.

                exitcode = int(cmd())
                sys.exit(exitcode)

            # Make sure we log everything.
            os.close(2)  # close stderr
            os.dup2(1, 2)  # open stderr, that will be our stdout

            # Don't leave empty output files, give an indication of the particular
            # command run.
            print("# kde-builder running: '" + "' '".join(command) + "'")
            print("# from directory: ", os.getcwd())

            # TODO: Implement this when appropriate, but also keep in mind that
            # filter_program_output might be a better idea if you're parsing
            # output, and that function already does this.
            # disable_locale_message_translation();

            # External command.
            try:
                os.execvp(command[0], command)
            except Exception as e:
                cmd_string = " ".join(command)
                logger_util.error(textwrap.dedent(f"""\
                    r[b[Unable to execute "{cmd_string}"]!
                    {e}
                    
                    Please check your binpath setting (it controls the PATH used by kde-builder).
                    Currently it is set to g[{os.environ.get("PATH")}].
                    """))
                # Don't use return, this is the child still!
                sys.exit(1)

    @staticmethod
    def good_exitcode(exitcode: int) -> bool:
        """
        Returns True if exitcode is 0, False otherwise.
        """
        return exitcode == 0

    @staticmethod
    def log_command(module: Module, filename: str, arg_ref: list[str], options_ref: dict | None = None) -> int:
        """
        Function to run a command, optionally filtering on the output of the child
        command. Use like:

            exitcode = log_command(module, "build-output", ["make", "-j4"])

        After the required three parameters (module, base name for log file, and a list
        with the command and arguments) you can pass a dict of optional
        features:

            def callback(line):
                ...

        A function to have each line of child output passed to. This
        output is not supposed to be printed to the screen by the function, normally
        the output is only logged. However, this is useful for e.g. munging out the
        progress of the build.

        If you wish to run short commands and look through their output, prefer
        ``filter_program_output`` instead, as this disables message translation.

        #  "no_translate": any true value will cause a flag to be set to request
        #  the executed child process to not translate (for locale purposes) its
        #  output, so that it can be screen-scraped.

        The return value is the shell return code, so 0 is success, and non-zero is
        failure.

        `NOTE`: This function has a special feature. If the command passed into the
        argument reference is "kde-builder", then log_command will, when it forks,
        execute the function named by the second parameter rather than executing a
        child process. The function should include the full python module name as well
        (otherwise the package containing log_command's implementation is used). The
        remaining arguments in the list are passed to the function that is called.

        Pretend handling:

        The program is not actually executed in pretend mode. If you need the program
        to always be run, use a python IPC mechanism like os.system(), subprocess, or
        a utility like ``filter_program_output``.
        """
        if options_ref is None:
            options_ref = {}

        command = arg_ref
        callback_ref = options_ref.get("callback", None)

        if Debug().pretending():
            logger_logged_cmd.pretend("\tWould have run g['" + "' '".join(command) + "'")
            return 0
        return Util.run_logged_command(module, filename, callback_ref, arg_ref)

    @staticmethod
    def run_logged(module: Module, filename: str, directory: str | None, arg_ref: list[str], callback_ref: Callable | None = None) -> int:
        """
        This is similar to ``log_command`` in that this runs the given command and
        arguments in a separate process. Returns the exit status of the sub-process.

        ``directory`` parameter allows you to set the working directory to use in the *subprocess* it creates.
        If the ``directory`` parameter is None then the directory is not changed.
        ::

            builddir = module.fullpath("build")  # need to pass dir to use
            result = run_logged(module, "build", builddir, ["make", "-j8"])
            def func(result):
                print(f"Process result: {result}")

            func(result)
        """

        if not directory:
            directory = ""
        if Debug().pretending():
            args_str = "', '".join(arg_ref)
            logger_logged_cmd.pretend(f"\tWould have run g{{'{args_str}'}}")
            return 0

        # Do this before we fork so the path is finalized to prevent auto-detection
        # in the child
        # Todo Check if this is still needed.
        module.get_log_path(f"{filename}.log")

        def subprocess_run(target: Callable) -> int:
            retval = multiprocessing.Value("i", -1)
            subproc = multiprocessing.Process(target=target, args=(retval,))
            subproc.start()
            # LoggedSubprocess runs subprocess from event loop, while here it is not the case, so we allow blocking join
            subproc.join()
            return retval.value

        def func(retval):
            # This happens in a CHILD PROCESS, not in the main process!
            # This means that changes made by log_command or function calls made
            # via log_command will not be saved or noted unless they are made part
            # of the return value, or sent earlier via a 'progress' event.
            setproctitle.setproctitle("kde-builder " + " ".join(arg_ref))  # better indicate what is the process
            if directory:
                Util.p_chdir(directory)
            retval.value = Util.log_command(module, filename, arg_ref, {"callback": callback_ref})

        exitcode = subprocess_run(func)
        logger_logged_cmd.info(f"run_logged() completed with exitcode: {exitcode}. d[Log file: {module.get_log_path(filename + '.log')}\n")
        if not exitcode == 0:
            Util._set_error_logfile(module, f"{filename}.log")
        return exitcode

    @staticmethod
    def split_quoted_on_whitespace(line):
        """
        This function acts like split(" ", arg) except that double-quoted strings
        are not split in the process.

        Parameters:
            line: String to split on whitespace.
        Returns:
            A list of the individual words and quoted values in the string.
            The quotes themselves are not returned.
        """
        return shlex.split(line.strip())

    @staticmethod
    def pretend_open(path, default_text: str = ""):
        """
        Opens the given file and returns a filehandle to it if the file actually exists or the script is not in pretend mode.
        If the script is in pretend mode and the file is not already present then an open filehandle to an empty string is returned.

        Parameters:
            path: Path to the file to open.
            default_text: String to use if the file doesn't exist in pretend mode

        Returns:
            filehandle on success (supports readline() and eof()), can return boolean
            false if there is an error opening an existing file (or if the file doesn't
            exist when not in pretend mode)
        """

        if Debug().pretending() and not os.path.exists(path):
            try:
                fh = StringIO(default_text)
            except IOError:
                return False
        else:
            try:
                fh = open(path, "r")
            except IOError:
                return False

        return fh

    @staticmethod
    def any(sub_ref, list_ref):
        """
        Returns true if the given function returns true for any item in the given list.
        """
        return any(sub_ref(item) for item in list_ref)

    # pl2py: perl specific, not needed
    # @staticmethod
    # def unique_items(*args):
    #     """
    #     Returns unique items of the list. Order not guaranteed.
    #     """
    #     # See perlfaq4
    #     seen = {}
    #     results = []
    #     for item in args:
    #         if item not in seen:
    #             seen[item] += 1
    #             results.append(item)
    #     return results

    @staticmethod
    def safe_rmtree(path) -> bool:
        """
        Function to delete a directory and all files and subdirectories within.
        Does nothing in pretend mode. An analog to "rm -rf" from Linux.

        Parameters:
             path: Path to delete
        Returns:
             True on success, False for failure.
        """
        # Pretty user-visible path
        user_path = path
        user_path = re.sub(r"^" + os.environ["HOME"], "~", user_path)

        if Debug().pretending():
            logger_util.pretend(f"Would have removed all files/folders in {user_path}")
            return True

        # Error out because we probably have a logic error even though it would
        # delete just fine.
        if not os.path.isdir(path):
            logger_util.error(f"Cannot recursively remove {user_path}, as it is not a directory.")
            return False

        try:
            shutil.rmtree(path)

        except Exception as e:
            logger_util.error(f"Unable to remove directory {user_path}: {e}")
            return False
        return True

    @staticmethod
    def get_list_digest(args: list[str]) -> str:
        """
        Returns a hash digest of the given options in the list. The return value is
        base64-encoded at this time.

        Note: Don't be dumb and pass data that depends on execution state as the
        returned hash is almost certainly not useful for whatever you're doing with
        it.  (i.e. passing a reference to a list is not helpful, pass the list itself)

        Parameters:
             args: List of values to hash.
        Returns:
             base64-encoded hash value.
        """

        md5_hash = hashlib.md5()
        for arg in args:
            md5_hash.update(arg.encode())
        return base64.b64encode(md5_hash.digest()).decode().rstrip("=")

    @staticmethod
    # Can just use `if not os.listdir(dir_path)` instead.
    def is_dir_empty(dir_path):
        """
        Utility function to see if a directory path is empty or not
        """
        try:
            with os.scandir(dir_path) as entries:
                for entry in entries:
                    if not entry.name == "." and not entry.name == "..":
                        return False  # not empty
        except OSError:
            return False
        return True

    @staticmethod
    def safe_lndir(from_path: str, to_path: str) -> int:
        """
        Recursively symlink a directory into another location, in a
        similar fashion to how the XFree/X.org lndir() program does it. This is
        reimplemented here since some systems lndir doesn't seem to work right.

        Use by passing two `absolute` paths, the first being where to symlink files
        from, and the second being what directory to symlink them into.
        ::

            result = safe_lndir("/path/to/symlink", "/where/to/put/symlinks")
            def func(result):
                if result:
                    print("success")

            func(result)

        All intervening directories will be created as needed. In addition, you may
        safely run this function again if you only want to catch additional files in
        the source directory.

        Returns:
            1 if successful, 0 if unsuccessful.
        """

        if Debug().pretending():
            return 1

        if not os.path.isabs(from_path) or not os.path.isabs(to_path):
            BuildException.croak_internal("Both paths to safe_lndir must be absolute paths!")

        # Create destination directory.
        if not Util.super_mkdir(to_path):
            logger_util.error(f"Couldn't create directory r[{to_path}]")
            return 0

        # # Create closure callback subroutine.
        # def wanted(root, dirs, files):
        #
        #     dir = re.sub(from_path, to_path, dir)
        #
        #     # Ignore version-control metadata
        #     if re.search(r"/\.git", dir) :
        #         return
        #
        #     if not Util.super_mkdir(dir):
        #         BuildException.croak_runtime(f"Couldn't create directory {dir}: $!")
        #
        #     # Symlink the file.  Check if it's a regular file because File::Find
        #     # has no qualms about telling you you have a file called "foo/bar"
        #     # before pointing out that it was really a directory.
        #     if os.path.isfile(file) and not os.path.exists(f"{dir}/$_"):
        #         if not os.symlink(file, f"{dir}/$_"):
        #             BuildException.croak_runtime(f"Couldn't create file {dir}/$_: $!")

        def subprocess_run(target: Callable):
            retval = multiprocessing.Value("i", -1)
            subproc = multiprocessing.Process(target=target, args=(retval,))
            subproc.start()
            # LoggedSubprocess runs subprocess from event loop, while here it is not the case, so we allow blocking join
            subproc.join()
            return retval.value

        def func(retval):
            # Happens in child process
            try:
                for root, dirs, files in os.walk(from_path):
                    # wanted(root, dirs, files)
                    relative_path = os.path.relpath(root, from_path)
                    target_dir = os.path.join(to_path, relative_path)

                    os.makedirs(target_dir, exist_ok=True)

                    for file in files:
                        link_source = os.path.join(root, file)
                        link_target = os.path.join(target_dir, file)
                        os.symlink(link_source, link_target)
            except Exception as e:
                logger_util.error(f"Unable to symlink {from_path} to {to_path}: {e}")
                retval.value = 0
            retval.value = 1

        result = subprocess_run(func)
        return result

    @staticmethod
    def prune_under_directory(module: Module, target_dir: str) -> int:
        """
        Delete recursively everything under the given directory, unless
        we're in pretend mode.

        Used from :class:`BuildSystem` to handle cleaning a build directory.

        I.e. the effect is similar to `rm -r arg/* arg/.*`.
        ::

            result = prune_under_directory_p(module, "/path/to/clean")

        Returns:
            1 on success, 0 on failure.
        """

        logpath = module.get_log_path("clean-builddir.log")
        log = None
        try:
            log = open(logpath, "w")
        except IOError as e:
            logger_util.error(f"\tError opening logfile {logpath}: r[b[{e}]")
            logger_util.error("\tContinuing without logging")

        print(f"starting delete of {target_dir}", file=log)

        try:
            def subprocess_run(target: Callable):
                retval = multiprocessing.Value("i", -1)
                subproc = multiprocessing.Process(target=target, args=(retval,))
                subproc.start()
                # LoggedSubprocess runs subprocess from event loop, while here it is not the case, so we allow blocking join
                subproc.join()
                if subproc.exitcode != 0:  # This is exit code of running subprocess, but not the returned value of the function in subprocess.
                    raise Exception(f"Subprocess failed with exitcode {subproc.exitcode}")
                return retval.value

            def func(retval):
                error_ref = {}

                with os.scandir(target_dir) as entries:
                    for entry in entries:
                        if entry.is_dir() and not entry.is_symlink():
                            try:
                                shutil.rmtree(entry.path)
                            except OSError as ex:
                                error_ref[entry.path] = ex
                        else:
                            try:
                                os.remove(entry.path)
                            except OSError as ex:
                                error_ref[entry.path] = ex

                if error_ref and len(error_ref):
                    for file in error_ref:
                        msg = error_ref[file]
                        if not file:
                            file = "general error"
                        print(f"{file}: error: {msg}", file=log)

                    retval.value = 0
                else:
                    retval.value = 1
                log.close()
                # pl2py: As we are in subprocess, we have "returned" the value via a shared variable.
                # The actual (normal) return value cannot be read by the parent process.

            result = subprocess_run(func)
            return result

        except Exception as e:
            logger_util.error(f"\tUnable to clean r[{target_dir}]:\n\ty[b[{e}]")
            return 0  # an error

    @staticmethod
    def remake_symlink(src, dst):
        # Make a symlink from dst to src. If symlink exists, ensures that it points to the requested src.
        # Parameters:
        #   src - path to point to (symlink target)
        #   dst - path to point from (symlink name)
        #
        # Return: 1 on success, 0 on failure.

        if os.path.isfile(dst) and not os.path.islink(dst):  # if dst is not a symlink to file, but a regular file
            BuildException.croak_runtime(f"Could not create '{dst}' symlink, because file with this name exists. Please remove it manually.")

        if os.path.isdir(dst) and not os.path.islink(dst):  # if dst is not a symlink to directory, but a regular directory
            BuildException.croak_runtime(f"Could not create '{dst}' symlink, because directory with this name exists. Please remove it manually.")

        if os.path.islink(dst) and os.readlink(dst) != src:  # if dst points to wrong src
            try:
                os.unlink(dst)  # delete wrong symlink
            except OSError:
                BuildException.croak_runtime(f"Could not delete '{dst}' symlink (needed to update target location). Please remove it manually.")

        if not os.path.exists(dst) and not os.path.islink(dst):  # pl2py: in perl the -e check also detects the symlinks, but in python the os.path.exists does not detect symlinks.
            try:
                os.symlink(src, dst)  # pl2py: in Perl, symlink command returns 1 on success, 0 on failure. In Python os.symlink returns None on success, raises exception on failure.
                return 1
            except FileNotFoundError:
                return 0

        return 1  # success (pointed to correct location already)