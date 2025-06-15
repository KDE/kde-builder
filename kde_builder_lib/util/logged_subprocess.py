# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import asyncio
import sys
from typing import Callable

from .util import Util
from ..kb_exception import ProgramError
from ..debug import Debug
from ..debug import KBLogger

if sys.platform == "darwin":
    import multiprocess as multiprocessing
else:
    import multiprocessing

logger_logged_cmd = KBLogger.getLogger("logged-command")

"""
child_output event is called whenever a line of output is produced in the child.
Use the ``on`` method to subscribe to the event.

Any subscriptions to this event must be in place before ``start`` is called, as
the child will not install a callback for this unless at least one subscriber
is in place.
"""


class UtilLoggedSubprocess:
    """
    Integrate the functionality subprocess into kde-builder's logging and module tracking functions.

    Unlike most of the rest of kde-builder, this is a "fluent" interface due to the number of adjustables vars that must be set,
    including which module is being built, the log file to use, what directory to build from, etc.

    Examples:
    ::

        def announ(mod):
             logger.note(f"g[{mod}] starting update")

        cmd = UtilLoggedSubprocess()
         .module(module)           # required
         .log_to(filename)         # required
         .set_command(arg_ref)      # required
         .chdir_to(builddir)       # optional
         .announcer(announ)  # optional


        def child_outp(cmd, line):
            # called in parent!
            log_command_callback(line)

        # optional, can have child output forwarded back to parent for processing
        cmd.on(child_output: child_outp)

        def func(exitcode):
            resultRef = {
             "was_successful": exitcode == 0,
             "warnings"      : warnings,
             "work_done"     : workDoneFlag,
            }

        # once ready, call .start() to obtain a result of
        # computation in a separate child process.
        result = cmd.start()
        func(result)
    """

    def __init__(self):
        """
        Initialize UtilLoggedSubprocess.

        These attributes are the configurable options that should be set before calling ``start`` to execute the desired command.

        If called without arguments, returns the existing value.
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
        Set the ``Module`` that is being executed against.
        """
        self._module = module
        return self

    def log_to(self, log_to):
        """
        Set the base filename (without a .log extension) that should receive command output in the log directory.

        This must be set even if child output will not be examined.
        """
        self._log_to = log_to
        return self

    def chdir_to(self, chdir_to):
        """
        Set the directory to run the command from just before execution in the child process.

        Optional, if not set the directory will not be changed. The directory is never changed for the parent process!
        """
        self._chdir_to = chdir_to
        return self

    def set_command(self, set_command: list[str]):
        """
        Set the command, and any arguments, to be run, as a reference to a list.

        E.g.
            cmd.set_command(["make", "-j4"])
        """
        self._set_command = set_command
        return self

    def disable_translations(self, disable_translations: bool | None = None):
        """
        Make the child process to attempt to disable command localization by setting the "C" locale in the shell environment.

        Optional.
        This can be needed for filtering command output but should be avoided if possible otherwise.
        """
        if disable_translations is not None:
            self._disable_translations = disable_translations
        return self

    def announcer(self, announcer):
        """
        Set a function that will be called with a single parameter (the ``Module`` being built) in the child process just before the build starts.

        Optional.
        You can use this to make an announcement just before the command is run since
        there's no way to guarantee the timing in a longer build.
        """
        self._announcer = announcer
        return self

    def start(self) -> int:
        """
        Begins the execution, if possible.

        Returns the exit code of the command being run. 0 indicates success, non-zero
        indicates failure.

        Exceptions may be thrown.
        """
        from ..module.module import Module
        module = self._module
        Util.assert_isa(module, Module)
        if not (filename := self._log_to):
            raise ProgramError("Need to log somewhere")
        if not (args := self._set_command):
            raise ProgramError("No command to run!")
        if not isinstance(args, list):
            raise ProgramError("Command list needs to be a listref!")

        dir_to_run_from = self._chdir_to
        announce_sub = self._announcer
        command = args

        if Debug().pretending():
            logger_logged_cmd.debug("\tWould have run] ('g[" + "]', 'g[".join(command) + "]')")
            return 0

        # Install callback handler to feed child output to parent if the parent has
        # a callback to filter through it.
        needs_callback = self.has_subscribers("child_output")

        if needs_callback:
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

        async def subprocess_run(target: Callable) -> int:
            retval = multiprocessing.Value("i", -1)
            subproc = multiprocessing.Process(target=target, args=(retval,))
            subproc.start()
            while subproc.is_alive():
                await asyncio.sleep(1)
            subproc.join()
            return retval.value

        lines_queue = multiprocessing.Queue()

        def _begin(retval):
            # in a child process
            if dir_to_run_from:
                Util.p_chdir(dir_to_run_from)

            if self.disable_translations():
                Util.disable_locale_message_translation()

            callback = None
            if needs_callback:
                def clbk(line):
                    if line is None:
                        return
                    self._send_to_parent(lines_queue, line.split("\n"))

                callback = clbk

            if announce_sub:
                announce_sub(module)

            result = Util.run_logged(module, filename, None, command, callback)
            retval.value = result

        exitcode = -1

        async def on_progress_handler(subp_finished: multiprocessing.Event):
            if needs_callback:
                nonlocal lines_queue
                while not subp_finished.is_set() or not lines_queue.empty():
                    while not lines_queue.empty():
                        line = lines_queue.get()
                        func(line)
                    await asyncio.sleep(1)
            else:
                return

        async def subprocess_waiter(event):
            nonlocal exitcode
            exitcode = await subprocess_run(_begin)
            event.set()

        # pl2py: Now we need to run the on_progress_handler and the subprocess at the same time.
        # so we create an async loop for this.
        loop = asyncio.get_event_loop()
        subproc_finished_event = asyncio.Event()
        task1 = loop.create_task(on_progress_handler(subproc_finished_event))
        task2 = loop.create_task(subprocess_waiter(subproc_finished_event))
        loop.run_until_complete(asyncio.gather(task1, task2))

        # Now we have our subprocess finished, and we can continue

        succeeded = exitcode == 0

        # If an exception was thrown or we didn't succeed, set error log
        if not succeeded:
            module.set_error_logfile(f"{filename}.log")

        return exitcode

    @staticmethod
    def _send_to_parent(queue, data: list[str]):
        """
        Send the given data to the parent process.

        Our calling code and this
        class must share the same single channel (over the "progress" event).
        Although we only support handling for the calling
        code (to send line-by-line output back to the parent), to support future
        expansion we send a dict which we can add different keys to if we need to
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
