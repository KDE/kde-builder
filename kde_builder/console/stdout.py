# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import builtins
import contextlib
import os
import sys
from typing import Generator
from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class OutputProtocol(Protocol):
    """Set of methods required for output streams."""

    def isatty(self) -> bool:
        pass

    def write(self, s: str, /) -> int:
        pass

    def flush(self) -> None:
        pass


_output: OutputProtocol = sys.stdout
_is_tty = _output.isatty()


def use_as_output(stream: OutputProtocol):
    """
    Set the stream to be used as output stream.

    This does not replace `sys.stdout`. See `redirect_stdout()`.
    """
    if not isinstance(stream, OutputProtocol):
        raise TypeError(f"stream does not implement {OutputProtocol.__qualname__}")

    global _output, _is_tty

    _output, _is_tty = stream, stream.isatty()


@contextlib.contextmanager
def redirect_stdout(require_tty: bool = True) -> Generator[None]:
    """
    Redirect all writes to `sys.stdout` to the registered output stream.

    If `require_tty` is `True`, and the registered output stream is not a TTY,
    all writes are redirected to `os.devnull` instead.

    If you only want to print a single thing, see `print_if_tty()` instead.
    """
    if require_tty and not _is_tty:
        with open(file=os.devnull, mode="w") as fd:
            with contextlib.redirect_stdout(fd):
                yield
    else:
        with contextlib.redirect_stdout(_output):
            try:
                yield
            finally:
                _output.flush()


def print_if_tty(
    *values: object,
    sep: str | None = " ",
    end: str | None = "\n",
    flush: bool = False,
) -> None:
    """
    Print to the registered output stream, if it is a TTY.

    If your code uses this function, it's worthwhile to investigate whether
    adding an abstraction or widget to the console package would be appropriate.

    If you want to print many things, see `redirect_stdout()` instead.
    """
    if _is_tty:
        builtins.print(*values, sep=sep, end=end, file=_output, flush=flush)
