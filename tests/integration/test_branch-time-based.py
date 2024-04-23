# SPDX-FileCopyrightText: 2018 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from ksblib.Application import Application
from ksblib.Updater.Git import Updater_Git
from ksblib.Debug import Debug


def test_tag_names_based_on_time():
    """
    Test tag names based on time
    """
    app = Application(["--pretend", "--rc-file", "tests/integration/fixtures/branch-time-based/kdesrc-buildrc"])
    moduleList = app.modules
    assert len(moduleList) == 3, "Right number of modules"

    for mod in moduleList:
        scm = mod.scm()
        assert isinstance(scm, Updater_Git)

        branch, sourcetype = scm._determinePreferredCheckoutSource()
        assert branch == "master@{3 weeks ago}", "Right tag name"
        assert sourcetype == "tag", "Result came back as a tag with detached HEAD"
        assert sourcetype == "tag", "Result came back as a tag with detached HEAD"

    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
