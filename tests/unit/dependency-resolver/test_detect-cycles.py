# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

from ksblib.DependencyResolver import DependencyResolver


def test_trivial_cycle():
    """
    Test detection of dependency cycles in a dependency graph
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

    assert DependencyResolver._detectDependencyCycle(graph1, "a", "a"), "should detect 'trivial' cycles of an item to itself"


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

    assert DependencyResolver._detectDependencyCycle(graph2, "a", "a"), "should detect cycle: a -> b -> a"
    assert DependencyResolver._detectDependencyCycle(graph2, "b", "b"), "should detect cycle: b -> a -> b"


def test_no_cycles():
    # no cycles, should therefore not 'detect' any false positives
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

    assert not DependencyResolver._detectDependencyCycle(graph3, "a", "a"), "should not report false positives for 'a'"
    assert not DependencyResolver._detectDependencyCycle(graph3, "b", "b"), "should not report false positives for 'b'"
