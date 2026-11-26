# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Colorization support."""

from kde_builder.console.color.clap import inject_color_args as inject_color_args
from kde_builder.console.color.legacy import strip_color_tags as strip_color_tags

# Import statements that modify state must come last!
from kde_builder.console.color.state import colorize as colorize
from kde_builder.console.color.state import parse_color_args as parse_color_args
from kde_builder.console.color.state import set_color_enabled as set_color_enabled
from kde_builder.console.color.state import stderr as stderr
from kde_builder.console.color.state import stdout as stdout
