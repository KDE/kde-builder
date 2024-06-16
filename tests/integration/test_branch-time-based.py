# SPDX-FileCopyrightText: 2018 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.application import Application
from kde_builder_lib.debug import Debug
from kde_builder_lib.updater.updater import Updater


def test_tag_names_based_on_time():
    """
    Test tag names based on time
    """
    app = Application(["--pretend", "--rc-file", "tests/integration/fixtures/branch-time-based/kdesrc-buildrc"])
    moduleList = app.modules
    assert len(moduleList) == 3, "Right number of modules"

    for mod in moduleList:
        scm = mod.scm()
        assert isinstance(scm, Updater)

        branch, sourcetype = scm._determine_preferred_checkout_source()
        assert branch == "master@{3 weeks ago}", "Right tag name"
        assert sourcetype == "tag", "Result came back as a tag with detached HEAD"
        assert sourcetype == "tag", "Result came back as a tag with detached HEAD"

    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
