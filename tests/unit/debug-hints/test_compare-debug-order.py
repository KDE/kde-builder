# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder.debug_order_hints import DebugOrderHints
from kde_builder.module.module import Module


@pytest.fixture
def mock_module(monkeypatch):
    def mock__init__(self, name, count, failed_phase):
        self.count = count
        self.name = name
        self.failed_phase = failed_phase

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
    a1 = Module("A:i-d2-v0-c0", 0, failed_phase="install")
    b1 = Module("B:i-d1-v1-c0", 0, failed_phase="install")
    c1 = Module("C:i-d0-v0-c0", 0, failed_phase="install")
    d1 = Module("D:i-d0-v0-c1", 1, failed_phase="install")
    e1 = Module("E:i-d0-v1-c0", 0, failed_phase="install")

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
    }

    assert DebugOrderHints(graph1)._compare_debug_order(c1, c1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints(graph1)._compare_debug_order(c1, d1) == -1, "No dependency relation ship, root causes, same popularity: the \"newest\" failure (lower count) should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(c1, e1) == 1, "No dependency relation ship, root causes: the higher popularity should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(c1, b1) == -1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(c1, a1) == -1, "No dependency relation ship: the root cause should be sorted first"

    assert DebugOrderHints(graph1)._compare_debug_order(d1, c1) == 1, "No dependency relation ship, root causes, same popularity: the \"newest\" failure (lower count) should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(d1, d1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints(graph1)._compare_debug_order(d1, e1) == 1, "No dependency relation ship, root causes: the higher popularity should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(d1, b1) == -1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(d1, a1) == -1, "No dependency relation ship: the root cause should be sorted first"

    assert DebugOrderHints(graph1)._compare_debug_order(e1, c1) == -1, "No dependency relation ship, root causes: the higher popularity should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(e1, d1) == -1, "No dependency relation ship, root causes: the higher popularity should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(e1, e1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints(graph1)._compare_debug_order(e1, b1) == -1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(e1, a1) == -1, "Dependencies should be sorted before dependent modules"

    assert DebugOrderHints(graph1)._compare_debug_order(b1, c1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(b1, d1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(b1, e1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(b1, b1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints(graph1)._compare_debug_order(b1, a1) == -1, "Dependencies should be sorted before dependent modules"

    assert DebugOrderHints(graph1)._compare_debug_order(a1, c1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(a1, d1) == 1, "No dependency relation ship: the root cause should be sorted first"
    assert DebugOrderHints(graph1)._compare_debug_order(a1, e1) == 1, "Dependencies should be sorted before dependent modules"
    assert DebugOrderHints(graph1)._compare_debug_order(a1, b1) == 1, "Dependencies should be sorted before dependent modules"
    assert DebugOrderHints(graph1)._compare_debug_order(a1, a1) == 0, "Comparing the same modules should always yield the same relative position"

    # test: ordering of modules that fail in different phases
    p_b1 = Module("build1", 0, failed_phase="build")
    p_b2 = Module("build2", 0, failed_phase="build")
    p_i = Module("install", 0, failed_phase="install")
    p_t = Module("test", 0, failed_phase="test")
    p_u = Module("update", 0, failed_phase="update")
    p_x = Module("unknown", 0, failed_phase="unknown")

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
    }

    assert DebugOrderHints(graph2)._compare_debug_order(p_b1, p_b1) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints(graph2)._compare_debug_order(p_b1, p_b2) == -1, "Same phase: sort by name for reproducibility"
    assert DebugOrderHints(graph2)._compare_debug_order(p_b1, p_i) == 1, "Phase ordering: \"build\" should be sorted after \"install\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_b1, p_t) == 1, "Phase ordering: \"build\" should be sorted after \"test\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_b1, p_u) == -1, "Phase ordering: \"build\" should be sorted before \"update\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_b1, p_x) == -1, "Phase ordering: \"build\" should be sorted before unsupported phases"

    assert DebugOrderHints(graph2)._compare_debug_order(p_b2, p_b1) == 1, "Same phase: sort by name for reproducibility"
    assert DebugOrderHints(graph2)._compare_debug_order(p_b2, p_b2) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints(graph2)._compare_debug_order(p_b2, p_i) == 1, "Phase ordering: \"build\" should be sorted after \"install\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_b2, p_t) == 1, "Phase ordering: \"build\" should be sorted after \"test\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_b2, p_u) == -1, "Phase ordering: \"build\" should be sorted before \"update\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_b2, p_x) == -1, "Phase ordering: \"build\" should be sorted before unsupported phases"

    assert DebugOrderHints(graph2)._compare_debug_order(p_i, p_b1) == -1, "Phase ordering: \"install\" should be sorted before \"build\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_i, p_b2) == -1, "Phase ordering: \"install\" should be sorted before \"build\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_i, p_i) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints(graph2)._compare_debug_order(p_i, p_t) == -1, "Phase ordering: \"install\" should be sorted before \"test\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_i, p_u) == -1, "Phase ordering: \"install\" should be sorted before \"update\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_i, p_x) == -1, "Phase ordering: \"install\" should be sorted before unsupported phases"

    assert DebugOrderHints(graph2)._compare_debug_order(p_t, p_b1) == -1, "Phase ordering: \"test\" should be sorted before \"build\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_t, p_b2) == -1, "Phase ordering: \"test\" should be sorted before \"build\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_t, p_i) == 1, "Phase ordering: \"test\" should be sorted after \"install\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_t, p_t) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints(graph2)._compare_debug_order(p_t, p_u) == -1, "Phase ordering: \"test\" should be sorted before \"update\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_t, p_x) == -1, "Phase ordering: \"test\" should be sorted before unsupported phases"

    assert DebugOrderHints(graph2)._compare_debug_order(p_u, p_b1) == 1, "Phase ordering: \"update\" should be sorted after \"build\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_u, p_b2) == 1, "Phase ordering: \"update\" should be sorted after \"build\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_u, p_i) == 1, "Phase ordering: \"update\" should be sorted after \"install\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_u, p_t) == 1, "Phase ordering: \"update\" should be sorted after \"test\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_u, p_u) == 0, "Comparing the same modules should always yield the same relative position"
    assert DebugOrderHints(graph2)._compare_debug_order(p_u, p_x) == -1, "Phase ordering: \"update\" should be sorted before unsupported phases"

    assert DebugOrderHints(graph2)._compare_debug_order(p_x, p_b1) == 1, "Phase ordering: unknown phases should be sorted after \"build\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_x, p_b2) == 1, "Phase ordering: unknown phases should be sorted after \"build\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_x, p_i) == 1, "Phase ordering: unknown phases should be sorted after \"install\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_x, p_t) == 1, "Phase ordering: unknown phases should be sorted after \"test\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_x, p_u) == 1, "Phase ordering: unknown phases should be sorted after \"update\""
    assert DebugOrderHints(graph2)._compare_debug_order(p_x, p_x) == 0, "Comparing the same modules should always yield the same relative position"
