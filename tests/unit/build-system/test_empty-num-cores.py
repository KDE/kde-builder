# SPDX-FileCopyrightText: 2021, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

import pytest

from kde_builder_lib.build_context import BuildContext
from kde_builder_lib.build_system.build_system import BuildSystem
from kde_builder_lib.module.module import Module


@pytest.fixture
def mock_buildsystem(monkeypatch):
    BuildSystem.madeArguments = []

    # Defang the build command and just record the args passed to it
    def mock_safe_make(self, optsRef):
        BuildSystem.madeArguments = optsRef["make-options"]
        return {"was_successful": 1}

    monkeypatch.setattr(BuildSystem, "safe_make", mock_safe_make)


def test_empty_numcores(mock_buildsystem):
    """
    Test that empty num-cores settings (which could lead to blank -j being passed
    to the build in some old configs) have their -j filtered out.
    """
    # Set up a shell build system
    ctx = BuildContext()
    module = Module(ctx, "test")
    buildSystem = BuildSystem(module)

    # The -j logic will take off one CPU if you ask for too many so try to ensure
    # test cases don't ask for too many.
    max_cores = os.cpu_count()
    if max_cores is None:
        max_cores = 2

    if max_cores < 2:
        max_cores = 2

    testOption = "make-options"

    testMatrix = [
        ["a b -j", ["a", "b"], "Empty -j removed at end"],
        ["-j a b", ["a", "b"], "Empty -j removed at beginning"],
        ["a b", ["a", "b"], "Opts without -j left alone"],
        ["-j", [], "Empty -j with no other opts removed"],
        ["a -j 17 b", ["a", "-j", "17", "b"], "Numeric -j left alone"],
        ["a -j17 b", ["a", "-j17", "b"], "Numeric -j left alone"],
    ]

    for item in testMatrix:
        testString, resultRef, testName = item
        module.setOption({testOption: testString})
        buildSystem.buildInternal(testOption)
        assert BuildSystem.madeArguments == resultRef, testName

        module.setOption({"num-cores": str(max_cores - 1)})
        buildSystem.buildInternal(testOption)
        assert BuildSystem.madeArguments == ["-j", str(max_cores - 1), *resultRef], f"{testName} with num-cores set"
        module.setOption({"num-cores": ""})

    testOption = "ninja-options"
    module.setOption({"make-options": "not used"})
    module.setOption({"cmake-generator": "Kate - Ninja"})

    for item in testMatrix:
        testString, resultRef, testName = item
        module.setOption({testOption: testString})
        buildSystem.buildInternal(testOption)
        assert BuildSystem.madeArguments == resultRef, testName

        module.setOption({"num-cores": str(max_cores - 1)})
        buildSystem.buildInternal(testOption)
        assert BuildSystem.madeArguments == ['-j', str(max_cores - 1), *resultRef], f"{testName} with num-cores set"
        module.setOption({"num-cores": ""})
