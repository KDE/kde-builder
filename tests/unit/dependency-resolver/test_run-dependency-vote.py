# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.dependency_resolver import DependencyResolver


def test_vote_dependencies():
    """
    Test running the full vote for dependencies.
    """
    graph1 = {
        "a": {
            "votes": {},
            "all_deps": {
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "b": {
            "votes": {},
            "all_deps": {
                "items": {
                    "c": 1
                }
            }
        },
        "c": {
            "votes": {},
            "all_deps": {
                "items": {}
            }
        },
        #
        # an item might depend through multiple (transitive) paths on the same
        # dependency at the same time
        #
        "d": {
            "votes": {},
            "all_deps": {
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "e": {
            "votes": {},
            "all_deps": {
                "items": {}
            }
        }
    }

    expected1 = {
        "a": {
            "votes": {},
            "all_deps": {
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "b": {
            "votes": {
                "a": 1,
                "d": 1
            },
            "all_deps": {
                "items": {
                    "c": 1
                }
            }
        },
        "c": {
            "votes": {
                "a": 1,
                "b": 1,
                "d": 1
            },
            "all_deps": {
                "items": {}
            }
        },
        "d": {
            "votes": {},
            "all_deps": {
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "e": {
            "votes": {},
            "all_deps": {
                "items": {}
            }
        }
    }

    DependencyResolver._run_dependency_vote(graph1)

    assert graph1 == expected1, "should yield expected votes"
