from __future__ import annotations

import re
import struct
from typing import NoReturn, Callable, TYPE_CHECKING
from enum import IntEnum
from ..BuildException import BuildException
from ..Debug import Debug, kbLogger

if TYPE_CHECKING:
    from ..Module.Module import Module

logger_ipc = kbLogger.getLogger("ipc")


class IPC:
    """
    Handles the asynchronous communications needed to perform update and build
    processes at the same time. This can be thought of as a partially-abstract
    class, really you should use IPC::Null (which is fully synchronous) or
    IPC::Pipe, which both fall back to common methods implemented here.
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

    MODULE_CONFLICT = 8  # Used to indicate specifically that a source conflict has occurred.
    MODULE_LOGMSG = 9  # Tagged message should be put to TTY for module.
    MODULE_PERSIST_OPT = 10  # Change to a persistent module option

    ALL_DONE = 11  # Affirmatively flags that all updates are done

    MODULE_POSTBUILD_MSG = 12  # A message to print after all work done

    def __init__(self):
        self.no_update = 0
        self.updated = {}
        self.logged_module: str = "global"
        self.messages = {}  # Holds log output from update process
        self.postbuild_msg = {}  # Like above but for post-build msgs
        self.why_refresh = {}  # If module should build despite not being updated, why?
        self.updates_done = 0
        self.opt_update_handler = None  # Callback for persistent option changes

    def notifyPersistentOptionChange(self, moduleName: str, optName: str, optValue: str) -> None:
        """
        Sends a message to the main/build process that a persistent option for the
        given module name must be changed. For use by processes that do not control
        the persistent option store upon shutdown.
        """
        self.sendIPCMessage(IPC.MODULE_PERSIST_OPT, f"{moduleName},{optName},{optValue}")

    def notifyNewPostBuildMessage(self, moduleName: str, msg) -> None:
        """
        Sends a message to the main/build process that a given message should be
        shown to the user at the end of the build.
        """
        self.sendIPCMessage(IPC.MODULE_POSTBUILD_MSG, f"{moduleName},{msg}")

    def notifyUpdateSuccess(self, module: str, msg: str) -> None:
        self.sendIPCMessage(IPC.MODULE_SUCCESS, f"{module},{msg}")

    def setLoggedModule(self, moduleName: str) -> None:
        # Sets which module messages stored by sendLogMessage are supposed to be
        # associated with.
        self.logged_module = moduleName

    def sendLogMessage(self, logger_name: str, message_level: str, msg: str) -> None:
        """
        Sends a message to be logged by the process holding the TTY.
        The logged message is associated with the module set by setLoggedModule.
        """
        loggedModule = self.logged_module
        self.sendIPCMessage(IPC.MODULE_LOGMSG, f"{loggedModule},{logger_name},{message_level},{msg}")

    @staticmethod
    def _printLoggedMessage(combined_msg: str) -> None:
        """
        Prints the given message out (adjusting to have proper whitespace
        if needed). For use with the log-message forwarding facility.
        """
        logger_name, message_level, msg = combined_msg.split(",", maxsplit=2)
        if not re.match(r"^\s+", msg):
            msg = f"\t{msg}"
        kbLogger.print_clr(logger_name, message_level, msg)

    def _updateSeenModulesFromMessage(self, ipcType, buffer) -> str | None:
        """
        Called any time we're waiting for an IPC message from a sub process. This can
        occur during a module build (waiting for messages from update process) or
        while we're near the end of the script execution. There is no way to tell
        which module we'll be about to receive messages for from the other end.
        """
        updated = self.updated
        messagesRef = self.messages
        message = None

        if not ipcType:
            BuildException.croak_runtime("IPC failure: no IPC mechanism defined")

        if ipcType == IPC.MODULE_SUCCESS:
            ipcModuleName, msg = buffer.split(",")
            message = msg
            updated[ipcModuleName] = "success"
        elif ipcType == IPC.MODULE_SKIPPED:
            # The difference between success here and 'skipped' below
            # is that success means we should build even though we
            # didn't perform an update, while 'skipped' means the
            # *build* should be skipped even though there was no
            # failure.
            message = "skipped"
            updated[buffer] = "success"
        elif ipcType == IPC.MODULE_CONFLICT:
            message = "conflicts present"
            updated[buffer] = "failed"
        elif ipcType == IPC.MODULE_FAILURE:
            message = "update failed"
            updated[buffer] = "failed"
        elif ipcType == IPC.MODULE_UPTODATE:
            # Although the module source hasn't changed, the user might be forcing a
            # rebuild, so our message should reflect what's actually going to happen.
            message = "no files affected"
            ipcModuleName, refreshReason = buffer.split(",")

            if refreshReason:
                updated[ipcModuleName] = "success"
                self.why_refresh[ipcModuleName] = refreshReason
            else:
                updated[ipcModuleName] = "skipped"
        elif ipcType == IPC.MODULE_PERSIST_OPT:
            ipcModuleName, optName, value = buffer.split(",")
            if self.opt_update_handler:
                # Call into callback to update persistent options
                self.opt_update_handler(ipcModuleName, optName, value)
        elif ipcType == IPC.MODULE_LOGMSG:
            ipcModuleName, logMessage = buffer.split(",", maxsplit=1)

            # Save it for later if we can't print it yet.
            if ipcModuleName not in messagesRef:
                messagesRef[ipcModuleName] = []
            messagesRef[ipcModuleName].append(logMessage)
        elif ipcType == IPC.ALL_DONE:
            self.updates_done = 1
        elif ipcType == IPC.MODULE_POSTBUILD_MSG:
            ipcModuleName, postBuildMsg = buffer.split(",", maxsplit=1)

            if ipcModuleName not in self.postbuild_msg:
                self.postbuild_msg[ipcModuleName] = []
            self.postbuild_msg[ipcModuleName].append(postBuildMsg)
        else:
            BuildException.croak_internal(f"Unhandled IPC type: {ipcType}")
        return message

    def setPersistentOptionHandler(self, handler: Callable) -> None:
        """
        Used to assign a callback / subroutine to use for updating persistent
        options based on IPC update messages.  The sub should itself take a
        key and value pair.
        """
        self.opt_update_handler = handler

    def refreshReasonFor(self, module: str) -> str:
        """
        Returns a text reason to refresh a non-updated module, or an empty string if
        the module has been updated or has not yet been seen.
        """
        return self.why_refresh.get(module, "")

    def waitForEnd(self) -> None:
        self.waitForStreamStart()
        while not self.no_update and not self.updates_done:
            ipcType, buffer = self.receiveIPCMessage()
            ipcType = MsgType(ipcType)  # pl2py: this was not in kdesrc-build
            # We ignore the return value in favor of ->{updates_done}
            self._updateSeenModulesFromMessage(ipcType, buffer)

    def waitForModule(self, module: Module) -> tuple:
        """
        Waits for an update for a module with the given name.
        Returns a list containing whether the module was successfully updated,
        and any specific string message (e.g. for module update success you get
        number of files affected)
        Will throw an exception for an IPC failure or if the module should not be
        built.
        """
        moduleName = module.name
        updated = self.updated

        # Wait for the initial phase to complete, if it hasn't.
        self.waitForStreamStart()

        # No update? Just mark as successful
        if self.no_update or not module.phases.has("update"):
            updated[moduleName] = "success"
            return "success", "Skipped"

        message = None
        while updated.get(moduleName) is None and not self.updates_done:
            ipcType, buffer = self.receiveIPCMessage()
            ipcType = MsgType(ipcType)  # pl2py: this was not in kdesrc-build
            message = self._updateSeenModulesFromMessage(ipcType, buffer)

            # If we have 'global' messages they are probably for the first module and
            # include standard setup messages, etc. Print first and then print module's
            # messages.
            messagesRef = self.messages
            for item in ["global", moduleName]:
                if item in messagesRef:  # pl2py: we specifically check if there is such a key
                    for msg in messagesRef[item]:
                        self._printLoggedMessage(msg)
                    del messagesRef[item]

        # We won't print post-build messages now but we need to save them for when
        # they can be printed.
        if moduleName in self.postbuild_msg:
            for msg in self.postbuild_msg[moduleName]:
                module.addPostBuildMessage(msg)
            del self.postbuild_msg[moduleName]
        return updated[moduleName], message

    def outputPendingLoggedMessages(self) -> None:
        """
        Just in case we somehow have messages to display after all modules are
        processed, we have this function to show any available messages near the end
        of the script run.
        """
        messages = self.messages

        for module, logMessages in messages.items():
            nonEmptyMessages = [logMessage for logMessage in logMessages if logMessage.split(",", maxsplit=2)[2]]
            if nonEmptyMessages:
                logger_ipc.debug(f"\nUnhandled messages for module {module}:")
                for combined_msg in nonEmptyMessages:
                    logger_name, message_level, msg = combined_msg.split(",", maxsplit=2)
                    if not re.match(r"^\s+", msg):
                        msg = f"\t{msg}"
                    kbLogger.print_clr(logger_name, message_level, msg)
        self.messages = {}

    def forgetModule(self, module: Module) -> None:
        """
        Flags the given module as something that can be ignored from now on.  For use
        after the module has been waited on
        """
        modulename = module.name
        del self.updated[modulename]

    def unacknowledgedModules(self) -> dict:
        """
        Returns a hashref mapping module *names* to update statuses, for modules that
        have not already been marked as ignorable using forgetModule()
        """
        return self.updated

    def waitForStreamStart(self) -> None:
        """
        Waits on the IPC connection until one of the ALL_* IPC codes is returned.
        If ksb::IPC::ALL_SKIPPED is returned then the 'no_update' entry will be set in
        $self to flag that you shouldn't wait.
        If ksb::IPC::ALL_FAILURE is returned then an exception will be thrown due to the
        fatal error.
        This method can be called multiple times, but only the first time will
        result in a wait.
        """

        if not hasattr(IPC, "waited"):
            IPC.waited = 0

        if IPC.waited:
            return

        buffer = ""
        ipcType = 0
        IPC.waited = 1

        while ipcType != IPC.ALL_UPDATING:
            ipcType, buffer = self.receiveIPCMessage()
            ipcType = MsgType(ipcType)  # pl2py: this was not in kdesrc-build

            if not ipcType:
                BuildException.croak_internal("IPC Failure waiting for stream start :(")
            if ipcType == IPC.ALL_FAILURE:
                BuildException.croak_runtime(f"Unable to perform source update for any module:\n\t{buffer}")
            elif ipcType == IPC.ALL_SKIPPED:
                self.no_update = 1
                self.updates_done = 1
            elif ipcType == IPC.MODULE_LOGMSG:
                ipcModuleName, logMessage = buffer.split(",", maxsplit=1)
                if ipcModuleName not in self.messages:
                    self.messages[ipcModuleName] = []
                self.messages[ipcModuleName].append(logMessage)
            elif ipcType != IPC.ALL_UPDATING:
                BuildException.croak_runtime(f"IPC failure while expecting an update status: Incorrect type: {ipcType}")

    def sendIPCMessage(self, ipcType, msg: str) -> bool:
        """
        Sends an IPC message along with some IPC type information.
        
        First parameter is the IPC type to send.
        Second parameter is the actual message.
        All remaining parameters are sent to the object's sendMessage()
         procedure.
        """
        encodedMsg = struct.pack("!l", ipcType) + msg.encode("utf-8")
        return self.sendMessage(encodedMsg)

    @staticmethod
    def unpackMsg(msg: bytes) -> tuple:
        """
        Static class function to unpack a message.
        
        First parameter is the message.
        
        Returns the IPC message type and message content.
        """
        returnType, outBuffer = struct.unpack("!l", msg[:4])[0], msg[4:].decode("utf-8")
        return returnType, outBuffer

    def receiveIPCMessage(self) -> tuple:
        """
        Receives an IPC message and decodes it into the message and its
        associated type information.
        
        Returns the list with IPC type and message content, or list with two None on failure.
        """
        if self.updates_done:
            BuildException.croak_internal("Trying to pull message from closed IPC channel!")
        msg = self.receiveMessage()
        return self.unpackMsg(msg) if msg else (None, None)

    # These must be reimplemented.  They must be able to handle scalars without
    # any extra frills.

    def sendMessage(self, msg: bytes) -> NoReturn:
        # sendMessage should accept one parameter (the message to send) and return
        # true on success, or false on failure.  $! should hold the error information
        # if false is returned.
        BuildException.croak_internal("Unimplemented.")

    def receiveMessage(self) -> NoReturn:
        """
        receiveMessage should return a message received from the other side, or
        undef for EOF or error.  On error, $! should be set to hold the error
        information.
        """
        BuildException.croak_internal("Unimplemented.")

    @staticmethod
    def supportsConcurrency() -> bool:
        """
        Should be reimplemented if default does not apply.
        """
        return False

    def close(self) -> None:
        """
        Should be reimplemented if default does not apply.
        """
        pass


# pl2py: this was not in kdesrc-build, I (Andrew Shark) made this just for convenience while debugging.
# Note that IntEnum can be compared with int as normal.
class MsgType(IntEnum):
    MODULE_SUCCESS = IPC.MODULE_SUCCESS
    MODULE_FAILURE = IPC.MODULE_FAILURE
    MODULE_SKIPPED = IPC.MODULE_SKIPPED
    MODULE_UPTODATE = IPC.MODULE_UPTODATE
    ALL_SKIPPED = IPC.ALL_SKIPPED
    ALL_FAILURE = IPC.ALL_FAILURE
    ALL_UPDATING = IPC.ALL_UPDATING
    MODULE_CONFLICT = IPC.MODULE_CONFLICT
    MODULE_LOGMSG = IPC.MODULE_LOGMSG
    MODULE_PERSIST_OPT = IPC.MODULE_PERSIST_OPT
    ALL_DONE = IPC.ALL_DONE
    MODULE_POSTBUILD_MSG = IPC.MODULE_POSTBUILD_MSG
