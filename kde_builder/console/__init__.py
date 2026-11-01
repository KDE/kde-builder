# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Emit and log terminal output."""

from kde_builder.console.colors import ColorFormatter
from kde_builder.console.colors import color_formatter
from kde_builder.console.colors import colors_enabled
from kde_builder.console.colors import force_colors

__all__ = [
    "ColorFormatter",
    "color_formatter",
    "colors_enabled",
    "force_colors",
]
