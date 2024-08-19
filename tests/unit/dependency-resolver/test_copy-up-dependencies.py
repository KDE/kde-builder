# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.dependency_resolver import DependencyResolver


def test_vote_for_dependencies():
    """
    Test running the full vote for dependencies.
    """
    graph1 = {
        "a": {
            "deps": {
                "b": 1
            },
            "all_deps": {}
        },
        "b": {
            "deps": {
                "c": 1
            },
            "all_deps": {}
        },
        "c": {
            "deps": {},
            "all_deps": {}
        },
        #
        # an item might depend through multiple (transitive) paths on the same
        # dependency at the same time
        #
        "d": {
            "deps": {
                "b": 1,
                "c": 1
            },
            "all_deps": {}
        },
        "e": {
            "deps": {},
            "all_deps": {}
        }
    }

    expected1 = {
        "a": {
            "deps": {
                "b": 1
            },
            "all_deps": {
                "done": 1,
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "b": {
            "deps": {
                "c": 1
            },
            "all_deps": {
                "done": 1,
                "items": {
                    "c": 1
                }
            }
        },
        "c": {
            "deps": {},
            "all_deps": {
                "done": 1,
                "items": {}
            }
        },
        "d": {
            "deps": {
                "b": 1,
                "c": 1
            },
            "all_deps": {
                "done": 1,
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "e": {
            "deps": {},
            "all_deps": {
                "done": 1,
                "items": {}
            }
        }
    }

    assert DependencyResolver._copy_up_dependencies(graph1) == expected1, "should copy up dependencies correctly"
