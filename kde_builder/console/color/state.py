# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Global colorization state."""

import argparse
from typing import TYPE_CHECKING

from kde_builder.console.color.clap import extract_color_arg
from kde_builder.console.color.clap import inject_color_args
from kde_builder.console.color.env_vars import get_color_from_env
from kde_builder.console.color.env_vars import set_color_env_vars
from kde_builder.console.color.legacy import LegacyColorizer
from kde_builder.console.state import is_tty
from kde_builder.util.forceable import ForceableBool

if TYPE_CHECKING:
    from collections.abc import Iterable


_color_enabled = ForceableBool("color_enabled", get_color_from_env(is_tty()))


def color_enabled() -> bool:
    """Return whether color are enabled."""
    return _color_enabled.value


legacy_colorizer = LegacyColorizer()
legacy_colorizer.set_colorful_output(_color_enabled.value)


def colorize(text: str) -> str:
    """Colorize a string, provided that color are enabled."""
    return legacy_colorizer.colorize(text)


def set_color_enabled(value: bool) -> None:
    """
    Enable or disable color.

    This may set environment variables. The usual memory safety concerns
    regarding setting environment variables on certain platforms apply, in
    particular in multi-threaded contexts.

    If the setting has already been forced, this function has no effect.

    Args:
        value:
            The new setting value.
    """
    _set_color_enabled(value, force=False)


def _set_color_enabled(value: bool, *, force: bool = False) -> None:
    """
    Enable or disable color.

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
    if _color_enabled.set_checked(value, force=force):
        # We only need to update synchronized state if the setting changes.

        set_color_env_vars(_color_enabled.value)

        legacy_colorizer.set_colorful_output(_color_enabled.value)


def parse_color_args(
    args: Iterable[str] | None = None,
    *,
    prog: str = "kde-builder",
    add_help: bool = False,
    formatter_class: type[argparse.HelpFormatter] = argparse.RawDescriptionHelpFormatter,
) -> list[str]:
    """Parse command-line arguments to enable or disable color."""
    parser = argparse.ArgumentParser(
        prog=prog,
        add_help=add_help,
        formatter_class=formatter_class,
    )

    inject_color_args(parser)

    namespace, unhandled_args = parser.parse_known_args(args)

    value = extract_color_arg(namespace, default=None)

    if value is not None:
        # The command-line argument has the final say, so we force the setting.
        _set_color_enabled(value, force=True)

    return unhandled_args
