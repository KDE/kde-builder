from ksblib.DependencyResolver import DependencyResolver


def test_vote_for_dependencies():
    """
    Test running the full vote for dependencies
    """
    graph1 = {
        "a": {
            "deps": {
                "b": 1
            },
            "allDeps": {}
        },
        "b": {
            "deps": {
                "c": 1
            },
            "allDeps": {}
        },
        "c": {
            "deps": {},
            "allDeps": {}
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
            "allDeps": {}
        },
        "e": {
            "deps": {},
            "allDeps": {}
        }
    }
    
    expected1 = {
        "a": {
            "deps": {
                "b": 1
            },
            "allDeps": {
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
            "allDeps": {
                "done": 1,
                "items": {
                    "c": 1
                }
            }
        },
        "c": {
            "deps": {},
            "allDeps": {
                "done": 1,
                "items": {}
            }
        },
        "d": {
            "deps": {
                "b": 1,
                "c": 1
            },
            "allDeps": {
                "done": 1,
                "items": {
                    "b": 1,
                    "c": 1
                }
            }
        },
        "e": {
            "deps": {},
            "allDeps": {
                "done": 1,
                "items": {}
            }
        }
    }
    
    assert DependencyResolver._copyUpDependencies(graph1) == expected1, "should copy up dependencies correctly"
