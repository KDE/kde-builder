# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import argparse

import pytest

from kde_builder.util.clap import extract_bool_arg_or_default
from kde_builder.util.clap import extract_bool_arg_or_none


@pytest.fixture(scope="module")
def namespace() -> argparse.Namespace:
    return argparse.Namespace(
        none=None,
        true=True,
        false=False,
        string="String",
        integer=1,
        namespace=argparse.Namespace(),
    )


@pytest.mark.parametrize(
    argnames="attribute,type_name",
    argvalues=[
        ("string", "str"),
        ("integer", "int"),
        ("namespace", "argparse.Namespace"),
    ],
)
def test_extract_bool_arg_or_default_raises(namespace: argparse.Namespace, attribute: str, type_name: str):
    default = getattr(namespace, attribute)

    with pytest.raises(TypeError) as exc_info:
        extract_bool_arg_or_default(namespace, attribute=attribute, default=default)

    assert exc_info.match(attribute)
    assert exc_info.match(type_name)

    assert "<" not in str(exc_info.value)


@pytest.mark.parametrize(
    argnames="attribute,default,expected",
    argvalues=[
        ("missing", "fallback", "fallback"),
        ("none", "fallback", "fallback"),
        ("true", "fallback", True),
        ("false", "fallback", False),
    ],
)
def test_extract_bool_arg_or_string(namespace: argparse.Namespace, attribute: str, default: str, expected: bool | str):
    assert extract_bool_arg_or_default(namespace, attribute=attribute, default=default) == expected


@pytest.mark.parametrize(
    argnames="attribute,expected",
    argvalues=[
        ("missing", None),
        ("none", None),
        ("true", True),
        ("false", False),
    ],
)
def test_extract_bool_arg_or_none(namespace: argparse.Namespace, attribute: str, expected: bool | None):
    assert extract_bool_arg_or_none(namespace, attribute=attribute) == expected
