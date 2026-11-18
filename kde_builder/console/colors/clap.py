# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Command-line argument processing."""

import argparse
from typing import Any

_COLOR_DEST = "colors"

_COLOR_GROUP_TITLE = "color options"

_COLOR_GROUP_DESC = """
KDE Builder can colorize its output, if desired.

This behaviour can be controlled using the standard `NO_COLOR` and `FORCE_COLOR`
environment variables, or by using any of the options in this group.
"""


def inject_colors_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Inject arguments that control colors into a parser."""
    group = parser.add_argument_group(
        title=_COLOR_GROUP_TITLE,
        description=_COLOR_GROUP_DESC,
    )

    # Adding a mutually exclusive group here would be pointless, because for
    # some reason, `argparse.BooleanOptionalAction` allows you to specify both
    # the flag and its negation (last one wins semantics) without complaint.

    group.add_argument(
        "--color",
        dest=_COLOR_DEST,
        action=argparse.BooleanOptionalAction,
        help="enable or disable colors",
    )

    group.add_argument(
        "--colorful-output",
        dest=_COLOR_DEST,
        action=argparse.BooleanOptionalAction,
        help=argparse.SUPPRESS,  # hide from help, one option is enough
    )

    return parser


def extract_color_arg[T](namespace: argparse.Namespace | Any, *, default: T) -> bool | T:
    """
    Extract the value of the argument that controls colors from a namespace.

    Args:
        namespace: The object to extract the attribute from.
        default: The fallback value.

    Returns:
        The value of the corresponding namespace attribute, if it is set on
        namespace and is not None, and default otherwise.

    Raises:
        TypeError: The value of the namespace attribute was not a boolean.
    """
    value = getattr(namespace, _COLOR_DEST, None)

    if value is None:
        return default

    if isinstance(value, bool):
        return value

    raise TypeError(f"namespace.{_COLOR_DEST} was {type(value)} instead of a boolean")
