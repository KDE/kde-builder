# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Emit and log terminal output."""

from kde_builder.console.colors import colorize as colorize
from kde_builder.console.colors import colors_enabled as colors_enabled
from kde_builder.console.colors import inject_colors_args as inject_colors_args
from kde_builder.console.colors import parse_colors_args as parse_colors_args
from kde_builder.console.colors import set_colors_enabled as set_colors_enabled
from kde_builder.console.colors import strip_color_tags as strip_color_tags
from kde_builder.console.stdout import is_tty as is_tty
from kde_builder.console.stdout import print_if_tty as print_if_tty
from kde_builder.console.stdout import redirect_stdout as redirect_stdout
from kde_builder.console.stdout import use_as_output as use_as_output
