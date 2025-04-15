# SPDX-FileCopyrightText: 2012 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from .ipc import IPC


class IPCNull(IPC):
    """
    Dummy IPC module in case SysVIPC doesn't work or async mode is not needed.
    """

    def __init__(self):
        IPC.__init__(self)
        self.msgList: list[bytes] = []  # List of messages.

    # @override(check_signature=False)
    def send_message(self, msg: bytes) -> bool:
        self.msgList.append(msg)
        return True

    # @override(check_signature=False)
    def receive_message(self) -> bytes:
        if not len(self.msgList) > 0:
            return b""
        return self.msgList.pop(0)
