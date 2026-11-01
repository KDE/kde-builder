# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys


def colors_enabled() -> bool:
    """
    Determines whether colors should be enabled.

    Broadly replicates Python's approach to controlling color. It performs the
    following checks in order:

    If the `PYTHON_COLORS` environment variable is set, then we enable colors
    if its value is equal to `1`, and disable colors if it is set to `0`.

    If the `NO_COLOR` environment variable is present, colors are disabled.

    If the `FORCE_COLOR` environment variable is present, colors are enabled.

    If the `TERM` environment variable is set to `dumb`, colors are disabled.

    If `sys.stdout.isatty()` is True, colors are enabled, otherwise disabled.
    """
    # See https://docs.python.org/3/using/cmdline.html#envvar-PYTHON_COLORS
    python_colors = os.getenv("PYTHON_COLORS")
    if python_colors == "1":
        return True
    elif python_colors == "0":
        return False

    # See https://no-color.org/
    if os.getenv("NO_COLOR", "") != "":
        return False

    # See https://force-color.org/
    if os.getenv("FORCE_COLOR", "") != "":
        return True

    # See https://docs.python.org/3/using/cmdline.html#using-on-controlling-color
    if os.getenv("TERM", "") == "dumb":
        return False

    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
