# SPDX-FileCopyrightText: 2012, 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import struct

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
        self.pipe_read, self.pipe_write = os.pipe()
        self.fh = None

    def set_sender(self):
        """
        Call this to let the object know it will be the update process.
        """
        os.close(self.pipe_read)
        self.fh = os.fdopen(self.pipe_write, "wb", 0)  # Disable buffering and any possibility of IO "interpretation" of the bytes

    def set_receiver(self):
        os.close(self.pipe_write)
        self.fh = os.fdopen(self.pipe_read, "rb", 0)  # Disable buffering and any possibility of IO "interpretation" of the bytes

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
        encoded_msg = struct.pack("H", len(msg)) + msg
        written_length = self.fh.write(encoded_msg)

        if not written_length or len(encoded_msg) != written_length:
            raise KBRuntimeError("Unable to write full msg to pipe")

        return True

    def _read_number_of_bytes(self, length: int) -> bytes:
        fh = self.fh
        result = fh.read(length)
        return result

    # @override(check_signature=False)
    def receive_message(self) -> bytes:
        # Read unsigned short with msg length, then the message
        msg_length = self._read_number_of_bytes(2)
        if not msg_length:
            return b""

        msg_length = struct.unpack("H", msg_length)[0]  # Decode to Perl type
        if not msg_length:
            raise ProgramError(f"Failed to read {msg_length} bytes as needed by earlier message!")

        return self._read_number_of_bytes(msg_length)

    # @override
    def close(self):
        self.fh.close()
