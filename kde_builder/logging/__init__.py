# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Logging infrastructure."""

from kde_builder.logging.formatter import ColorFormatter as ColorFormatter
from kde_builder.logging.root import disable_screen_log as disable_screen_log
from kde_builder.logging.root import replace_root_handlers as replace_root_handlers
from kde_builder.logging.root import set_log_directory as set_log_directory
from kde_builder.logging.state import color_formatter as color_formatter
