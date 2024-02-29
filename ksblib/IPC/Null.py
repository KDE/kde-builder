# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>

from ..Util.Conditional_Type_Enforced import conditional_type_enforced
# from overrides import override

from .IPC import IPC


@conditional_type_enforced
class IPC_Null(IPC):
    """
    Dummy IPC module in case SysVIPC doesn't work or async mode is not needed.
    """
    
    def __init__(self):
        IPC.__init__(self)
        self.msgList = []  # List of messages.
    
    # @override(check_signature=False)
    def sendMessage(self, msg) -> bool:
        self.msgList.append(msg)
        return True
    
    # @override(check_signature=False)
    def receiveMessage(self) -> bytes:
        if not len(self.msgList) > 0:
            return b""
        return self.msgList.pop(0)
