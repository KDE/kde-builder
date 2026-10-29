# SPDX-FileCopyrightText: 2012, 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import multiprocessing
import queue
from typing import override

from kde_builder.ipc.ipc import IPC


class IPCPipe(IPC):
    """IPC class that uses pipes in addition to forking for IPC."""

    def __init__(self) -> None:
        super().__init__()
        self.queue = multiprocessing.Queue()

    @override
    def receive_message(self) -> tuple[int, str]:
        try:
            return self.queue.get()
        except queue.Empty:
            return 0, ""

    @staticmethod
    @override
    def supports_concurrency() -> bool:
        return True
