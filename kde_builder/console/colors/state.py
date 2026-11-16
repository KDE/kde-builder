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
from kde_builder.console.colors.legacy import LegacyColorizer
from kde_builder.util.forceable import ForceableBool

if TYPE_CHECKING:
    from collections.abc import Iterable


_colors_enabled = ForceableBool("colors_enabled", get_colors_from_env())


def colors_enabled() -> bool:
    """Return whether colors are enabled."""
    return _colors_enabled.value


legacy_colorizer = LegacyColorizer()
legacy_colorizer.set_colorful_output(_colors_enabled.value)


def colorize(text: str) -> str:
    """Colorize a string, provided that colors are enabled."""
    return legacy_colorizer.colorize(text)


def set_colors_enabled(value: bool, *, force: bool = False) -> None:
    """
    Enable or disable colors.

    This may set environment variables. The usual memory safety concerns
    regarding setting environment variables on certain platforms apply, in
    particular in multi-threaded contexts.

    Args:
        value:
            The new setting value.
        force:
            Whether to force the setting.

            If force is True, the new value is always set.

            If force is False, the new value is only applied if the setting was
            not forced previously.
    """
    if _colors_enabled.set_checked(value, force=force):
        # We only need to update synchronized state if the setting changes.

        set_colors_env_vars(_colors_enabled.value)

        legacy_colorizer.set_colorful_output(_colors_enabled.value)


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

    value = extract_color_arg(namespace, default=None)

    if value is not None:
        # The command-line argument has the final say, so we force the setting.
        set_colors_enabled(value, force=True)

    return unhandled_args
