# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Colorization support."""

from kde_builder.console.colors.clap import inject_colors_args as inject_colors_args
from kde_builder.console.colors.legacy import strip_color_tags as strip_color_tags

# Import statements that modify state must come last!
from kde_builder.console.colors.state import colorize as colorize
from kde_builder.console.colors.state import colors_enabled as colors_enabled
from kde_builder.console.colors.state import parse_colors_args as parse_colors_args
from kde_builder.console.colors.state import set_colors_enabled as set_colors_enabled
