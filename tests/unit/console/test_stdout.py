# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import io
import sys
from typing import Any

import pytest

import kde_builder.console.stdout as stdout


def test_protocol_matches_stdout(capsys: pytest.CaptureFixture[str]):
    with capsys.disabled():
        assert isinstance(sys.stdout, stdout.OutputProtocol)


def test_protocol_matches_stderr(capsys: pytest.CaptureFixture[str]):
    with capsys.disabled():
        assert isinstance(sys.stderr, stdout.OutputProtocol)


class NoIsatty:
    def write(self, _: str, /) -> int:
        raise NotImplementedError

    def flush(self) -> None:
        raise NotImplementedError


class NoWrite:
    def isatty(self) -> bool:
        raise NotImplementedError

    def flush(self) -> None:
        raise NotImplementedError


class NoFlush:
    def isatty(self) -> bool:
        raise NotImplementedError

    def write(self, _: str, /) -> int:
        raise NotImplementedError


@pytest.mark.parametrize(
    argnames="stream",
    argvalues=[
        NoIsatty(),
        NoWrite(),
        NoFlush(),
        RuntimeError(),
    ],
    ids=lambda x: x.__class__.__qualname__,
)
def test_use_as_output_rejects_unsuitable_type(stream: Any):
    with pytest.raises(TypeError):
        stdout.use_as_output(stream)


class MockOutput(io.StringIO):
    def __init__(self, /, is_tty: bool) -> None:
        super().__init__()
        self.is_tty = is_tty

    def isatty(self) -> bool:
        return self.is_tty

    def write(self, s: str) -> int:
        print(f"write({s!r})", file=sys.stderr)
        n = super().write(s)
        print(f" -> {self.getvalue()!r}\n", file=sys.stderr)
        return n

    def flush(self) -> None:
        print("flush()", file=sys.stderr)
        super().flush()


def parametrize_stdout_tests(fn):
    def print_call_param(*args, **kwargs):
        arg_desc = [f"{v}" for v in args]
        kwarg_desc = [f"{k}={v}" for k, v in kwargs.items()]
        desc = f"print({', '.join(arg_desc + kwarg_desc)})"

        return pytest.param(args, kwargs, id=desc)

    fn = pytest.mark.parametrize(
        argnames="args,kwargs",
        argvalues=[
            print_call_param("Hello", "World", end=""),
            print_call_param("Hello", "World"),
            print_call_param(),
            print_call_param(1),
        ],
    )(fn)

    fn = pytest.mark.parametrize(
        argnames="is_tty",
        argvalues=[True, False],
        ids=lambda x: "TTY" if x else "NOT",
    )(fn)

    return fn


def setup_output(is_tty: bool) -> MockOutput:
    output = MockOutput(is_tty=is_tty)
    stdout.use_as_output(output)
    return output


@parametrize_stdout_tests
def test_print_if_tty(is_tty: bool, args: tuple, kwargs: dict):

    expected = io.StringIO()
    if is_tty:
        print(*args, **kwargs, file=expected)

    output = setup_output(is_tty=is_tty)

    stdout.print_if_tty(*args, **kwargs)

    assert expected.getvalue() == output.getvalue()


@parametrize_stdout_tests
def test_redirect_stdout_require_tty(is_tty: bool, args: tuple, kwargs: dict):

    expected = io.StringIO()
    if is_tty:
        print(*args, **kwargs, file=expected)

    output = setup_output(is_tty=is_tty)

    with stdout.redirect_stdout(require_tty=True):
        print(*args, **kwargs)

    assert expected.getvalue() == output.getvalue()


@parametrize_stdout_tests
def test_redirect_stdout_no_require_tty(is_tty: bool, args: tuple, kwargs: dict):
    output = setup_output(is_tty=is_tty)

    expected = io.StringIO()
    print(*args, **kwargs, file=expected)

    with stdout.redirect_stdout(require_tty=False):
        print(*args, **kwargs)

    assert expected.getvalue() == output.getvalue()
