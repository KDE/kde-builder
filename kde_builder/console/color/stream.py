# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from typing import TYPE_CHECKING
from typing import Literal
from typing import override

from kde_builder.console.color.legacy import LegacyColorizer
from kde_builder.console.stream import Stream
from kde_builder.util.forceable import ForceableBool

if TYPE_CHECKING:
    from collections.abc import Iterable


class ColorStream(Stream):
    """A wrapper for a standard output stream that knows about color."""

    def __init__(
        self,
        target: Literal["stdout"] | Literal["stderr"],
        color: bool | None = None,
    ) -> None:

        super().__init__(target)

        if color is None:
            color = self.is_tty

        self._color = ForceableBool(f"{target}-color", color)

        self._legacy_colorizer = LegacyColorizer()
        self._legacy_colorizer.set_colorful_output(self._color.value)

    @property
    def color(self) -> bool:
        return self._color.value

    @color.setter
    def color(self, value: bool) -> None:
        self._set_color(value, force=False)

    def _set_color(self, color: bool, force: bool = False) -> bool:
        changed = self._color.set_checked(color, force=force)
        if changed:
            self._legacy_colorizer.set_colorful_output(self._color.value)
        return changed

    @property
    def legacy_colorizer(self) -> LegacyColorizer:
        return self._legacy_colorizer

    def colorize(self, text: str) -> str:
        return self._legacy_colorizer.colorize(text)

    def _colorize[T](self, arg: T) -> T | str:
        if isinstance(arg, str):
            return self._legacy_colorizer.colorize(arg)
        else:
            return arg

    def _maybe_colorize_all(self, args: Iterable[object]) -> list[object]:
        return [self._colorize(arg) for arg in args]

    def print_as_is_if_tty(
        self,
        *args: object,
        sep: str | None = " ",
        end: str | None = "\n",
        flush: bool = False,
    ) -> None:
        """Print to the registered output, if it is a TTY."""
        super().print_if_tty(*args, sep=sep, end=end, flush=flush)

    @override
    def print(
        self,
        *args: object,
        sep: str | None = " ",
        end: str | None = "\n",
        flush: bool = False,
    ) -> None:
        """Colorize and print to the registered output."""
        super().print(*self._maybe_colorize_all(args), sep=sep, end=end, flush=flush)

    @override
    def print_if_tty(
        self,
        *args: object,
        sep: str | None = " ",
        end: str | None = "\n",
        flush: bool = False,
    ) -> None:
        """Colorize and print to the registered output, if it is a TTY."""
        super().print_if_tty(*self._maybe_colorize_all(args), sep=sep, end=end, flush=flush)


class ConfigurableColorStream(ColorStream):
    """Allow this package to override certain settings."""

    def set_color(self, color: bool, force: bool = False) -> bool:
        return self._set_color(color, force=force)
