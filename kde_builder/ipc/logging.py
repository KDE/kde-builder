# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import logging
from logging import LogRecord
from typing import TYPE_CHECKING
from typing import override

if TYPE_CHECKING:
    from kde_builder.ipc.pipe import IPCPipe


class IPCQueueLoggingHandler(logging.Handler):
    """
    Inter-process logging handler for the concurrent update process.

    Intercepts standard log records inside the background updater process and
    extracts metadata (logger name, severity level, and message string). It then
    safely forwards this structured data via the IPC layer to the main build
    process for synchronized console display.
    """

    def __init__(self, ipc_obj: IPCPipe) -> None:
        super().__init__()
        self.ipc = ipc_obj

    @override
    def emit(self, record: LogRecord) -> None:
        try:
            logger_name = record.name
            message_level = record.levelname.lower()
            msg = str(record.msg)

            self.ipc.send_log_message(logger_name, message_level, msg)
        except Exception:
            self.handleError(record)
