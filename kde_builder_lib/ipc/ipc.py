# SPDX-FileCopyrightText: 2012, 2013, 2016, 2020 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from enum import IntEnum
import re
import struct
from typing import Callable
from typing import NoReturn
from typing import TYPE_CHECKING

from ..kb_exception import KBRuntimeError
from ..kb_exception import ProgramError
from ..debug import KBLogger

if TYPE_CHECKING:
    from ..module.module import Module

logger_ipc = KBLogger.getLogger("ipc")


class IPC:
    """
    Handles the asynchronous communications needed to perform update and build processes at the same time.

    This can be thought of as a partially-abstract
    class, really you should use IPCNull (which is fully synchronous) or
    IPCPipe, which both fall back to common methods implemented here.
    """

    # IPC message types

    MODULE_SUCCESS = 1  # Used for a successful src checkout
    MODULE_FAILURE = 2  # Used for a failed src checkout
    MODULE_SKIPPED = 3  # Used for a skipped src checkout (i.e. build anyways)
    MODULE_UPTODATE = 4  # Used to skip building a module when had no code updates

    # One of these messages should be the first message placed on the queue.
    ALL_SKIPPED = 5  # Used to indicate a skipped update process (i.e. build anyways)
    ALL_FAILURE = 6  # Used to indicate a major update failure (don't build)
    ALL_UPDATING = 7  # Informational message, feel free to start the build.

    MODULE_LOGMSG = 9  # Tagged message should be put to TTY for module.
    MODULE_PERSIST_OPT = 10  # Change to a persistent module option

    ALL_DONE = 11  # Affirmatively flags that all updates are done

    MODULE_POSTBUILD_MSG = 12  # A message to print after all work done

    def __init__(self):
        self.no_update: bool = False
        self.updated: dict[str, str] = {}
        self.logged_module: str = "global"
        self.messages: dict[str, list[str]] = {}  # Holds log output from update process
        self.postbuild_msg: dict[str, list[str]] = {}  # Like above but for post-build msgs
        self.why_refresh: dict[str, str] = {}  # If module should build despite not being updated, why?
        self.updates_done: bool = False
        self.opt_update_handler: Callable | None = None  # Callback for persistent option changes

    def notify_persistent_option_change(self, module_name: str, opt_name: str, opt_value: str) -> None:
        """
        Send a message to the main/build process that a persistent option for the given module name must be changed.

        For use by processes that do not control the persistent option store upon shutdown.
        """
        self.send_ipc_message(IPC.MODULE_PERSIST_OPT, f"{module_name},{opt_name},{opt_value}")

    def notify_new_post_build_message(self, module_name: str, msg: str) -> None:
        """
        Send a message to the main/build process that a given message should be shown to the user at the end of the build.
        """
        self.send_ipc_message(IPC.MODULE_POSTBUILD_MSG, f"{module_name},{msg}")

    def notify_update_success(self, module: str, msg: str) -> None:
        self.send_ipc_message(IPC.MODULE_SUCCESS, f"{module},{msg}")

    def set_logged_module(self, module_name: str) -> None:
        # Sets which module messages stored by send_log_message are supposed to be
        # associated with.
        self.logged_module = module_name

    def send_log_message(self, logger_name: str, message_level: str, msg: str) -> None:
        """
        Send a message to be logged by the process holding the TTY.

        The logged message is associated with the module set by set_logged_module.
        """
        logged_module = self.logged_module
        self.send_ipc_message(IPC.MODULE_LOGMSG, f"{logged_module},{logger_name},{message_level},{msg}")

    @staticmethod
    def _print_logged_message(combined_msg: str) -> None:
        """
        Print the given message out (adjusting to have proper whitespace if needed). For use with the log-message forwarding facility.
        """
        logger_name, message_level, msg = combined_msg.split(",", maxsplit=2)
        if not re.match(r"^\s+", msg):
            msg = f"\t{msg}"  # Automatically adds tabulation if message misses it. Note that this is in main process (kde-builder-build).
        KBLogger.print_clr(logger_name, message_level, msg)

    def _update_seen_modules_from_message(self, ipc_type: int, buffer: str) -> str:
        """
        Update seen modules.

        Called any time we're waiting for an IPC message from a sub process.

        This can occur during a module build (waiting for messages from update process) or
        while we're near the end of the script execution. There is no way to tell
        which module we'll be about to receive messages for from the other end.
        """
        updated = self.updated
        messages = self.messages
        message = ""

        if not ipc_type:
            raise KBRuntimeError("IPC failure: no IPC mechanism defined")

        if ipc_type == IPC.MODULE_SUCCESS:
            ipc_module_name, msg = buffer.split(",")
            message = msg
            updated[ipc_module_name] = "success"
        elif ipc_type == IPC.MODULE_SKIPPED:
            # The difference between success here and "skipped" below
            # is that success means we should build even though we
            # didn't perform an update, while "skipped" means the
            # *build* should be skipped even though there was no
            # failure.
            message = "skipped"
            updated[buffer] = "success"
        elif ipc_type == IPC.MODULE_FAILURE:
            message = "update failed"
            updated[buffer] = "failed"
        elif ipc_type == IPC.MODULE_UPTODATE:
            # Although the module source hasn't changed, the user might be forcing a
            # rebuild, so our message should reflect what's actually going to happen.
            message = "no commits pulled"
            ipc_module_name, refresh_reason = buffer.split(",")

            if refresh_reason:
                updated[ipc_module_name] = "success"
                self.why_refresh[ipc_module_name] = refresh_reason
            else:
                updated[ipc_module_name] = "skipped"
        elif ipc_type == IPC.MODULE_PERSIST_OPT:
            ipc_module_name, opt_name, value = buffer.split(",")
            if self.opt_update_handler:
                # Call into callback to update persistent options
                self.opt_update_handler(ipc_module_name, opt_name, value)
        elif ipc_type == IPC.MODULE_LOGMSG:
            ipc_module_name, log_message = buffer.split(",", maxsplit=1)

            # Save it for later if we can't print it yet.
            if ipc_module_name not in messages:
                messages[ipc_module_name] = []
            messages[ipc_module_name].append(log_message)
        elif ipc_type == IPC.ALL_DONE:
            self.updates_done = True
        elif ipc_type == IPC.MODULE_POSTBUILD_MSG:
            ipc_module_name, post_build_msg = buffer.split(",", maxsplit=1)

            if ipc_module_name not in self.postbuild_msg:
                self.postbuild_msg[ipc_module_name] = []
            self.postbuild_msg[ipc_module_name].append(post_build_msg)
        else:
            raise ProgramError(f"Unhandled IPC type: {ipc_type}")
        return message

    def set_persistent_option_handler(self, handler: Callable) -> None:
        """
        Assign a callback / function to use for updating persistent options based on IPC update messages.

        The function should itself take a key and value pair.
        """
        self.opt_update_handler = handler

    def refresh_reason_for(self, module: str) -> str:
        """
        Return a text reason to refresh a non-updated module, or an empty string if the module has been updated or has not yet been seen.
        """
        return self.why_refresh.get(module, "")

    def wait_for_end(self) -> None:
        self.wait_for_stream_start()
        while not self.no_update and not self.updates_done:
            ipc_type, buffer = self.receive_ipc_message()
            ipc_type = MsgType(ipc_type)  # pl2py: this was not in kdesrc-build
            # We ignore the return value in favor of ->{updates_done}
            self._update_seen_modules_from_message(ipc_type, buffer)

    def wait_for_module(self, module: Module) -> tuple[str, str]:
        """
        Wait for an update for a module with the given name.

        Returns:
            Tuple containing whether the module was successfully updated,
            and any specific string message (e.g. for module update success you get
            number of pulled commits).

        Raises:
            Exception: For an IPC failure or if the module should not be built.
        """
        module_name = module.name
        updated = self.updated

        # Wait for the initial phase to complete, if it hasn't.
        self.wait_for_stream_start()

        # No update? Just mark as successful
        if self.no_update or not module.phases.has("update"):
            updated[module_name] = "success"
            return "success", "Skipped"

        message = ""
        messages = self.messages
        while updated.get(module_name) is None and not self.updates_done:
            ipc_type, buffer = self.receive_ipc_message()
            ipc_type = MsgType(ipc_type)  # pl2py: this was not in kdesrc-build
            message = self._update_seen_modules_from_message(ipc_type, buffer)

            # If we have "global" messages they are probably for the first module and
            # include standard setup messages, etc. Print first and then print module's
            # messages.
            for item in ["global", module_name]:
                if item in messages:  # pl2py: we specifically check if there is such a key
                    for msg in messages[item]:
                        self._print_logged_message(msg)
                    del messages[item]

        # We won't print post-build messages now but we need to save them for when
        # they can be printed.
        if module_name in self.postbuild_msg:
            for msg in self.postbuild_msg[module_name]:
                module.add_post_build_message(msg)
            del self.postbuild_msg[module_name]
        return updated[module_name], message

    def output_pending_logged_messages(self) -> None:
        """
        Show any available messages near the end of the script run.

        Just in case we somehow have messages to display after all modules are processed, we have this function.
        """
        messages = self.messages

        for module, log_messages in messages.items():
            non_empty_messages = [logMessage for logMessage in log_messages if logMessage.split(",", maxsplit=2)[2]]
            if non_empty_messages:
                logger_ipc.debug(f"\nUnhandled messages for project {module}:")
                for combined_msg in non_empty_messages:
                    logger_name, message_level, msg = combined_msg.split(",", maxsplit=2)
                    if not re.match(r"^\s+", msg):
                        msg = f"\t{msg}"  # Automatically adds tabulation if message misses it.
                    KBLogger.print_clr(logger_name, message_level, msg)
        self.messages.clear()

    def forget_module(self, module: Module) -> None:
        """
        Flag the given module as something that can be ignored from now on.

        For use after the module has been waited on.
        """
        modulename = module.name
        del self.updated[modulename]

    def unacknowledged_modules(self) -> dict[str, str]:
        """
        Return a dict mapping module *names* to update statuses, for modules that have not already been marked as ignorable using forget_module().
        """
        return self.updated

    def wait_for_stream_start(self) -> None:
        """
        Wait on the IPC connection until one of the ALL_* IPC codes is returned.

        If IPC.ALL_SKIPPED is returned then the "no_update" entry will be set in self to flag that you shouldn't wait.
        If IPC.ALL_FAILURE is returned then an exception will be thrown due to the fatal error.
        This method can be called multiple times, but only the first time will result in a wait.
        """
        if not hasattr(IPC, "waited"):
            IPC.waited = 0

        if IPC.waited:
            return

        ipc_type = 0
        IPC.waited = 1

        while ipc_type != IPC.ALL_UPDATING:
            ipc_type, buffer = self.receive_ipc_message()
            ipc_type = MsgType(ipc_type)  # pl2py: this was not in kdesrc-build

            if not ipc_type:
                raise ProgramError("IPC Failure waiting for stream start :(")
            if ipc_type == IPC.ALL_FAILURE:
                raise KBRuntimeError(f"Unable to perform source update for any project:\n\t{buffer}")
            elif ipc_type == IPC.ALL_SKIPPED:
                self.no_update = True
                self.updates_done = True
            elif ipc_type == IPC.MODULE_LOGMSG:
                ipc_module_name, log_message = buffer.split(",", maxsplit=1)
                if ipc_module_name not in self.messages:
                    self.messages[ipc_module_name] = []
                self.messages[ipc_module_name].append(log_message)
            elif ipc_type != IPC.ALL_UPDATING:
                raise KBRuntimeError(f"IPC failure while expecting an update status: Incorrect type: {ipc_type}")

    def send_ipc_message(self, ipc_type: int, msg: str) -> bool:
        """
        Send an IPC message along with some IPC type information.

        Args:
            ipc_type: The IPC type to send.
            msg: The actual message.
        All remaining parameters are sent to the object's send_message()
         procedure.
        """
        encoded_msg: bytes = struct.pack("!l", ipc_type) + msg.encode("utf-8")
        return self.send_message(encoded_msg)

    @staticmethod
    def unpack_msg(msg: bytes) -> tuple[int, str]:
        """
        Unpack a message.

        Args:
            msg: The message.

        Returns:
             The IPC message type and message content.
        """
        return_type, out_buffer = struct.unpack("!l", msg[:4])[0], msg[4:].decode("utf-8")
        return return_type, out_buffer

    def receive_ipc_message(self) -> tuple[int, str]:
        """
        Receive an IPC message and decodes it into the message and its associated type information.

        Returns:
             The tuple with IPC type and message content, or tuple with 0 and empty string on failure.
        """
        if self.updates_done:
            raise ProgramError("Trying to pull message from closed IPC channel!")
        msg: bytes = self.receive_message()
        return self.unpack_msg(msg) if msg else (0, "")

    # These must be reimplemented.  They must be able to handle scalars without
    # any extra frills.

    def send_message(self, msg: bytes) -> NoReturn:
        # send_message should accept one parameter (the message to send) and return
        # true on success, or false on failure.  $! should hold the error information
        # if false is returned.
        raise ProgramError("Unimplemented.")

    def receive_message(self) -> NoReturn:
        """
        Return a message received from the other side, or None for EOF or error.
        """
        raise ProgramError("Unimplemented.")

    @staticmethod
    def supports_concurrency() -> bool:
        return False

    def close(self) -> None:
        pass


class MsgType(IntEnum):
    """
    Convenience class to represent message type as human-readable name instead of just int number.

    pl2py: this was not in kdesrc-build, I (Andrew Shark) made this just for convenience while debugging.
    Note that IntEnum can be compared with int as normal.
    """

    MODULE_SUCCESS = IPC.MODULE_SUCCESS
    MODULE_FAILURE = IPC.MODULE_FAILURE
    MODULE_SKIPPED = IPC.MODULE_SKIPPED
    MODULE_UPTODATE = IPC.MODULE_UPTODATE
    ALL_SKIPPED = IPC.ALL_SKIPPED
    ALL_FAILURE = IPC.ALL_FAILURE
    ALL_UPDATING = IPC.ALL_UPDATING
    MODULE_LOGMSG = IPC.MODULE_LOGMSG
    MODULE_PERSIST_OPT = IPC.MODULE_PERSIST_OPT
    ALL_DONE = IPC.ALL_DONE
    MODULE_POSTBUILD_MSG = IPC.MODULE_POSTBUILD_MSG
