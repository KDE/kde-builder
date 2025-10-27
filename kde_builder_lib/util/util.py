# SPDX-FileCopyrightText: 2012, 2013, 2015, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2020 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import base64
import codecs
import hashlib
import logging
import os.path
from io import TextIOWrapper
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
from typing import Callable
from typing import TYPE_CHECKING

import setproctitle

from kde_builder_lib.kb_exception import KBRuntimeError
from kde_builder_lib.debug import Debug
from kde_builder_lib.debug import KBLogger
from ..kb_exception import ProgramError
from .textwrap_mod import dedent

if TYPE_CHECKING:
    from ..module.module import Module

logger_logged_cmd = KBLogger.getLogger("logged-command")
logger_util = KBLogger.getLogger("util")


class Util:
    """
    Helper methods that may be used across the KDE Builder code.
    """

    @staticmethod
    def locate_exe(prog: str, preferred: list[str] | None = None) -> str | None:
        """
        Return the path to the given executable based on either the given paths or the current PATH.

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
    def safe_unlink(path) -> None:
        """
        Unlink the given symlink if global-pretend isn't set.
        """
        if Debug().pretending():
            logger_util.debug(f"\tWould have unlinked {path}.")
            return
        os.unlink(path)

    @staticmethod
    def safe_system(cmd_list: list[str]) -> int:
        """
        Execute the system call on the given list if the pretend global option is not set.

        Returns:
             The shell error code, so 0 means success, non-zero means failure.
        """
        if not Debug().pretending():
            logger_util.debug("\tExecuting g['" + "' '".join(cmd_list) + "'")
            return subprocess.run(cmd_list).returncode

        logger_util.debug("\tWould have run g['" + "' '".join(cmd_list) + "'")
        return 0  # Return true (success code)

    @staticmethod
    def p_chdir(directory) -> None:
        """
        Is exactly like "chdir", but it will also print out a message saying that we're switching to the directory when debugging.
        """
        logger_util.debug(f"\tcd g[{directory}]")

        try:
            os.chdir(directory)
        except OSError as e:
            if Debug().pretending():
                return
            raise KBRuntimeError(f"Could not change to directory {directory}: {e}")

    @staticmethod
    def super_mkdir(pathname) -> bool:
        """
        Create a directory, including any parent directories that may also need created.

        Does nothing in pretend mode (but it does remember that it would
        have created the path to avoid message spam).

        Throws an exception on failure. See Path.
        """
        if not hasattr(Util, "createdPaths"):
            Util.createdPaths = {}

        if Debug().pretending():
            if pathname not in Util.createdPaths and not os.path.exists(pathname):
                logger_util.debug(f"\tWould have created g[{pathname}]")
            Util.createdPaths[pathname] = True
            return True
        else:
            try:
                Path(pathname).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(e)
            return True if os.path.exists(pathname) else False

    @staticmethod
    def file_digest_md5(file_name) -> str:
        """
        Calculate the MD5 digest of a file already on-disk.

        The digest is returned as a hex string digest as from md5.hexdigest

        Args:
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
    def disable_locale_message_translation() -> None:
        """
        Disable the message translation catalog settings in the program environment.

        So any child processes executed will have their output untranslated (and therefore scrapeable).

        As such this should only be called for a forked child about to exec as
        there is no easy way to undo this within the process.
        """
        # Ensure that program output is untranslated by setting "C" locale.
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
    def get_program_output(program: str, *args) -> list[str]:
        """
        Return a list of output lines from a program.

        Args:
            program: The program to run (either full path or something
                accessible in PATH).
            *args: All remaining arguments are passed to the program.
        """
        logger_util.debug(f"""\tSlurping '{program}' '{"' '".join(args)}'""")

        # Check early for whether an executable exists.
        if not Util.locate_exe(program):
            raise KBRuntimeError(f"Can't find {program} in PATH!")

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

        lines = child_outputs

        if exit_code:
            # other errors might still be serious but don't need a backtrace
            if Debug().pretending():
                logger_util.debug(f"{program} gave error exit code {exit_code}")
            else:
                logger_util.warning(f"{program} gave error exit code {exit_code}")
        return lines

    @staticmethod
    def prettify_seconds(total_seconds: int) -> str:
        """
        Convert total number of seconds to a human-readable string.

        For example, 3601 will be converted to "1 hour, 0 minutes and 1 second" string.
        """
        # noinspection PyDictCreation
        calculated = {}
        remaining = total_seconds

        calculated["seconds"] = remaining % 60
        remaining = int(remaining / 60)

        calculated["minutes"] = remaining % 60
        remaining = int(remaining / 60)

        calculated["hours"] = remaining % 24
        remaining = int(remaining / 24)

        calculated["days"] = remaining

        str_list: list[str] = []
        for text in ["days", "hours", "minutes", "seconds"]:
            value = calculated[text]
            if value == 1:  # Make singular
                text = re.sub(r"s$", "", text)

            if value == 0 and len(str_list) == 0 and text != "seconds":
                # Skip leading zero values, like "0 days". But allow "0 seconds" alone.
                continue

            str_list.append(f"{value} {text}")

        return_str = ", ".join(str_list)
        return_str = re.sub(r", ([^,]*)$", r" and \1", return_str)  # Replace last ", " with " and ".
        return return_str

    @staticmethod
    def _run_logged_internal(module: Module, filename: str, args: list[str], callback_func: Callable | None) -> int:

        logger_logged_cmd.info(f"_run_logged_internal(): Project {module}, Command: " + " ".join(args))

        if re.match(r"\.log$", filename) or re.match(r"/", filename):
            raise ProgramError(f"Pass only base filename for {module}/{filename}")
        logpath = module.get_log_path(f"{filename}.log")

        # Fork a child, with its stdout connected to CHILD.
        pipe_read, pipe_write = os.pipe()
        pid = os.fork()

        if pid:
            # Parent
            os.close(pipe_write)

            dec = codecs.getincrementaldecoder("utf8")()  # We need incremental decoder, because our pipe may be split in half of multibyte character, see https://stackoverflow.com/a/62027284/7869636

            if not callback_func and logger_logged_cmd.isEnabledFor(logging.DEBUG):
                with open(logpath, "w") as f_logpath:  # pl2py: they have written both to file and to pipe from child. We instead just write to pipe from child, and write to file from here
                    # If no other callback given, pass to debug() if debug-mode is on.
                    while True:
                        line = dec.decode(os.read(pipe_read, 4096))
                        if not line:
                            break
                        if line.strip():
                            print(line.strip())
                        f_logpath.write(line)  # pl2py: actually write to file, which was done by tee in child in perl

            if callback_func:
                with open(logpath, "w") as f_logpath:  # pl2py: they have written both to file and to pipe from child. We instead just write to pipe from child, and write to file from here
                    while True:
                        line = dec.decode(os.read(pipe_read, 4096))
                        if not line:
                            break
                        callback_func(line)  # Note that line may contain several lines (a string containing "\n")
                        f_logpath.write(line)  # pl2py: actually write to file, which was done by tee in child in perl

            _, return_code = os.waitpid(pid, 0)
            try:
                os.close(pipe_read)
            except OSError as e:
                raise ProgramError(f"syscall failed waiting on log_command to finish: {e}")

            # Append the line with exit code to the log file that child process created
            with open(logpath, "a") as f:
                f.write(f"\n# exit code was: {return_code}\n")

            # kernel stuff went OK but the child gave a failing exit code
            if return_code != 0:
                logger_util.debug(f"{module} command logged to {logpath} gave non-zero exit: {return_code}")
                return return_code
            return 0
        else:
            # Child. Note here that we need to avoid running our exit cleanup
            # handlers in here. For that we need sys.exit.

            setproctitle.setproctitle("kde-builder run_logged_internal: " + " ".join(args))

            # Apply altered environment variables.
            module.commit_environment_changes()

            signal.signal(signal.SIGPIPE, signal.SIG_IGN)

            def sigint_handler(signum, frame):
                sys.stdout.close()  # This should be a pipe
                sys.stderr.close()
                sys.exit(signal.SIGINT)

            signal.signal(signal.SIGINT, sigint_handler)

            # Redirect STDIN to /dev/null so that the handle is open but fails when
            # being read from (to avoid waiting forever for e.g. a password prompt
            # that the user can't see.

            if "KDE_BUILDER_USE_TTY" not in os.environ:
                with open("/dev/null", "r") as dev_null:
                    os.dup2(dev_null.fileno(), 0)

            if callback_func or logger_logged_cmd.isEnabledFor(logging.DEBUG):
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

            # Make sure we log everything.
            os.close(2)  # close stderr
            os.dup2(1, 2)  # open stderr, that will be our stdout

            # Don't leave empty output files, give an indication of the particular
            # command run.
            print("# kde-builder running: '" + "' '".join(args) + "'")
            print("# from directory: ", os.getcwd())
            if module.current_phase != "update":
                print("# with environment: ", module.fullpath("build") + "/kde-builder.env")

            # disable_locale_message_translation();

            # External command.
            try:
                os.execvp(args[0], args)
            except Exception as e:
                cmd_string = " ".join(args)
                logger_util.error(dedent(f"""
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
        Return True if exitcode is 0, False otherwise.
        """
        return exitcode == 0

    @staticmethod
    def run_logged(module: Module, filename: str, directory: str | None, args: list[str], callback_func: Callable | None = None) -> int:
        """
        Run the command, and log it.

        If you wish to run short commands and look through their output, prefer
        ``filter_program_output`` instead, as this disables message translation.

        ::

            builddir = module.fullpath("build")  # need to pass dir to use
            result = run_logged(module, "build", builddir, ["make", "-j8"])

        Args:
            module: The Module object for which the command in args does something
            filename: A filename to use for log.
            directory: The working directory to run in. If it is None, the directory is not changed.
            args: The command to run - args[0] is the executable, the rest its arguments.
            callback_func: Optional. Will be invoked for every nonempty line of stdout from the command.
                           Useful for e.g. munging out the progress of the build.

        Returns:
            Exit status of the command. This is a shell return code, so 0 is success,
            and non-zero is failure.

        Pretend handling:
            The program is not actually executed in pretend mode. If you need the program
            to always be run, use a mechanism like os.system(), subprocess, or a utility like
            ``filter_program_output``.
        """
        if not directory:
            directory = ""
        if Debug().pretending():
            args_str = "', '".join(args)
            logger_logged_cmd.debug(f"\tWould have run] (g['{args_str}'])")
            return 0

        # Do this before we fork so the path is finalized to prevent auto-detection
        # in the child
        # Todo Check if this is still needed.
        module.get_log_path(f"{filename}.log")

        orig_wd = os.getcwd()
        if directory:
            Util.p_chdir(directory)

        exitcode = Util._run_logged_internal(module, filename, args, callback_func)

        logger_logged_cmd.debug("Return to the original working directory after running log_command().")
        Util.p_chdir(orig_wd)

        logger_logged_cmd.info(f"""run_logged() completed with exitcode: {exitcode}. Log file: {module.get_log_path(filename + ".log")}\n""")
        if not exitcode == 0:
            module.set_error_logfile(f"{filename}.log")
        return exitcode

    @staticmethod
    def split_quoted_on_whitespace(line) -> list[str]:
        """
        Split quoted on whitespace.

        This function acts like `line.split(" ")` except that double-quoted strings are not split in the process.

        Args:
            line: String to split on whitespace.

        Returns:
            A list of the individual words and quoted values in the string.
            The quotes themselves are not returned.
        """
        return shlex.split(line.strip())

    @staticmethod
    def safe_rmtree(path) -> bool:
        """
        Delete a directory and all files and subdirectories within.

        Does nothing in pretend mode. An analog to "rm -rf" from Linux.

        Args:
             path: Path to delete
        Returns:
             True on success, False for failure.
        """
        # Pretty user-visible path
        user_path = path
        user_path = re.sub(r"^" + os.environ["HOME"], "~", user_path)

        if Debug().pretending():
            logger_util.debug(f"Would have removed all files/folders in {user_path}")
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
        Return a hash digest of the given options in the list.

        The return value is base64-encoded at this time.

        Note: Don't be dumb and pass data that depends on execution state as the
        returned hash is almost certainly not useful for whatever you're doing with
        it.  (i.e. passing a reference to a list is not helpful, pass the list itself)

        Args:
             args: List of values to hash.

        Returns:
             base64-encoded hash value.
        """
        md5_hash = hashlib.md5()
        for arg in args:
            md5_hash.update(arg.encode())
        return base64.b64encode(md5_hash.digest()).decode().rstrip("=")

    @staticmethod
    def prune_under_directory(module: Module, target_dir: str) -> int:
        """
        Delete recursively everything under the given directory, unless we're in pretend mode.

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
            error_dict = {}

            with os.scandir(target_dir) as entries:
                for entry in entries:
                    if entry.is_dir() and not entry.is_symlink():
                        try:
                            shutil.rmtree(entry.path)
                        except OSError as ex:
                            error_dict[entry.path] = ex
                    else:
                        try:
                            os.remove(entry.path)
                        except OSError as ex:
                            error_dict[entry.path] = ex

            if error_dict:
                for file in error_dict:
                    msg = error_dict[file]
                    if not file:
                        file = "general error"
                    print(f"{file}: error: {msg}", file=log)
                result = 0
            else:
                result = 1
            log.close()

            return result

        except Exception as e:
            logger_util.error(f"\tUnable to clean r[{target_dir}]:\n\ty[b[{e}]")
            return 0  # an error

    @staticmethod
    def remake_symlink(src, dst) -> int:
        """
        Make a symlink from dst to src. If symlink exists, ensures that it points to the requested src.

        Args:
          src: path to point to (symlink target)
          dst: path to point from (symlink name)

        Return: 1 on success, 0 on failure.
        """
        if os.path.isfile(dst) and not os.path.islink(dst):  # if dst is not a symlink to file, but a regular file
            raise KBRuntimeError(f"Could not create \"{dst}\" symlink, because file with this name exists. Please remove it manually.")

        if os.path.isdir(dst) and not os.path.islink(dst):  # if dst is not a symlink to directory, but a regular directory
            raise KBRuntimeError(f"Could not create \"{dst}\" symlink, because directory with this name exists. Please remove it manually.")

        if os.path.islink(dst) and os.readlink(dst) != src:  # if dst points to wrong src
            try:
                os.unlink(dst)  # delete wrong symlink
            except OSError:
                raise KBRuntimeError(f"Could not delete \"{dst}\" symlink (needed to update target location). Please remove it manually.")

        if not os.path.exists(dst) and not os.path.islink(dst):  # pl2py: in perl the -e check also detects the symlinks, but in python the os.path.exists does not detect symlinks.
            try:
                os.symlink(src, dst)  # pl2py: in Perl, symlink command returns 1 on success, 0 on failure. In Python os.symlink returns None on success, raises exception on failure.
                return 1
            except FileNotFoundError:
                return 0

        return 1  # success (pointed to correct location already)
