import base64
import hashlib
import os.path
import re
import shutil
import sys
import textwrap
from io import StringIO
from pathlib import Path
import subprocess
import shlex
import signal
from ..Util.Conditional_Type_Enforced import conditional_type_enforced
from promise import Promise
import multiprocessing
import traceback
import codecs

from ksblib.Debug import Debug
from ksblib.BuildException import BuildException


@conditional_type_enforced
class Util:
    """
    Useful utilities, which are exported into the calling module's namespace by default.
    
    =head1 DESCRIPTION
    
    Various helpful methods.  This documentation doesn't cover them all currently,
    take a peek at the source.
    """
    
    def __init__(self):
        self.createdPaths = {}
        pass
    
    @staticmethod
    def list_has(listRef: list, value):
        """
        Function to work around a Perl language limitation.
        First parameter is a reference to the list to search. ALWAYS.
        Second parameter is the value to search for.
        Returns true if the value is in the list
        No need to use it in Python. We can just use `if "value" in listRef`.
        """
        return value in listRef
    
    @staticmethod
    def locate_exe(prog: str, preferred: list | None = None):
        """
        Subroutine to return the path to the given executable based on the
        either the given paths or the current PATH.
        E.g.:
        locate_exe('make') -> '/usr/bin/make'
        locate_exe('make', 'foo', 'bar') -> /foo/make
        If the executable is not found undef is returned.
        
        This assumes that the module environment has already been updated since
        binpath doesn't exactly correspond to $ENV{'PATH'}.
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
        should be a string of the class name. There is no return value;
        """
        if not isinstance(obj, class_name):
            BuildException.croak_internal(f"{obj} is not of type {class_name}, but of type " + type(obj))
        return obj
    
    @staticmethod
    def assert_in(val, listRef):
        """
        Throws an exception if the first parameter is not included in the
        provided list of possible alternatives. The list of alternatives must
        be passed as a reference, as the second parameter.
        """
        if val not in listRef:
            BuildException.croak_runtime(f"{val} is not a permissible value for its argument")
        
        return val
    
    @staticmethod
    def safe_unlink(path):
        """
        Subroutine to unlink the given symlink if global-pretend isn't set.
        """
        if Debug().pretending():
            Debug().pretend("\tWould have unlinked ", path, ".")
            return 1  # Return true
        return os.unlink(path)
    
    @staticmethod
    def safe_system(cmd_list: list):
        """
        Subroutine to execute the system call on the given list if the pretend
        global option is not set.
        
        Returns the shell error code, so 0 means success, non-zero means failure.
        """
        if not Debug().pretending():
            Debug().whisper(f"\tExecuting g['", "' '".join(cmd_list), "'")
            return subprocess.run(cmd_list).returncode
        
        Debug().pretend("\tWould have run g['" + "' '".join(cmd_list) + "'")
        return 0  # Return true (success code)
    
    @staticmethod
    def p_chdir(Dir):
        """
        Is exactly like "chdir", but it will also print out a message saying that
        we're switching to the directory when debugging.
        """
        Debug().debug(f"\tcd g[{Dir}]")
        
        try:
            os.chdir(Dir)
        except OSError as e:
            if Debug().pretending():
                return 1
            BuildException.croak_runtime(f"Could not change to directory {dir}: {e}")
    
    def super_mkdir(self, pathname):
        """
        Creates a directory, including any parent directories that may also need
        created.  Does nothing in pretend mode (but it does remember that it would
        have created the path to avoid message spam).
        
        Throws an exception on failure. See L<File::Path>.
        """
        
        if Debug().pretending():
            if pathname not in self.createdPaths and not os.path.exists(pathname):
                Debug().pretend(f"\tWould have created g[{pathname}]")
            self.createdPaths[pathname] = True
            return True
        else:
            Path(pathname).mkdir(parents=True, exist_ok=True)
            return True if os.path.exists(pathname) else False
    
    @staticmethod
    def file_digest_md5(fileName):
        """
        Calculates the MD5 digest of a file already on-disk. The digest is
        returned as a hex string digest as from Digest::MD5::md5_hex
        
        First parameter: File name to read
        Return value: hex string MD5 digest of file.
        An exception is thrown if an error occurs reading the file.
        """
        md5 = hashlib.md5()
        with open(fileName, "rb") as file:
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
        # the task.  Patches (likely using Encode::Locale) are accepted. :P
        
        os.environ["LC_MESSAGES"] = "C"
        if "LC_ALL" in os.environ:
            os.environ["LANG"] = os.environ["LC_ALL"]  # This is lower-priority "catch all"
            del os.environ["LC_ALL"]
    
    @staticmethod
    def filter_program_output(filterRef, program, *args) -> list[str]:
        """
        Returns an array of lines output from a program.  Use this only if you expect
        that the output after filtering will be short.
        
         my $filter = sub { return 1 if /^U/ };
         my @output = filter_program_output($filter, 'git', 'describe', 'HEAD');
        
        Since there is no way to disambiguate no output from an error, this function
        will call C<die> on error, wrap in C<eval> if this bugs you.
        
        First parameter is subroutine reference to use as a filter (this sub will
        be passed a line at a time and should return true if the line should be
        returned).  If no filtering is desired pass C<undef>.
        
        Second parameter is the program to run (either full path or something
        accessible in $PATH).
        
        All remaining arguments are passed to the program.
        """
        
        if filterRef is None:
            def filterRef(_):
                return True  # Default to all lines
        
        Debug().debug(f"""\tSlurping '{program}' '{"' '".join(args)}'""")
        
        # Check early for whether an executable exists since otherwise
        # it is possible for our fork-open below to "succeed" (i.e. fork()
        # happens OK) and then fail when it gets to the exec(2) syscall.
        if not Util.locate_exe(program):
            BuildException.croak_runtime(f"Can't find {program} in PATH!")
        
        execFailedError = "\t - kde-builder - exec failed!\n"
        try:
            pipe_read, pipe_write = os.pipe()
            pid = os.fork()
        except OSError as e:
            raise BuildException.croak_internal(f"Can't fork: {e}")
        
        if pid:
            # parent
            os.close(pipe_write)
            
            if not pipe_read:
                BuildException.croak_internal(f"Unable to open pipe to read {program} output")
            
            childOutput = b""
            while True:
                chunk = os.read(pipe_read, 4096)
                if not chunk:
                    break
                childOutput += chunk
            
            _, exitCode = os.waitpid(pid, 0)  # we do it after we have read the pipe, because otherwise we could be deadlocked if pipe overflowed (for example for "git ls-files" command long output)
            childOutput = childOutput.decode()
            
            if "\0" in childOutput:
                childOutputs = [item + "\0" for item in childOutput.split("\0") if item]  # pl2py: for our git command terminated with --null
            else:
                childOutputs = childOutput.split("\n")
                childOutputs = childOutputs[:-1] if childOutputs[-1] == "" else childOutputs  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it. # pl2py split
                childOutputs = list(map(lambda x: x + "\n", childOutputs))
            
            lines = [line for line in childOutputs if filterRef(line)]
            
            os.close(pipe_read)
            
            # we can pass serious errors back to ourselves too.
            if exitCode == 99 and len(lines) >= 1 and lines[0] == execFailedError:
                BuildException.croak_runtime(f"Failed to exec {program}, is it installed?")
            
            if exitCode:
                # other errors might still be serious but don't need a backtrace
                if Debug().pretending():
                    Debug().whisper(f"{program} gave error exit code {exitCode}")
                else:
                    Debug().warning(f"{program} gave error exit code {exitCode}")
            return lines
        else:
            os.close(pipe_read)
            Util.disable_locale_message_translation()
            
            # We don't want stderr output on tty.
            devnull = open(os.devnull, "w")
            os.dup2(devnull.fileno(), 2)
            
            os.dup2(pipe_write, 1)
            
            try:
                os.execvp(program, [program, *args])
            except OSError:
                # Send a message back to parent
                print(execFailedError)
                exit(99)  # Helper proc, so don't use finish(), just die
            finally:
                os.close(pipe_write)
    
    @staticmethod
    def prettify_seconds(elapsed):
        """
        Subroutine to return a string suitable for displaying an elapsed time,
        (like a stopwatch) would.  The first parameter is the number of seconds
        elapsed.
        """
        return_str = ""
        days = hours = minutes = seconds = fraction = ""
        
        fraction = int(100 * (elapsed - int(elapsed)))
        elapsed = int(elapsed)
        
        seconds = elapsed % 60
        elapsed = int(elapsed / 60)
        
        minutes = elapsed % 60
        elapsed = int(elapsed / 60)
        
        hours = elapsed % 24
        elapsed = int(elapsed / 24)
        
        days = elapsed
        
        if fraction:
            seconds = f"{seconds}.{fraction}"
        
        str_list = []
        for x in ["days", "hours", "minutes", "seconds"]:
            # Use a symbolic reference without needing to disable strict refs.
            # I couldn't disable it even if I wanted to because these variables
            # aren't global or localized global variables.
            value = eval(f"locals()[\"{x}\"]")
            text = x
            if value == 1:  # Make singular
                text = re.sub(r"s$", "", text)
            
            if value or x == "seconds":
                str_list.append(f"{value} {text}")
        
        # Add 'and ' in front of last element if there was more than one.
        if len(str_list) > 1:
            str_list.append("and " + str_list.pop(0))
        
        return_str = ", ".join(str_list)
        return return_str
    
    @staticmethod
    def _setErrorLogfile(module, logfile) -> None:
        """
        Subroutine to mark a file as being the error log for a module.  This also
        creates a symlink in the module log directory for easy viewing.
        First parameter is the module in question.
        Second parameter is the filename in the log directory of the error log.
        """
        if not logfile:
            return
        
        logdir = module.getLogDir()
        
        if module.hasStickyOption("error-log-file"):
            Debug().error(f"{module} already has error log set, tried to set to r[b[{logfile}]")
            return
        
        module.setOption({"#error-log-file": f"{logdir}/{logfile}"})
        Debug().debug(f"Logfile for {module} is {logfile}")
        
        # Setup symlink in the module log directory pointing to the appropriate
        # file.  Make sure to remove it first if it already exists.
        if os.path.islink(f"{logdir}/error.log"):
            os.unlink(f"{logdir}/error.log")
        
        if os.path.exists(f"{logdir}/error.log"):
            # Maybe it was a regular file?
            Debug().error("r[b[ * Unable to create symlink to error log file]")
            return
        
        if os.path.exists(logfile):  # pl2py: in unit test, the log dir is not created. In perl symlinking just does not care and proceeds, but in python the exception is thrown. So we make this check.
            os.symlink(f"{logfile}", f"{logdir}/error.log")
    
    @staticmethod
    def run_logged_command(module, filename: str, callbackRef, command: list) -> int:
        """
        Common code for log_command and ksb::Util::LoggedSubprocess
        """
        Debug().debug(f"run_logged_command(): Module {module}, Command: ", " ".join(command))
        
        if re.match(r"\.log$", filename) or re.match(r"/", filename):
            BuildException.croak_internal(f"Pass only base filename for {module}/{filename}")
        logpath = module.getLogPath(f"{filename}.log")
        
        # Fork a child, with its stdout connected to CHILD.
        pipe_read, pipe_write = os.pipe()
        pid = os.fork()
        
        if pid:
            # Parent
            os.close(pipe_write)
            
            dec = codecs.getincrementaldecoder('utf8')()  # We need incremental decoder, because our pipe may be split in half of multibyte character, see https://stackoverflow.com/a/62027284/7869636
            
            if not callbackRef and Debug().debugging():
                with open(logpath, "w") as f_logpath:  # pl2py: they have written both to file and to pipe from child. We instead just write to pipe from child, and write to file from here
                    # If no other callback given, pass to debug() if debug-mode is on.
                    while True:
                        line = dec.decode(os.read(pipe_read, 4096))
                        if not line:
                            break
                        if line.strip():
                            print(line.strip())
                        f_logpath.write(line)  # pl2py: actually write to file, which was done by tee in child in perl
            
            if callbackRef:
                with open(logpath, "w") as f_logpath:  # pl2py: they have written both to file and to pipe from child. We instead just write to pipe from child, and write to file from here
                    while True:
                        line = dec.decode(os.read(pipe_read, 4096))
                        if not line:
                            break
                        callbackRef(line)  # Note that line may contain several lines (a string containing "\n")
                        f_logpath.write(line)  # pl2py: actually write to file, which was done by tee in child in perl
            
            _, return_code = os.waitpid(pid, 0)
            try:
                os.close(pipe_read)
            except OSError as e:
                BuildException.croak_internal(f"syscall failed waiting on log_command to finish: {e}")
            
            # kernel stuff went OK but the child gave a failing exit code
            if return_code != 0:
                Debug().debug(f"{module} command logged to {logpath} gave non-zero exit: {return_code}")
                return return_code
            return 0
        else:
            # Child. Note here that we need to avoid running our exit cleanup
            # handlers in here. For that we need POSIX::_exit.
            
            # Apply altered environment variables.
            module.buildContext().commitEnvironmentChanges()
            
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
            
            def sigint_handler(signum, frame):
                sys.stdout.close()  # This should be a pipe
                sys.stderr.close()
                sys.exit("EINTR")
            
            signal.signal(signal.SIGINT, sigint_handler)
            
            # Redirect STDIN to /dev/null so that the handle is open but fails when
            # being read from (to avoid waiting forever for e.g. a password prompt
            # that the user can't see.
            
            if "KDESRC_BUILD_USE_TTY" not in os.environ:
                with open("/dev/null", "r") as dev_null:
                    os.dup2(dev_null.fileno(), 0)
            
            if callbackRef or Debug().debugging():
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
                    Debug().error(f"Error {e} opening log to {logpath}!")
            
            # Call internal function, name given by $command[1]
            if command[0] == "kde-builder":
                # No colors!
                Debug().setColorfulOutput(False)
                Debug().debug(f"Calling {command}[1]")
                
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
            except OSError as e:
                cmd_string = " ".join(command)
                Debug().error(textwrap.dedent(f"""\
                    r[b[Unable to execute "{cmd_string}"]!
                    {e}
                    
                    Please check your binpath setting (it controls the PATH used by kde-builder).
                    Currently it is set to g[{os.environ.get("PATH")}].
                    """))
                # Don't use return, this is the child still!
                sys.exit(1)
    
    @staticmethod
    def await_promise(promise: Promise):
        """
        Takes a promise on input and calls ->wait on it, blocking until the promise
        resolves.  Returns the promise passed in.
        
        You should not use this function except as a porting aid to convert
        log_command()-based async code to use promises.
        
        Throws an exception if the I/O loop is already in operation, as this indicates
        serious bugs.
        """
        # if promise.ioloop.is_running:
        #     BuildException.croak_internal("Tried to await a promise when I/O loop active!")
        promise = promise.get()
        return promise
    
    @staticmethod
    def await_exitcode(promise: Promise):
        """
        Takes a promise on input, adds a handler to extract the final result (treating
        it as a shell-style exit code), and calls ->wait on it, blocking until the
        promise resolves or rejects.
        
        You should not use this function except as a porting aid to convert
        log_command()-based async code to use promises.
        
        Returns a boolean value (true if the promise exitcode resolved to 0, false
        otherwise).
        
        Throws an exception if the I/O loop is already in operation, as this indicates
        serious bugs.
        """
        result = None
        
        def func(exitcode):
            nonlocal result
            result = exitcode == 0
        
        Util.await_promise(promise.then(func))
        return result
    
    @staticmethod
    def await_result(promise: Promise):
        """
        Takes a promise on input, adds a handler to extract the final result (as a
        scalar), and calls ->wait on it, blocking until the promise resolves or
        rejects.
        
        You should not use this function except as a porting aid to convert
        log_command()-based async code to use promises.
        
        Returns the scalar result.
        
        Throws an exception if the I/O loop is already in operation, as this indicates
        serious bugs.
        """
        result = None
        
        def func(result_from_p):
            nonlocal result
            result = result_from_p
        
        Util.await_promise(promise.then(func))
        return result
    
    @staticmethod
    def log_command(module, filename: str, argRef, optionsRef=None) -> int:
        """
        Subroutine to run a command, optionally filtering on the output of the child
        command. Use like:
        
         my $exitcode = log_command($module, 'build-output', [qw(make -j4)]);
        
        After the required three parameters (module, base name for log file, and a list
        with the command and arguments) you can pass a hash reference of optional
        features:
        
        =over
        
        =item C<callback =E<gt> sub ($line) { ... }>
        
        A reference to a subroutine to have each line of child output passed to.  This
        output is not supposed to be printed to the screen by the subroutine, normally
        the output is only logged.  However this is useful for e.g. munging out the
        progress of the build.
        
        If you wish to run short commands and look through their output, prefer
        L<"filter_program_output"> instead, as this disables message translation.
        
        =for comment
        #  'no_translate' => any true value will cause a flag to be set to request
        #  the executed child process to not translate (for locale purposes) its
        #  output, so that it can be screen-scraped.
        
        =back
        
        The return value is the shell return code, so 0 is success, and non-zero is
          failure.
        
        I<NOTE>: This function has a special feature.  If the command passed into the
        argument reference is 'kde-builder', then log_command will, when it forks,
        execute the subroutine named by the second parameter rather than executing a
        child process.  The subroutine should include the full package name as well
        (otherwise the package containing log_command's implementation is used).  The
        remaining arguments in the list are passed to the subroutine that is called.
        
        =head3 Pretend handling
        
        The program is not actually executed in pretend mode.  If you need the program
        to always be run, use a Perl IPC mechanism like L<system|perlfunc/"system"> or
        a utility like L<"filter_program_output">.
        """
        if optionsRef is None:
            optionsRef = {}
        
        command = list(argRef)
        callbackRef = optionsRef.get("callback", None)
        
        if Debug().pretending():
            Debug().pretend("\tWould have run g['" + "' '".join(command) + "'")
            return 0
        return Util.run_logged_command(module, filename, callbackRef, argRef)
    
    @staticmethod
    def run_logged_p(module, filename: str, directory, argRef: list[str]) -> Promise:
        """
        This is similar to C<log_command> in that this runs the given command and
        arguments in a separate process. The difference is that this command
        I<does not wait> for the process to finish, and instead returns a
        L<Mojo::Promise> that resolves to the exit status of the sub-process.
        
        Another important difference is that fewer options are currently supported.
        In particular there is no built-in way to filter the program output or to
        force off locale translations.
        
        This is useful in permitting concurrent code without needing to resolve
        significant changes from a separate thread of execution over time.
        
        Note that concurrent code should be careful about accessing global state
        simultaneously. This includes things like the current working directory, which
        is shared across the entire process.  run_logged_p allows you to pass a param
        to set the working directory to use in the *subprocess* it creates so that
        there is no contention over the main process's current working directory.
        If the C<$directory> param is C<undef> then the directory is not changed.
        
         my $builddir = $module->fullpath('build'); # need to pass dir to use
         my $promise = run_logged_p($module, 'build', $builddir, [qw(make -j8)]);
         $promise->then(sub ($result) {
           say "Process result: $result";
         })->wait;
        
        # TODO: For really concurrent code we need to have run_logged_p change to a
        # specific directory in the subprocess, add to this interface.
        """
        
        if not directory:
            directory = ""
        if Debug().pretending():
            args_str = "', '".join(argRef)
            Debug().pretend(f"\tWould have run g{{'{args_str}'}}")
            return Promise.resolve(0)
        
        # Do this before we fork so the path is finalized to prevent auto-detection
        # in the child
        logpath = module.getLogPath(f"{filename}.log")
        
        def subprocess_run_p(target: callable) -> Promise:
            def subprocess_run():
                retval = multiprocessing.Value("i", -1)
                subproc = multiprocessing.Process(target=target, args=(retval,))
                subproc.start()
                # LoggedSubprocess runs subprocess from event loop, while here it is not the case, so we allow blocking join
                subproc.join()
                return retval.value
            
            p = Promise.promisify(subprocess_run)()
            return p
        
        def func(retval):
            # This happens in a CHILD PROCESS, not in the main process!
            # This means that changes made by log_command or function calls made
            # via log_command will not be saved or noted unless they are made part
            # of the return value, or sent earlier via a 'progress' event.
            if directory:
                Util.p_chdir(directory)
            retval.value = Util.log_command(module, filename, argRef)
        
        promise = subprocess_run_p(func)
        
        def then_(exitcode):
            # This happens back in the main process, so we can reintegrate the
            # changes into our data structures if needed.
            
            Debug().debug(f"run_logged_p(): {module} {filename} complete: {exitcode}"),
            if not exitcode == 0:
                Util._setErrorLogfile(module, f"{filename}.log")
            return exitcode
        
        promise = promise.then(then_)
        return promise
    
    @staticmethod
    def split_quoted_on_whitespace(line):
        """
        This subroutine acts like split(' ', $_) except that double-quoted strings
        are not split in the process.
        
        First parameter: String to split on whitespace.
        Return value: A list of the individual words and quoted values in the string.
        The quotes themselves are not returned.
        """
        return shlex.split(line.strip())
    
    @staticmethod
    def pretend_open(path, defaultText: str = ""):
        """
        Function: pretend_open
        
        Opens the given file and returns a filehandle to it if the file actually exists or the script is not in pretend mode.
        If the script is in pretend mode and the file is not already present then an open filehandle to an empty string is returned.
        
        Parameters:
         filename - Path to the file to open.
         default  - String to use if the file doesn't exist in pretend mode
        
        Returns:
         filehandle on success (supports readline() and eof()), can return boolean
         false if there is an error opening an existing file (or if the file doesn't
         exist when not in pretend mode)
        """
        
        if Debug().pretending() and not os.path.exists(path):
            try:
                fh = StringIO(defaultText)
            except IOError:
                return False
        else:
            try:
                fh = open(path, "r")
            except IOError:
                return False
        
        return fh
    
    @staticmethod
    def any(subRef, listRef):
        """
        Returns true if the given function returns true for any item in the given list.
        """
        return any(subRef(item) for item in listRef)
    
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
        Subroutine to delete a directory and all files and subdirectories within.
        Does nothing in pretend mode.  An analog to "rm -rf" from Linux.
        Requires File::Find module.
        
        First parameter: Path to delete
        Returns boolean true on success, boolean false for failure.
        """
        # Pretty user-visible path
        user_path = path
        user_path = re.sub(r"^" + os.environ["HOME"], "~", user_path)
        
        if Debug().pretending():
            Debug().pretend(f"Would have removed all files/folders in {user_path}")
            return True
        
        # Error out because we probably have a logic error even though it would
        # delete just fine.
        if not os.path.isdir(path):
            Debug().error(f"Cannot recursively remove {user_path}, as it is not a directory.")
            return False
        
        try:
            shutil.rmtree(path)
        
        except Exception as e:
            Debug().error(f"Unable to remove directory {user_path}: {e}")
            return False
        return True
    
    @staticmethod
    def get_list_digest(args: list):
        """
        Returns a hash digest of the given options in the list.  The return value is
        base64-encoded at this time.
        
        Note: Don't be dumb and pass data that depends on execution state as the
        returned hash is almost certainly not useful for whatever you're doing with
        it.  (i.e. passing a reference to a list is not helpful, pass the list itself)
        
        Parameters: List of scalar values to hash.
        Return value: base64-encoded hash value.
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
    def safe_lndir_p(from_path: str, to_path: str) -> Promise:
        """
        Subroutine to recursively symlink a directory into another location, in a
        similar fashion to how the XFree/X.org lndir() program does it.  This is
        reimplemented here since some systems lndir doesn't seem to work right.
        
        As a special exception to the GNU GPL, you may use and redistribute this
        function however you would like (i.e. consider it public domain).
        
        Use by passing two I<absolute> paths, the first being where to symlink files
        from, and the second being what directory to symlink them into.
        
         my $promise = safe_lndir_p('/path/to/symlink', '/where/to/put/symlinks');
         $promise->then(sub ($result) {
            say "success" if $result;
         });
        
        All intervening directories will be created as needed.  In addition, you may
        safely run this function again if you only want to catch additional files in
        the source directory.
        
        RETURN VALUE: A promise that resolves to a Boolean true (non-zero) if successful,
        Boolean false if unsuccessful.
        """
        
        if Debug().pretending():
            return Promise.resolve(1)
        
        if not os.path.isabs(from_path) or not os.path.isabs(to_path):
            BuildException.croak_internal("Both paths to safe_lndir_p must be absolute paths!")
        
        # Create destination directory.
        if not Util().super_mkdir(to_path):
            Debug().error(f"Couldn't create directory r[{to_path}]")
            return Promise.resolve(0)
        
        # # Create closure callback subroutine.
        # def wanted(root, dirs, files):
        #
        #     dir = re.sub(from_path, to_path, dir)
        #
        #     # Ignore version-control metadata
        #     if re.search(r"/\.git", dir) :
        #         return
        #
        #     if not Util().super_mkdir(dir):
        #         BuildException.croak_runtime(f"Couldn't create directory {dir}: $!")
        #
        #     # Symlink the file.  Check if it's a regular file because File::Find
        #     # has no qualms about telling you you have a file called "foo/bar"
        #     # before pointing out that it was really a directory.
        #     if os.path.isfile(file) and not os.path.exists(f"{dir}/$_"):
        #         if not os.symlink(file, f"{dir}/$_"):
        #             BuildException.croak_runtime(f"Couldn't create file {dir}/$_: $!")
        
        def subprocess_run_p(target: callable) -> Promise:
            def subprocess_run():
                retval = multiprocessing.Value("i", -1)
                subproc = multiprocessing.Process(target=target, args=(retval,))
                subproc.start()
                # LoggedSubprocess runs subprocess from event loop, while here it is not the case, so we allow blocking join
                subproc.join()
                return retval.value
            
            p = Promise.promisify(subprocess_run)()
            return p
        
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
                Debug().error(f"Unable to symlink {from_path} to {to_path}: {e}")
                retval.value = 0
            retval.value = 1
        
        promise = subprocess_run_p(func)
        return promise
    
    @staticmethod
    def prune_under_directory_p(module, target_dir) -> Promise:
        """
        Subroutine to delete recursively, everything under the given directory, unless
        we're in pretend mode.
        
        Used from L<ksb::BuildSystem> to handle cleaning a build directory.
        
        i.e. the effect is similar to C<rm -r $arg/* $arg/.*>.
        
         # promise resolves to a boolean success flag
         my $promise = prune_under_directory_p($module, '/path/to/clean');
        
        Returns a promise resolving to boolean true on success, boolean false on
        failure.
        """
        
        logpath = module.getLogPath("clean-builddir.log")
        log = None
        try:
            log = open(logpath, "w")
        except IOError as e:
            Debug().error(f"\tError opening logfile {logpath}: r[b[{e}]")
            Debug().error("\tContinuing without logging")
        
        print(f"starting delete o {target_dir}", file=log)
        
        try:
            def subprocess_run_p(target: callable) -> Promise:
                def subprocess_run():
                    retval = multiprocessing.Value("i", -1)
                    subproc = multiprocessing.Process(target=target, args=(retval,))
                    subproc.start()
                    # LoggedSubprocess runs subprocess from event loop, while here it is not the case, so we allow blocking join
                    subproc.join()
                    if subproc.exitcode != 0:  # This is exit code of running subprocess, but not the returned value of the function in subprocess.
                        raise Exception(f"Subprocess failed with exitcode {subproc.exitcode}")
                    return retval.value
                
                p = Promise.promisify(subprocess_run)()
                return p
            
            def func(retval):
                errorRef = {}
                
                with os.scandir(target_dir) as entries:
                    for entry in entries:
                        if entry.is_dir() and not entry.is_symlink():
                            try:
                                shutil.rmtree(entry.path)
                            except OSError as ex:
                                errorRef[entry.path] = ex
                        else:
                            try:
                                os.remove(entry.path)
                            except OSError as ex:
                                errorRef[entry.path] = ex
                
                if errorRef and len(errorRef):
                    for file in errorRef:
                        msg = errorRef[file]
                        if not file:
                            file = "general error"
                        print(f"{file}: error: {msg}", file=log)
                    
                    retval.value = 0
                else:
                    retval.value = 1
                log.close()
                # pl2py: As we are in subprocess, we have "returned" the value via a shared variable.
                # The actual (normal) return value cannot be read by the parent process.
            
            promise = subprocess_run_p(func)
            return promise
        
        except Exception as e:
            Debug().error(f"\tUnable to clean r[{target_dir}]:\n\ty[b[{e}]")
            return Promise.resolve(0)  # resolve, but to an error
    
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
    
    @staticmethod
    def print_filtered_traceback():
        """
        This is same as traceback.print_exc(), but we remove the type_enforced calls
        """
        tb = traceback.format_exc()
        tb_lines = tb.splitlines()
        index = 0
        filtered_tb_lines = []
        while len(tb_lines) > index:
            if "enforcer.py" in tb_lines[index]:
                index += 3
                continue
            filtered_tb_lines.append(tb_lines[index])
            index += 1
        print("\n".join(filtered_tb_lines))
