from __future__ import annotations

from promise import Promise
import multiprocessing
import asyncio

from ..BuildException import BuildException
from ..Debug import Debug
from .Util import Util

"""
=head1 EVENTS

=head2 child_output

This event (see L<Mojo::EventEmitter>, which is a base class of this one) is
called whenever a line of output is produced in the child.  Use the base
class's C<on> method to subscribe to the event.

Any subscriptions to this event must be in place before C<start> is called, as
the child will not install a callback for this unless at least one subscriber
is in place.
"""


class Util_LoggedSubprocess:
    """
    =head1 DESCRIPTION
    
    This is a subclass of L<Mojo::IOLoop::Subprocess> which integrates the functionality
    of that class into kde-builder's logging and module tracking functions.
    
    Like Mojolicious (and unlike most of the rest of kde-builder), this is a
    'fluent' interface due to the number of adjustables vars that must be set,
    including which module is being built, the log file to use, what directory to
    build from, etc.
    
    =head1 SYNOPSIS
    
     my $cmd = ksb::Util::LoggedSubprocess->new
         ->module($module)           # required
         ->log_to($filename)         # required
         ->set_command($argRef)      # required
         ->chdir_to($builddir)       # optional
         ->announcer(sub ($mod) {    # optional
             note("g[$mod] starting update")
         })
         ;
    
     # optional, can have child output forwarded back to parent for processing
     $cmd->on(child_output => sub ($cmd, $line) {
         # called in parent!
         $log_command_callback->($line);
     });
    
     # once ready, call ->start to obtain a Mojo::Promise that
     # can be waited on or chained from, pending the result of
     # computation in a separate child process.
     my $promise = $cmd->start->then(sub ($exitcode) {
         $resultRef = {
             was_successful => $exitcode == 0,
             warnings       => $warnings,
             work_done      => $workDoneFlag,
         };
     });
    
    """

    def __init__(self):
        """
        These attributes are the configurable options that should be set before calling
        C<start> to execute the desired command.  If called without arguments, returns
        the existing value. See L<Mojo::Base> for more information on how attributes
        work.
        """
        # start of attributes
        self._module = None
        self._log_to = None
        self._chdir_to = None
        self._set_command = None
        self._disable_translations = 0
        self._announcer = None
        # end of attributes

        self.subscribers = {}

    def module(self, module):
        """
        Sets the L<ksb::Module> that is being executed against.
        """
        self._module = module
        return self

    def log_to(self, log_to):
        """
        Sets the base filename (without a .log extension) that should receive command output
        in the log directory. This must be set even if child output will not be examined.
        """
        self._log_to = log_to
        return self

    def chdir_to(self, chdir_to):
        """
        Sets the directory to run the command from just before execution in the child
        process. Optional, if not set the directory will not be changed.  The directory is
        never changed for the parent process!
        """
        self._chdir_to = chdir_to
        return self

    def set_command(self, set_command: list[str]):
        """
        Sets the command, and any arguments, to be run, as a reference to a list. E.g.
        
        $cmd->set_command(['make', '-j4']);
        """
        self._set_command = set_command
        return self

    def disable_translations(self, disable_translations: bool | None = None):
        """
        Optional. If set to a true value, causes the child process to attempt to
        disable command localization by setting the "C" locale in the shell
        environment. This can be needed for filtering command output but should be
        avoided if possible otherwise.
        """
        if disable_translations is not None:
            self._disable_translations = disable_translations
        return self

    def announcer(self, announcer):
        """
        Optional. Can be set to a sub that will be called with a single parameter (the
        ksb::Module being built) in the child process just before the build starts.
        
        You can use this to make an announcement just before the command is run since
        there's no way to guarantee the timing in a longer build.
        """
        self._announcer = announcer
        return self

    def start(self) -> Promise:
        """
        Begins the execution, if possible.  Returns a L<Mojo::Promise> that resolves to
        the exit code of the command being run.  0 indicates success, non-zero
        indicates failure.
        
        Exceptions may be thrown, which L<Mojo::Promise> will catch and convert into
        a rejected promise. You must install a L<Mojo::Promise/"catch"> handler
        on the promise to handle this condition.
        """
        from ..Module.Module import Module
        module = self._module
        Util.assert_isa(module, Module)
        if not (filename := self._log_to):
            BuildException.croak_internal("Need to log somewhere")
        if not (argRef := self._set_command):
            BuildException.croak_internal("No command to run!")
        if not isinstance(argRef, list):
            BuildException.croak_internal("Command list needs to be a listref!")

        dir_to_run_from = self._chdir_to
        announceSub = self._announcer
        command = argRef

        if Debug().pretending():
            Debug().pretend(f"\tWould have run ('g[" + "]', 'g[".join(command) + "]')")
            a = Promise.resolve(0)
            return a

        # Install callback handler to feed child output to parent if the parent has
        # a callback to filter through it.
        needsCallback = self.has_subscribers("child_output")

        if needsCallback:
            def func(data):
                # pl2py: in perl they sent "child_data" here, we instead send just the line
                line = data
                if line:
                    self.subscribers["child_output"](line)  # invoke the child_output subscriber
                    return

                if isinstance(data, dict):
                    raise Exception("unimplemented " + ", ".join(data.keys()))

                raise Exception(f"unimplemented {data}")

            # pl2py: we will run "on progress handler" later below, because we need it to be run simultaneously with the subprocess

        succeeded = 0

        def subprocess_run_p(target: callable) -> Promise:
            async def subprocess_run():
                retval = multiprocessing.Value("i", -1)
                subproc = multiprocessing.Process(target=target, args=(retval,))
                subproc.start()
                while subproc.is_alive():
                    await asyncio.sleep(1)
                subproc.join()
                return retval.value

            p = Promise.promisify(subprocess_run)()
            return p

        lines_queue = multiprocessing.Queue()

        def _begin(retval):
            # in a child process
            if dir_to_run_from:
                Util.p_chdir(dir_to_run_from)

            if self.disable_translations():
                Util.disable_locale_message_translation()

            callback = None
            if needsCallback:
                def clbk(line):
                    if line is None:
                        return
                    # self._sendToParent(subp, line)
                    self._sendToParent(lines_queue, line.split("\n"))

                callback = clbk

            if announceSub:
                announceSub(module)

            result = Util.run_logged_command(module, filename, callback, command)
            Debug().whisper(f"{command[0]} complete, result {result}")
            retval.value = result

        promise = Promise()  # Just use Promise() here, to let PyCharm's inspector understand the type of "promise" variable.

        async def on_progress_handler(subp_finished: multiprocessing.Event):
            if needsCallback:
                nonlocal lines_queue
                while not subp_finished.is_set() or not lines_queue.empty():
                    while not lines_queue.empty():
                        line = lines_queue.get()
                        func(line)
                    await asyncio.sleep(1)
            else:
                return

        async def promise_waiter(event):
            nonlocal promise
            promise = subprocess_run_p(_begin)
            while promise.is_pending:  # because Promise.wait(promise) is not awaitable itself, we wait it in such way.
                await asyncio.sleep(1)
            event.set()

        # pl2py: Now we need to run the on_progress_handler and the subprocess at the same time.
        # so we create an async loop for this.
        loop = asyncio.get_event_loop()
        subproc_finished_event = asyncio.Event()
        task1 = loop.create_task(on_progress_handler(subproc_finished_event))
        task2 = loop.create_task(promise_waiter(subproc_finished_event))
        loop.run_until_complete(asyncio.gather(task1, task2))

        # Now we have our promise finished, and we can continue

        def _set_succeeded(exitcode):
            nonlocal succeeded
            succeeded = exitcode == 0
            return exitcode  # Don't change result, just pass it on

        promise = promise.then(_set_succeeded)

        def _finally():
            # If an exception was thrown or we didn't succeed, set error log
            if not succeeded:
                Util._setErrorLogfile(module, f"{filename}.log")

        Promise.wait(promise)
        _finally()
        return promise

    @staticmethod
    def _sendToParent(queue, data: list):
        """
        Sends the given data to the parent process.  Our calling code and this
        package must share the same single channel (over the 'progress' event
        supported by Mojolicious).  Although we only support handling for the calling
        code (to send line-by-line output back to the parent), to support future
        expansion we send a hashref which we can add different keys to if we need to
        support other use cases.
        """

        # pl2py: In perl they sent progress event here with {"child_data": data}. We will not send progress event, instead the on_progress_handler will check for entries in queue in loop
        for line in data:
            if line:
                queue.put(line)

    def on(self, arg: dict):
        key = list(arg.keys())[0]
        val = arg[key]
        self.subscribers[key] = val

    def has_subscribers(self, arg):
        return arg in self.subscribers.keys()
