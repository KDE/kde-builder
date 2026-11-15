# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from kde_builder.console.colors.state import colors_enabled
from kde_builder.console.colors.state import parse_colors_args

unhandled_argv = parse_colors_args(add_help=True)

print()

print("Colors Enabled:", colors_enabled())

if unhandled_argv:
    print("Unhandled argv:", unhandled_argv)

print()
