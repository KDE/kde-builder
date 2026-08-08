# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

def dedent(text: str, preserve_len: int = 0):
    """
    Strip leading spaces from a multi-line string.

    Allows usage of docstring-like strings in code, for eye candy multiline string code blocks.
    Only spaces are stripped. The tabulations are always preserved.

    Args:
        text (str): The multi-line string to dedent.
        preserve_len (int): The number of spaces to preserve before dedenting.
    """
    assert isinstance(text, str)
    lines = text.split("\n")

    # Remove first and last new lines, to behave like docstring.
    if len(lines):
        if lines[0].isspace() or lines[0] == "":
            lines.pop(0)
    if len(lines):
        if lines[-1].isspace() or lines[-1] == "":
            lines.pop(-1)

    # Determine length of common leading whitespace.
    non_blank_lines = [line for line in lines if line and not line.isspace()]
    line_min = min(non_blank_lines, default="")
    line_max = max(non_blank_lines, default="")
    start_index = 0
    for start_index, char in enumerate(line_min):
        if char != line_max[start_index] or char != " ":
            break

    start_index -= preserve_len
    ret = "\n".join([line[start_index:] if not line.isspace() else "" for line in lines])
    return ret
