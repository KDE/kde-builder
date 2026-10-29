# SPDX-FileCopyrightText: 2012 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import queue
from typing import override

from kde_builder.ipc.ipc import IPC


class IPCNull(IPC):
    """Dummy IPC module in case SysVIPC doesn't work or async mode is not needed."""

    def __init__(self) -> None:
        super().__init__()
        self.queue = queue.Queue()

    @override
    def receive_message(self) -> tuple[int, str]:
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return 0, ""

    @staticmethod
    def supports_concurrency() -> bool:
        return False
