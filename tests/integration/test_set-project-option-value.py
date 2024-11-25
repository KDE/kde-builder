# SPDX-FileCopyrightText: 2018, 2020, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.application import Application
from kde_builder_lib.debug import Debug


def test_set_project_option():
    """
    Test use of --set-project-option-value.
    """
    app = Application("--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --all-config-projects --set-project-option-value module2,tag,fake-tag10 --set-project-option-value setmod2,tag,tag-setmod10".split(" "))
    module_list = app.modules
    assert len(module_list) == 4, "Right number of modules"

    module = [m for m in module_list if f"{m}" == "module2"][0]
    scm = module.scm()
    branch, sourcetype = scm.determine_preferred_checkout_source()

    assert branch == "refs/tags/fake-tag10", "Right tag name"
    assert sourcetype == "tag", "Result came back as a tag"

    module = [m for m in module_list if f"{m}" == "setmod2"][0]
    branch, sourcetype = module.scm().determine_preferred_checkout_source()

    assert branch == "refs/tags/tag-setmod10", "Right tag name (options block from cmdline)"
    assert sourcetype == "tag", "cmdline options block came back as tag"

    assert not module.is_kde_project(), "setmod2 is *not* a \"KDE\" project"
    assert module.full_project_path() == "setmod2", "full_project_path on non-KDE modules returns name"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
