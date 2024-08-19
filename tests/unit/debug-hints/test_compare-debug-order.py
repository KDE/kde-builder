# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder_lib.debug_order_hints import DebugOrderHints
from kde_builder_lib.module.module import Module


@pytest.fixture
def mock_module(monkeypatch):
    def mock__init__(self, name, count):
        self.count = count
        self.name = name

    # Redefine `Module` to stub get_persistent_option() results
    def mock_get_persistent_option(self, option):
        assert option == "failure-count", "only the \"failure-count\" should be queried"
        return self.count

    monkeypatch.setattr(Module, "__init__", mock__init__)
    monkeypatch.setattr(Module, "get_persistent_option", mock_get_persistent_option)


def test_debug_order(mock_module):
    """
    Test comparison operation for sorting modules into debug order.
    """
    a1 = Module("A:i-d2-v0-c0", 0)
    b1 = Module("B:i-d1-v1-c0", 0)
    c1 = Module("C:i-d0-v0-c0", 0)
    d1 = Module("D:i-d0-v0-c1", 1)
    e1 = Module("E:i-d0-v1-c0", 0)

    # test: ordering of modules that fail in the same phase based on dependency info
    graph1 = {
        c1.name: {
            "votes": {},
            "deps": {},
            "module": c1
        },
        d1.name: {
            "votes": {},
            "deps": {},
            "module": d1
        },
        e1.name: {
            "votes": {
                a1.name: 1
            },
            "deps": {},
            "module": e1
        },
        b1.name: {
            "votes": {
                a1.name: 1
            },
            "deps": {"foo": 1},
            "module": b1
        },
        a1.name: {
            "votes": {},
            "deps": {
                e1.name: 1,
                b1.name: 1
            },
            "module": a1
        }
    }

    extra_debug_info1 = {
        "phases": {
            a1.name: "install",
            b1.name: "install",
            c1.name: "install",
            d1.name: "install",
            e1.name: "install"
        }
    }

    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(c1, c1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(c1, d1) == -1, "No dependency relation ship, root causes, same popularity: the \"newest\" failure (lower count) should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(c1, e1) == 1, "No dependency relation ship, root causes: the higher popularity should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(c1, b1) == -1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(c1, a1) == -1, "No dependency relation ship: the root cause should be sorted first"

    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(d1, c1) == 1, "No dependency relation ship, root causes, same popularity: the \"newest\" failure (lower count) should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(d1, d1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(d1, e1) == 1, "No dependency relation ship, root causes: the higher popularity should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(d1, b1) == -1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(d1, a1) == -1, "No dependency relation ship: the root cause should be sorted first"

    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(e1, c1) == -1, "No dependency relation ship, root causes: the higher popularity should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(e1, d1) == -1, "No dependency relation ship, root causes: the higher popularity should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(e1, e1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(e1, b1) == -1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(e1, a1) == -1, "Dependencies should be sorted before dependent modules"

    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(b1, c1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(b1, d1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(b1, e1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(b1, b1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(b1, a1) == -1, "Dependencies should be sorted before dependent modules"

    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(a1, c1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(a1, d1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(a1, e1) == 1, "Dependencies should be sorted before dependent modules"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(a1, b1) == 1, "Dependencies should be sorted before dependent modules"
    assert DebugOrderHints._make_comparison_func(graph1, extra_debug_info1)(a1, a1) == 0, "Comparing the same modules should always yield the same relative position"

    # test: ordering of modules that fail in different phases
    p_b1 = Module("build1", 0)
    p_b2 = Module("build2", 0)
    p_i = Module("install", 0)
    p_t = Module("test", 0)
    p_u = Module("update", 0)
    p_x = Module("unknown", 0)

    graph2 = {
        p_b1.name: {
            "votes": {},
            "deps": {},
            "module": p_b1
        },
        p_b2.name: {
            "votes": {},
            "deps": {},
            "module": p_b2
        },
        p_i.name: {
            "votes": {},
            "deps": {},
            "module": p_i
        },
        p_t.name: {
            "votes": {},
            "deps": {},
            "module": p_t
        },
        p_u.name: {
            "votes": {},
            "deps": {},
            "module": p_u
        },
        p_x.name: {
            "votes": {},
            "deps": {},
            "module": p_x
        }
    }

    extra_debug_info2 = {
        "phases": {
            p_b1.name: "build",
            p_b2.name: "build",
            p_i.name: "install",
            p_t.name: "test",
            p_u.name: "update",
            p_x.name: "unknown"
        }
    }

    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b1, p_b1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b1, p_b2) == -1, "Same phase: sort by name for reproducibility"
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b1, p_i) == 1, "Phase ordering: \"build\" should be sorted after \"install\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b1, p_t) == 1, "Phase ordering: \"build\" should be sorted after \"test\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b1, p_u) == -1, "Phase ordering: \"build\" should be sorted before \"update\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b1, p_x) == -1, "Phase ordering: \"build\" should be sorted before unsupported phases"

    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b2, p_b1) == 1, "Same phase: sort by name for reproducibility"
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b2, p_b2) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b2, p_i) == 1, "Phase ordering: \"build\" should be sorted after \"install\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b2, p_t) == 1, "Phase ordering: \"build\" should be sorted after \"test\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b2, p_u) == -1, "Phase ordering: \"build\" should be sorted before \"update\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_b2, p_x) == -1, "Phase ordering: \"build\" should be sorted before unsupported phases"

    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_i, p_b1) == -1, "Phase ordering: \"install\" should be sorted before \"build\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_i, p_b2) == -1, "Phase ordering: \"install\" should be sorted before \"build\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_i, p_i) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_i, p_t) == -1, "Phase ordering: \"install\" should be sorted before \"test\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_i, p_u) == -1, "Phase ordering: \"install\" should be sorted before \"update\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_i, p_x) == -1, "Phase ordering: \"install\" should be sorted before unsupported phases"

    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_t, p_b1) == -1, "Phase ordering: \"test\" should be sorted before \"build\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_t, p_b2) == -1, "Phase ordering: \"test\" should be sorted before \"build\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_t, p_i) == 1, "Phase ordering: \"test\" should be sorted after \"install\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_t, p_t) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_t, p_u) == -1, "Phase ordering: \"test\" should be sorted before \"update\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_t, p_x) == -1, "Phase ordering: \"test\" should be sorted before unsupported phases"

    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_u, p_b1) == 1, "Phase ordering: \"update\" should be sorted after \"build\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_u, p_b2) == 1, "Phase ordering: \"update\" should be sorted after \"build\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_u, p_i) == 1, "Phase ordering: \"update\" should be sorted after \"install\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_u, p_t) == 1, "Phase ordering: \"update\" should be sorted after \"test\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_u, p_u) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_u, p_x) == -1, "Phase ordering: \"update\" should be sorted before unsupported phases"

    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_x, p_b1) == 1, "Phase ordering: unknown phases should be sorted after \"build\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_x, p_b2) == 1, "Phase ordering: unknown phases should be sorted after \"build\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_x, p_i) == 1, "Phase ordering: unknown phases should be sorted after \"install\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_x, p_t) == 1, "Phase ordering: unknown phases should be sorted after \"test\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_x, p_u) == 1, "Phase ordering: unknown phases should be sorted after \"update\""
    assert DebugOrderHints._make_comparison_func(graph2, extra_debug_info2)(p_x, p_x) == 0, "Comparing the same modules should always yield the same relative position"
