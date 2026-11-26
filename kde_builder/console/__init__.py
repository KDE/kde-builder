# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Emit and log terminal output."""

from kde_builder.console.color import color_enabled as color_enabled
from kde_builder.console.color import colorize as colorize
from kde_builder.console.color import inject_color_args as inject_color_args
from kde_builder.console.color import parse_color_args as parse_color_args
from kde_builder.console.color import set_color_enabled as set_color_enabled
from kde_builder.console.color import strip_color_tags as strip_color_tags
from kde_builder.console.state import print_if_tty as print_if_tty
from kde_builder.console.state import redirect_stdout as redirect_stdout
from kde_builder.console.state import stderr as stderr
from kde_builder.console.state import stdout as stdout
from kde_builder.console.state import use_as_outputs as use_as_outputs
