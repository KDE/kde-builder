# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.dependency_resolver import DependencyResolver


def test_trivial_cycle():
    """
    Test detection of dependency cycles in a dependency graph.
    """
    # trivial cycle a -> a
    graph1 = {
        "a": {
            "deps": {
                "a": {}
            }
        },
        "b": {
            "deps": {}
        }
    }

    dr = DependencyResolver(None)
    dr.dependency_graph = graph1
    assert dr._detect_dependency_cycle("a", "a"), "should detect \"trivial\" cycles of an item to itself"


def test_cycle_to_self():
    graph2 = {
        "a": {
            "deps": {
                "b": {}
            }
        },
        "b": {
            "deps": {
                "a": {}
            }
        }
    }

    dr = DependencyResolver(None)
    dr.dependency_graph = graph2
    assert dr._detect_dependency_cycle("a", "a"), "should detect cycle: a -> b -> a"
    assert dr._detect_dependency_cycle("b", "b"), "should detect cycle: b -> a -> b"


def test_no_cycles():
    # no cycles, should therefore not "detect" any false positives
    graph3 = {
        "a": {
            "deps": {
                "b": {}
            }
        },
        "b": {
            "deps": {}
        }
    }

    dr = DependencyResolver(None)
    dr.dependency_graph = graph3
    assert not dr._detect_dependency_cycle("a", "a"), "should not report false positives for \"a\""
    assert not dr._detect_dependency_cycle("b", "b"), "should not report false positives for \"b\""
