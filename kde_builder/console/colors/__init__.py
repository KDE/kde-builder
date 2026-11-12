# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Colorization support."""

from kde_builder.console.colors.legacy import ColorFormatter as ColorFormatter

# Import statements that modify state must come last!
from kde_builder.console.colors.state import color_formatter as color_formatter
from kde_builder.console.colors.state import colorize as colorize
from kde_builder.console.colors.state import force_colors as force_colors
