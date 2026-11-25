# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import builtins
import os
import sys
from contextlib import contextmanager
from typing import Generator
from typing import Literal
from typing import Protocol
from typing import runtime_checkable


class Stream:
    """A wrapper for an output stream (i.e. stdout or stderr)."""

    def __init__(self, target: Literal["stdout"] | Literal["stderr"]) -> None:
        self._output: OutputProtocol = getattr(sys, target)
        self._target = target
        self._is_tty = self._output.isatty()

        # Make `redirect()` re-entrant:
        self._redirect_stack: list[OutputProtocol] = []

    @property
    def is_tty(self) -> bool:
        return self._is_tty

    @property
    def output(self) -> OutputProtocol:
        return self._output

    @output.setter
    def output(self, value: OutputProtocol) -> None:
        if not isinstance(value, OutputProtocol):
            raise TypeError(f"stream does not implement {OutputProtocol.__qualname__}")

        self._output = value
        self._is_tty = value.isatty()

    def print(
        self,
        *args: object,
        sep: str | None = " ",
        end: str | None = "\n",
        flush: bool = False,
    ) -> None:
        """Print to the registered output."""
        builtins.print(*args, sep=sep, end=end, file=self._output, flush=flush)

    def print_if_tty(
        self,
        *args: object,
        sep: str | None = " ",
        end: str | None = "\n",
        flush: bool = False,
    ) -> None:
        """Print to the registered output, if it is a TTY."""
        if self._is_tty:
            builtins.print(*args, sep=sep, end=end, file=self._output, flush=flush)

    @contextmanager
    def intercept(self, require_tty: bool = True) -> Generator[None]:
        """
        Intercepts all writes to the target, and forwards them to output.

        If `require_tty` is `True`, and the registered output is not a TTY,
        all writes are redirected to `os.devnull` instead.
        """
        if require_tty and not self._is_tty:
            with open(file=os.devnull, mode="w") as output:
                self._redirect_stack.append(getattr(sys, self._target))
                setattr(sys, self._target, output)
                try:
                    yield
                finally:
                    setattr(sys, self._target, self._redirect_stack.pop())
        else:
            self._redirect_stack.append(getattr(sys, self._target))
            setattr(sys, self._target, self._output)
            try:
                yield
                self._output.flush()
            finally:
                setattr(sys, self._target, self._redirect_stack.pop())


@runtime_checkable
class OutputProtocol(Protocol):
    """Set of methods required for output streams."""

    def isatty(self) -> bool:
        pass

    def write(self, s: str, /) -> int:
        pass

    def flush(self) -> None:
        pass
