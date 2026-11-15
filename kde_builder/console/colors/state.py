# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Global colorization state."""

import argparse
from typing import TYPE_CHECKING

from kde_builder.console.colors.clap import extract_color_arg
from kde_builder.console.colors.clap import inject_colors_args
from kde_builder.console.colors.environment import get_colors_from_env
from kde_builder.console.colors.environment import set_colors_env_vars
from kde_builder.console.colors.legacy import ColorFormatter
from kde_builder.console.colors.legacy import Colorizer

if TYPE_CHECKING:
    from collections.abc import Iterable

_colors_enabled = get_colors_from_env()


def colors_enabled() -> bool:
    """Return whether colors are enabled."""
    return _colors_enabled


colorizer = Colorizer()
colorizer.set_colorful_output(_colors_enabled)


def colorize(text: str) -> str:
    """Colorize a string, provided that colors are enabled."""
    return colorizer.colorize(text)


color_formatter = ColorFormatter(colorizer)


def force_colors(value: bool) -> None:
    """
    Forcefully enable or disable colors.

    This sets environment variables. The usual memory safety concerns regarding
    setting environment variables on certain platforms apply, in particular in
    multi-threaded contexts.
    """
    global _colors_enabled

    _colors_enabled = value

    set_colors_env_vars(value)

    colorizer.set_colorful_output(value)


def parse_colors_args(
    args: Iterable[str] | None = None,
    *,
    prog: str = "kde-builder",
    add_help: bool = False,
    formatter_class: type[argparse.HelpFormatter] = argparse.RawDescriptionHelpFormatter,
) -> list[str]:
    """Parse command-line arguments to enable or disable colors."""
    parser = argparse.ArgumentParser(
        prog=prog,
        add_help=add_help,
        formatter_class=formatter_class,
    )

    inject_colors_args(parser)

    namespace, unhandled_args = parser.parse_known_args(args)

    force_colors(extract_color_arg(namespace, default=_colors_enabled))

    return unhandled_args
