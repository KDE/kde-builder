# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Command-line argument processing helpers."""

import argparse
from typing import Any


def extract_bool_arg_or_default[T](
    namespace: argparse.Namespace | Any,
    *,
    attribute: str,
    default: T,
) -> bool | T:
    """
    Extract the value of the named attribute from a namespace.

    Args:
        namespace: The object to extract the attribute from.
        attribute: The name of the attribute to extract.
        default: The fallback value.

    Returns:
        The value of the attribute, if it is set on namespace and is not None,
        and default otherwise.

    Raises:
        TypeError: The value of the namespace attribute was not a boolean.
    """
    value = getattr(namespace, attribute, None)

    if value is None:
        return default

    if isinstance(value, bool):
        return value

    type_name = str(value.__class__.__qualname__)
    if hasattr(value, "__module__"):
        type_name = f"{value.__module__}.{type_name}"

    raise TypeError(f"namespace.{attribute} was {type_name} instead of a boolean")


def extract_bool_arg_or_none(
    namespace: argparse.Namespace | Any,
    *,
    attribute: str,
) -> bool | None:
    """
    Extract the value of the named attribute from a namespace.

    Args:
        namespace: The object to extract the attribute from.
        attribute: The name of the attribute to extract.

    Returns:
        The value of the attribute, if it is set on namespace, otherwise None.

    Raises:
        TypeError: The value of the namespace attribute was not a boolean.
    """
    return extract_bool_arg_or_default(namespace, attribute=attribute, default=None)
