# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder.console.color.state import legacy_colorizer
from kde_builder.logging.formatter import ColorFormatter

color_formatter = ColorFormatter(legacy_colorizer=legacy_colorizer)
