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

from contextlib import AbstractContextManager
from typing import Any
from typing import Self

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


class ProgressBar(AbstractContextManager):
    """
    Show a percentage using a progress bar.

    This class is intended to be used as a context manager, like so:

    ```python
    with ProgressBar() as progress:
        for i in range(0, 20):
            progress.value = i * 5
    ```

    It is also possible to increment or decrement the progress bar value, either
    by an integer or by a fractional amount:

    ```python
    with ProgressBar() as progress:
        for _ in range(0, 200):
            progress.value += 0.5
    ```

    As shorthand, you can use the `+=` and `-=` operators:

    ```python
    with ProgressBar() as progress:
        for _ in range(0, 40):
            progress += 2.5
    ```

    A `ProgressBar()` instance can be compared with regular numbers:

    ```python
    with ProgressBar() as progress:
        for i in range(0, 100):
            progress.value = i
            if progress == 95:
                print("Almost there!")
    ```

    The `<`, `>`, `<=`, `>=`, `==`, and `!=` operators can be used to compare
    a `ProgressBar` with `int` and `float`. The comparisons are always performed
    by rounding and clamping both values to the range `[0, 100]`.

    The above is equivalent to comparing the `ProgressBar.rounded_and_clamped`
    property with a number.

    If you need to compare the progress including the fractional part with a
    number, use the `ProgressBar.value` property instead.
    """

    def __init__(self):
        self._value: float | int = 0.0
        self._rounded_and_clamped: int = 0
        self._visible = False

    def __enter__(self) -> Self:
        self._visible = True
        show_progress_bar(self._rounded_and_clamped)
        return self

    def __exit__(self, *_args) -> bool:
        hide_progress_bar()
        self._visible = False
        return False

    def __ge__(self, other: float | int) -> bool:
        return self._rounded_and_clamped >= _round_and_clamp(other)

    def __gt__(self, other: float | int) -> bool:
        return self._rounded_and_clamped > _round_and_clamp(other)

    def __le__(self, other: float | int) -> bool:
        return self._rounded_and_clamped <= _round_and_clamp(other)

    def __lt__(self, other: float | int) -> bool:
        return self._rounded_and_clamped < _round_and_clamp(other)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float):
            return self._rounded_and_clamped == _round_and_clamp(other)

        return False

    def __ne__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float):
            return self._rounded_and_clamped != _round_and_clamp(other)

        return True

    def __str__(self) -> str:
        return f"{self._value:.1f}%"

    @property
    def rounded_and_clamped(self) -> int:
        return self._rounded_and_clamped

    @property
    def value(self) -> float | int:
        return self._value

    def _set_value(self, value: float | int) -> Self:
        """Update the percentage to the given value."""
        self._value = max(0.0, min(value, 100.0))
        self._rounded_and_clamped = round(self._value)
        self.refresh()
        return self

    @value.setter
    def value(self, value: float | int) -> None:
        self._set_value(value)

    def hide(self) -> None:
        self._visible = False
        hide_progress_bar()

    def show(self) -> None:
        self._visible = True
        _show_progress_bar(self._rounded_and_clamped)

    def refresh(self) -> None:
        if self._visible:
            _show_progress_bar(self._rounded_and_clamped)
        else:
            hide_progress_bar()

    def __iadd__(self, delta: float | int) -> Self:
        """Add the given delta to the percentage."""
        return self._set_value(self._value + delta)

    def __isub__(self, delta: float | int) -> Self:
        """Subtract the given delta to the percentage."""
        return self._set_value(self._value - delta)
