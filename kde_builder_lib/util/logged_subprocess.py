# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import asyncio
import queue
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

# This needs to be a toplevel function in order to be picklable; being picklable is mandatory for
# any arguments - including the "target" argument - to multiprocessing.Process()
def subprocess_run_func(ulsSelf: UtilLoggedSubprocess, filename, command, retval):
    # in a child process
    if ulsSelf._chdir_to:
        Util.p_chdir(ulsSelf._chdir_to)

    if ulsSelf.disable_translations():
        Util.disable_locale_message_translation()

    callback = None
    if ulsSelf.child_output_handler:
        def callback_func(lines):
            if lines is None:
                return
            for line in lines.split("\n"):
                if line:
                    lines_queue.put(line)
        callback = callback_func

    if ulsSelf._announcer:
        ulsSelf._announcer(ulsSelf.module)

    result = Util.run_logged(ulsSelf._module, filename, None, command, callback)
    retval.value = result


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


        def on_child_output(line):
            ...

        # optional, can have child output forwarded back to parent for processing
        cmd.child_output_handler = on_child_output

        def func(exitcode):
            resultRef = {
             "was_successful": exitcode == 0,
             "warnings"      : warnings,
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

        self.child_output_handler: None | Callable = None

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
        Util.assert_isa(self._module, Module)
        if not (filename := self._log_to):
            raise ProgramError("Need to log somewhere")
        if not (args := self._set_command):
            raise ProgramError("No command to run!")
        if not isinstance(args, list):
            raise ProgramError("Command list needs to be a listref!")

        command = args

        if Debug().pretending():
            logger_logged_cmd.debug("\tWould have run] ('g[" + "]', 'g[".join(command) + "]')")
            return 0

        succeeded = 0
        exitcode = -1
        lines_queue = multiprocessing.Queue()

        async def subprocess_run():
            nonlocal exitcode

            multiprocessing.set_start_method("forkserver", True)
            retval = multiprocessing.Value("i", -1)
            subproc = multiprocessing.Process(target=subprocess_run_func,
                                              args=(self, filename, command, retval))
            subproc.start()
            await asyncio.get_running_loop().run_in_executor(None, subproc.join)

            exitcode = retval.value
            lines_queue.put(None) # end of data token

        async def subprocess_progress_handler():
            nonlocal lines_queue
            while True:
                # multiprocessing.Queue is multi-process, but not awaitable. Need to shunt it off to
                # a worker thread to make it awaitable.
                # The get() blocks process termination if the queue isn't fed (like during process
                # termination...), so let it time out occasionally to relinquish control.
                try:
                    line = await asyncio.get_running_loop().run_in_executor(None, lines_queue.get, True, 0.3)
                except queue.Empty:
                    continue
                if line is None: # end of data token
                    return
                self.child_output_handler(line)

        # Now we need to run the subprocess_progress_handler() and the subprocess at the same time.
        # so we create an async loop for this.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task1 = loop.create_task(subprocess_progress_handler())
        task2 = loop.create_task(subprocess_run())
        loop.run_until_complete(asyncio.gather(task1, task2))
        loop.close()

        # Now we have our subprocess finished, and we can continue

        succeeded = exitcode == 0

        # If an exception was thrown or we didn't succeed, set error log
        if not succeeded:
            self._module.set_error_logfile(f"{filename}.log")

        return exitcode
