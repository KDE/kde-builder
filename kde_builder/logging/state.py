# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder.console import stderr
from kde_builder.logging.formatter import ColorFormatter

color_formatter = ColorFormatter(colorizer=stderr)
