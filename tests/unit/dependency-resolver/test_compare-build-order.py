# SPDX-FileCopyrightText: 2020 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder_lib.dependency_resolver import DependencyResolver
from kde_builder_lib.module.module import Module


@pytest.fixture
def mock_module_from_attrs(monkeypatch):
    def mock__init__(self, **kwargs):
        self.name = kwargs.get("name", None)
        self.create_id = kwargs.get("create_id", 0)

    monkeypatch.setattr(Module, "__init__", mock__init__)


def test_comparison(mock_module_from_attrs):
    """
    Test comparison operation for sorting modules into build order.
    """
    graph1 = {
        "a": {
            "votes": {
                "b": 1,
                "d": 1
            },
            "module": Module(name="a"),
        },
        "b": {
            "votes": {},
            "module": Module(name="b"),
        },
        "c": {
            "votes": {
                "d": 1
            },
            "module": Module(name="c"),
        },
        "d": {
            "votes": {},
            "module": Module(name="d"),
        },

        "e": {  # Here to test sorting by rc-file order
            "votes": {
                "b": 1,
                "d": 1,
            },
            "module": Module(name="e", create_id=2),
        },
        "f": {  # Identical to "e" except it's simulated earlier in rc-file
            "votes": {
                "b": 1,
                "d": 1,
            },
            "module": Module(name="f", create_id=1),
        },
    }

    # Test that tests are symmetric e.g. a > b => b < a. This permits us to only manually
    # test one pair of these tests now that the test matrix is growing.
    for left in ["a", "b", "c", "d", "e", "f"]:
        for right in ["a", "b", "c", "d", "e", "f"]:
            res = DependencyResolver.make_comparison_func(graph1)(left, right)

            if left == right:
                assert res == 0, f"\"{left}\" should be sorted at the same position as itself"
            else:
                assert abs(res) == 1, f"Different module items (\"{left}\" and \"{right}\") compare to 1 or -1 (but not 0)"
                assert DependencyResolver.make_comparison_func(graph1)(right, left) == -res, f"Swapping order of operands should negate the result (\"{right}\" vs \"{left}\")"

    assert DependencyResolver.make_comparison_func(graph1)("a", "b") == -1, "\"a\" should be sorted before \"b\" by dependency ordering"
    assert DependencyResolver.make_comparison_func(graph1)("a", "c") == -1, "\"a\" should be sorted before \"c\" by vote ordering"
    assert DependencyResolver.make_comparison_func(graph1)("a", "d") == -1, "\"a\" should be sorted before \"d\" by dependency ordering"
    assert DependencyResolver.make_comparison_func(graph1)("a", "e") == -1, "\"a\" should be sorted before \"e\" by lexicographic ordering"
    assert DependencyResolver.make_comparison_func(graph1)("a", "f") == -1, "\"a\" should be sorted before \"f\" by lexicographic ordering"

    assert DependencyResolver.make_comparison_func(graph1)("b", "c") == 1, "\"b\" should be sorted after \"c\" by vote ordering"
    assert DependencyResolver.make_comparison_func(graph1)("b", "d") == -1, "\"b\" should be sorted before \"d\" by lexicographic ordering"
    assert DependencyResolver.make_comparison_func(graph1)("b", "e") == 1, "\"b\" should be sorted after \"e\" by dependency ordering"
    assert DependencyResolver.make_comparison_func(graph1)("b", "f") == 1, "\"b\" should be sorted after \"f\" by dependency ordering"

    assert DependencyResolver.make_comparison_func(graph1)("c", "d") == -1, "\"c\" should be sorted before \"d\" by dependency ordering"
    assert DependencyResolver.make_comparison_func(graph1)("c", "e") == 1, "\"c\" should be sorted after \"e\" by vote ordering"
    assert DependencyResolver.make_comparison_func(graph1)("c", "f") == 1, "\"c\" should be sorted after \"f\" by vote ordering"

    assert DependencyResolver.make_comparison_func(graph1)("d", "e") == 1, "\"d\" should be sorted after \"e\" by dependency ordering"
    assert DependencyResolver.make_comparison_func(graph1)("d", "f") == 1, "\"d\" should be sorted after \"f\" by dependency ordering"

    assert DependencyResolver.make_comparison_func(graph1)("e", "f") == 1, "\"e\" should be sorted after \"f\" by rc-file ordering"
