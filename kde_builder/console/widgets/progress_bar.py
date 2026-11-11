# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later


"""
Show a progress bar using OSC 9;4 sequences.

Some terminal emulators implement support for escape sequence of the form

    ESC ] 9 ; st ; pr ST

where

    st = state in 0, 1, 2, 3, 4
    pr = progress from 0 to 100

They can be used to notify terminal emulators that they should update their UI
to indicate process state, e.g. by rendering a progress bar.

The meanings of the five values for `st` are:

    0 = remove the progress bar
    1 = show/update the progress bar
    2 = set process state as error
    3 = set process state as undetermined
    4 = set process state as paused

This module only implements support for the first two, because the other three
are not widely supported, and rendered incorrectly, if at all.

See the [ConEmu][1] docs for the original specification.

The [Ghostty Docs][2] also contain helpful information on the subject.

In particular, the note at the very bottom may be salient: Since there is no way
for a terminal to check whether process state has become stale, Ghostty hides
the progress bar if there is no activity for a certain period. To prevent this,
they recommend updating the progress bar state at least once every second.


[1]: https://conemu.github.io/en/AnsiEscapeCodes.html#ConEmu_specific_OSC
[2]: https://ghostty.org/docs/vt/osc/conemu
"""


from kde_builder.console.stdout import print_if_tty


def hide_progress_bar() -> None:
    """Hide the progress bar."""
    print_if_tty("\033]9;4;0;0\033\\", end="", flush=True)


def _show_progress_bar(percent: int):
    print_if_tty(f"\033]9;4;1;{percent}\033\\", end="", flush=True)


def _round_and_clamp(number: float | int, /, at_least: int = 0, at_most: int = 100) -> int:
    return max(at_least, min(round(number), at_most))


def show_progress_bar(percent: float | int):
    """
    Display a progress bar updated to show the given percentage.

    The rounded value of `percent` is clamped to the range `[0, 100]`.
    """
    _show_progress_bar(_round_and_clamp(percent))
