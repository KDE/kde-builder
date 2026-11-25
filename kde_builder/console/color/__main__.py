# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from kde_builder.console.color.state import color_enabled
from kde_builder.console.color.state import parse_color_args

unhandled_argv = parse_color_args(add_help=True)

print()

print("Color Enabled:", color_enabled())

if unhandled_argv:
    print("Unhandled argv:", unhandled_argv)

print()
