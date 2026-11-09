# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Emit and log terminal output."""

from kde_builder.console.colors import ColorFormatter as ColorFormatter
from kde_builder.console.colors import color_formatter as color_formatter
from kde_builder.console.colors import colorize as colorize
from kde_builder.console.colors import colors_enabled as colors_enabled
from kde_builder.console.colors import force_colors as force_colors
from kde_builder.console.stdout import print_if_tty as print_if_tty
from kde_builder.console.stdout import redirect_stdout as redirect_stdout
from kde_builder.console.stdout import use_as_output as use_as_output
