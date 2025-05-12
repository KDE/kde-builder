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


@pytest.fixture
def graph1(mock_module_from_attrs):
    graph = {
        "a": {
            "votes": {
                "b": 1,
                "d": 1
            },
            "build": 1,
            "module": Module(name="a", create_id=1),
        },
        "b": {
            "votes": {},
            "build": 1,
            "module": Module(name="b", create_id=1),
        },
        "c": {
            "votes": {
                "d": 1
            },
            "build": 1,
            "module": Module(name="c", create_id=1),
        },
        "d": {
            "votes": {},
            "build": 1,
            "module": Module(name="d", create_id=1),
        },
        "e": {
            "votes": {},
            "build": 1,
            "module": Module(name="e", create_id=2),  # Should come after everything else
        },
    }
    return graph


def test_proper_order(graph1):
    """
    Test sorting modules into build order.
    """
    expected1 = [graph1[item]["module"] for item in ["a", "c", "b", "d", "e"]]
    actual1 = DependencyResolver.sort_modules_into_build_order(graph1)

    assert actual1 == expected1, "should sort modules into the proper build order"


def test_key_order_does_not_matter(graph1):
    # use some random key strokes for names:
    # unlikely to yield keys in equivalent order as $graph1: key order *should not matter*
    graph2 = {
        "avdnrvrl": graph1["c"],
        "lexical1": graph1["b"],
        "lexicla3": graph1["e"],
        "nllfmvrb": graph1["a"],
        "lexical2": graph1["d"],
    }

    # corresponds to same order as the test above
    expected2 = [graph2[item]["module"] for item in ["nllfmvrb", "avdnrvrl", "lexical1", "lexical2", "lexicla3"]]
    actual2 = DependencyResolver.sort_modules_into_build_order(graph2)

    assert actual2 == expected2, "key order should not matter for build order"


def test_not_built_omitted(graph1):
    graph3 = {
        "a": graph1["a"],
        "b": graph1["b"],
        "c": graph1["c"],
        "d": graph1["d"],
        "e": graph1["e"],
    }
    graph3["a"]["build"] = 0
    graph3["b"]["module"] = None  # Empty module blocks should be treated as build == 0

    expected3 = [graph3[item]["module"] for item in ("c", "d", "e")]
    actual3 = DependencyResolver.sort_modules_into_build_order(graph3)

    assert actual3 == expected3, "modules that are not to be built should be omitted"
