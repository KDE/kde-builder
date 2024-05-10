# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from ksblib.DependencyResolver import DependencyResolver


def test_vote_dependencies():
    """
    Test running the full vote for dependencies
    """
    graph1 = {
        "a": {
            "votes": {},
            "allDeps": {
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "b": {
            "votes": {},
            "allDeps": {
                "items": {
                    "c": 1
                }
            }
        },
        "c": {
            "votes": {},
            "allDeps": {
                "items": {}
            }
        },
        #
        # an item might depend through multiple (transitive) paths on the same
        # dependency at the same time
        #
        "d": {
            "votes": {},
            "allDeps": {
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "e": {
            "votes": {},
            "allDeps": {
                "items": {}
            }
        }
    }

    expected1 = {
        "a": {
            "votes": {},
            "allDeps": {
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
            "allDeps": {
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
            "allDeps": {
                "items": {}
            }
        },
        "d": {
            "votes": {},
            "allDeps": {
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "e": {
            "votes": {},
            "allDeps": {
                "items": {}
            }
        }
    }

    DependencyResolver._runDependencyVote(graph1)

    assert graph1 == expected1, "should yield expected votes"
