# SPDX-FileCopyrightText: 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.application import Application
from kde_builder_lib.debug import Debug


def test_kde_projects():
    """
    Verify that test kde-project data still results in workable build.
    """
    # The file has a module-set that only refers to juk but should expand to
    # kcalc juk in that order
    args = "--pretend --rc-file tests/integration/fixtures/kde-projects/kde-builder-with-deps.yaml --all-config-projects".split(" ")
    app = Application(args)
    module_list = app.modules

    assert len(module_list) == 3, "Right number of modules (include-dependencies)"
    assert module_list[0].name == "kcalc", "Right order: kcalc before juk (test dep data)"
    assert module_list[1].name == "juk", "Right order: juk after kcalc (test dep data)"
    assert module_list[2].name == "kde-builder", "Right order: dolphin after juk (implicit order)"
    assert module_list[0].get_option("tag") == "tag-setmod2", "options block works for indirect reference to kde-projects module"
    assert module_list[0].get_option("cmake-generator") == "Ninja", "Global opts seen even with other options"
    assert module_list[1].get_option("cmake-generator") == "Make", "options block works for kde-projects module-set"
    assert module_list[1].get_option("cmake-options") == "-DSET_FOO:BOOL=ON", "module options block can override set options block"
    assert module_list[2].get_option("cmake-generator") == "Make", "options block works for kde-projects module-set after options"
    assert module_list[2].get_option("cmake-options") == "-DSET_FOO:BOOL=ON", "module-set after options can override options block"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
