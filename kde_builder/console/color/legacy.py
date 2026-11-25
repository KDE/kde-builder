# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Legacy colorization method."""


class LegacyColorizer:
    """
    Format strings by replacing tags with escape sequences.

    Translates custom styling tags like "r[" (red), "g[" (green), "y[" (yellow),
    "b[" (bold) into ANSI terminal escape sequences. It ensures that colors are
    automatically reset back to normal at the end of each log message.
    """

    def __init__(self) -> None:
        # Colors
        self.RED = ""
        self.GREEN = ""
        self.YELLOW = ""
        # Other
        self.NORMAL = ""
        self.BOLD = ""

    def set_colorful_output(self, use_color: bool) -> None:
        if use_color:
            # Colors
            self.RED = "\033[31m"  # "r["
            self.GREEN = "\033[32m"  # "g["
            self.YELLOW = "\033[33m"  # "y["
            # Other
            self.NORMAL = "\033[0m"  # "]"
            self.BOLD = "\033[1m"  # "b["
        else:
            # Colors
            self.RED = ""
            self.GREEN = ""
            self.YELLOW = ""
            # Other
            self.NORMAL = ""
            self.BOLD = ""

    def colorize(self, text: str) -> str:
        """Colorize a string."""
        # Colors
        text = text.replace("r[", self.RED)
        text = text.replace("g[", self.GREEN)
        text = text.replace("y[", self.YELLOW)
        # Other
        text = text.replace("]", self.NORMAL)
        text = text.replace("b[", self.BOLD)

        return text + self.NORMAL


decolorizer = LegacyColorizer()


def strip_color_tags(text: str) -> str:
    """Remove styling tags from a string."""
    return decolorizer.colorize(text)
