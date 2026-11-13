# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Global colorization state."""

from kde_builder.console.colors.environment import get_colors_from_env
from kde_builder.console.colors.environment import set_colors_env_vars
from kde_builder.console.colors.legacy import ColorFormatter
from kde_builder.console.colors.legacy import Colorizer

colorizer = Colorizer()
colorizer.set_colorful_output(get_colors_from_env())

color_formatter = ColorFormatter(colorizer)


def force_colors(value: bool) -> None:
    """
    Forcefully enable or disable colors by setting environment variables.

    The usual memory safety concerns regarding setting environment variables on
    certain platforms apply, in particular in multi-threaded contexts.
    """
    set_colors_env_vars(value)

    colorizer.set_colorful_output(value)


def colorize(text: str) -> str:
    """Colorize a string, provided that colors are enabled."""
    return colorizer.colorize(text)
