# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from kde_builder.console.color import stderr as _stderr
from kde_builder.console.color import stdout as _stdout
from kde_builder.console.color.stream import ColorStream
from kde_builder.console.stream import OutputProtocol

stdout: ColorStream = _stdout
stderr: ColorStream = _stderr


def use_as_outputs(stdout: OutputProtocol, stderr: OutputProtocol):
    """
    Set the streams to be used as stdout and stderr.

    Does not modify `sys.stdout` or `sys.sdtderr`. use the `intercept()` method
    on `console.stdout` and `console.stderr` for that purpose.
    """
    _stdout.output = stdout
    _stderr.output = stderr


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
    _stdout.print_as_is_if_tty(*values, sep=sep, end=end, flush=flush)
