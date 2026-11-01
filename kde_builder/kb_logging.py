# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import logging
import sys
from logging import LogRecord
from typing import TYPE_CHECKING

import kde_builder
from kde_builder.console import ColorFormatter

if TYPE_CHECKING:
    from kde_builder.ipc.pipe import IPCPipe


class TTYAndScreenLogHandler(logging.Handler):
    """
    Main process logging handler for simultaneous terminal output and file logging.

    Formats and prints colorized log records directly to the standard output (TTY).
    Additionally, it strips formatting tags to write clean text into the "screen.log"
    file, managing an internal buffer for any log messages generated before the
    application's log directory is fully initialized.
    """

    def __init__(self) -> None:
        super().__init__()
        self.screen_log_fh = None
        """Filehandle pointing to the "screen.log"."""
        self._pending_screen_log_text = ""
        """Store screen text that was printed before we determined log-dir."""

        self.formatter = ColorFormatter()

    def set_log_file(self, file_name: str) -> None:
        if kde_builder.is_pretending:
            return
        try:
            self.screen_log_fh = open(file_name, "w")
            print(self._pending_screen_log_text, file=self.screen_log_fh, end="")  # flush pended text to log file
        except IOError:
            sys.stderr.write(f"Unable to open log file {file_name}!")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            color_msg = self.formatter.format(record)
            print(color_msg)

            if not kde_builder.is_pretending:
                clean_msg = record.msg
                for tag in ["r[", "g[", "y[", "]", "b["]:
                    clean_msg = clean_msg.replace(tag, "")

                if self.screen_log_fh:
                    print(clean_msg, file=self.screen_log_fh)
                else:
                    self._pending_screen_log_text += clean_msg + "\n"

        except Exception:
            self.handleError(record)


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

    def emit(self, record: LogRecord) -> None:
        try:
            logger_name = record.name
            message_level = record.levelname.lower()
            msg = str(record.msg)

            self.ipc.send_log_message(logger_name, message_level, msg)
        except Exception:
            self.handleError(record)


main_handler = TTYAndScreenLogHandler()
main_handler.formatter.set_colorful_output(True)


def colorize(text: str) -> str:
    return main_handler.formatter.format_string(text)
