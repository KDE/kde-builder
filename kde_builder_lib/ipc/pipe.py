# SPDX-FileCopyrightText: 2012, 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import struct
import multiprocessing

from .ipc import IPC
from ..kb_exception import KBRuntimeError
from ..kb_exception import ProgramError


class IPCPipe(IPC):
    """
    IPC class that uses pipes in addition to forking for IPC.
    """

    def __init__(self):
        IPC.__init__(self)

        # Define file handles.
        self.queue = multiprocessing.Queue()

    def set_sender(self):
        """
        Call this to let the object know it will be the update process.
        """
        pass

    def set_receiver(self):
        pass

    @staticmethod
    # @override
    def supports_concurrency() -> bool:
        return True

    # @override(check_signature=False)
    def send_message(self, msg: bytes) -> bool:
        """
        Send message.

        Args:
             msg: The (encoded) message to send.
        """
        # Since streaming does not provide message boundaries, we will insert
        # ourselves, by sending a 2-byte unsigned length, then the message.
        self.queue.put(msg)

        return True

    # @override(check_signature=False)
    def receive_message(self) -> bytes:
        # Read unsigned short with msg length, then the message
        msg = self.queue.get()
        return msg

    # @override
    def close(self):
        self.queue.close()
