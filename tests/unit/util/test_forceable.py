# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from typing import Any

import pytest

from kde_builder.util.forceable import Forceable
from kde_builder.util.forceable import ForceableBool


def test_assign_when_already_forced():
    it = Forceable[int](1, forced=True)
    assert it.value == 1

    it.value = 2
    assert it.value == 1


def test_assign_when_not_forced():
    it = Forceable[int](1, forced=False)
    assert it.value == 1

    it.value = 2
    assert it.value == 2


def test_set_unforced_when_already_forced():
    it = Forceable[int](1, forced=True)
    assert it.value == 1

    assert not it.set(2)
    assert it.value == 1


def test_set_unforced_when_not_forced():
    it = Forceable[int](1, forced=False)
    assert it.value == 1

    assert it.set(2)
    assert it.value == 2


def test_set_forced_when_already_forced():
    it = Forceable[int](1, forced=True)
    assert it.value == 1

    assert it.set(2, force=True)
    assert it.value == 2


def test_set_forced_when_not_forced():
    it = Forceable[int](1, forced=False)
    assert it.value == 1

    assert it.set(2, force=True)
    assert it.value == 2


@pytest.mark.parametrize(
    argnames="value",
    argvalues=["Yes", "no", 1, 0, None, Any],
    ids=lambda x: f"value={x}",
)
@pytest.mark.parametrize(
    argnames="forced",
    argvalues=[True, False],
    ids=lambda x: f"forced={x}",
)
@pytest.mark.parametrize(
    argnames="force",
    argvalues=[True, False],
    ids=lambda x: f"force={x}",
)
def test_forceable_bool_set_checked_raises_if_not_bool(value: Any, forced: bool, force: bool):
    it = ForceableBool("%%%%", False, forced=forced)

    with pytest.raises(TypeError):
        it.set_checked(value, force=force)


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[True, False],
    ids=lambda x: f"value={x}",
)
@pytest.mark.parametrize(
    argnames="forced",
    argvalues=[True, False],
    ids=lambda x: f"forced={x}",
)
@pytest.mark.parametrize(
    argnames="force",
    argvalues=[True, False],
    ids=lambda x: f"force={x}",
)
def test_forceable_bool_set_checked_accepts_own_value(value: Any, forced: bool, force: bool):
    it = ForceableBool("%%%%", value, forced=forced)

    # We set it to the same value, so changed should always be false.
    assert not it.set_checked(it.value, force=force)
    assert it.value == value
    assert it.forced == (force or forced)


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[True, False],
    ids=lambda x: f"value={x}",
)
@pytest.mark.parametrize(
    argnames="forced",
    argvalues=[True, False],
    ids=lambda x: f"forced={x}",
)
@pytest.mark.parametrize(
    argnames="force",
    argvalues=[True, False],
    ids=lambda x: f"force={x}",
)
def test_forceable_bool_set_checked_accepts_other_value(value: Any, forced: bool, force: bool):
    it = ForceableBool("%%%%", not value, forced=forced)

    should_change = force or not forced

    assert it.set_checked(value, force=force) == should_change
    assert it.forced == (forced or force)
    if should_change:
        assert it.value == value
    else:
        assert it.value != value
