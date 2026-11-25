# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import sys
from logging import FileHandler
from logging import StreamHandler
from logging.handlers import MemoryHandler
from pathlib import Path

from kde_builder.console.color.legacy import decolorizer
from kde_builder.logging.formatter import ColorFormatter
from kde_builder.logging.state import color_formatter

SCREEN_LOG_BASENAME = "screen.log"


root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)


def set_log_level(level: int | str):
    """Sets the level of the root logger."""
    root_logger.setLevel(level)


# Immediately dump log records to `sys.stderr`:
stderr_handler = StreamHandler(sys.stderr)
stderr_handler.setFormatter(color_formatter)
root_logger.addHandler(stderr_handler)


# Buffer log records until the log directory is defined:
screen_log_handler = MemoryHandler(capacity=0, flushOnClose=True)
root_logger.addHandler(screen_log_handler)


def disable_screen_log() -> None:
    """Disables writing log records to the screen.log file."""
    root_logger.removeHandler(screen_log_handler)
    screen_log_handler.flushOnClose = False
    screen_log_handler.close()


def set_log_directory(path: Path | str) -> None:
    """Set the log file that captures the console output."""
    path = Path(path)

    path.mkdir(parents=True, exist_ok=True)

    handler = FileHandler(path / SCREEN_LOG_BASENAME, delay=True)

    # ColorFormatter in its default state just strips colorization syntax.
    handler.setFormatter(ColorFormatter(decolorizer))

    screen_log_handler.setTarget(handler)
    screen_log_handler.flush()


def replace_root_handlers(handler: logging.Handler) -> None:
    """
    Replaces all handlers of the root logger with the given handler.

    This is a method of last resort. Ideally, it should not be used at all.
    """
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
