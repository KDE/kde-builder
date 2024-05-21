# SPDX-FileCopyrightText: 2018, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from ksblib.Application import Application
from ksblib.Debug import Debug


def test_cmdline_selector_not_eaten():
    """
    Checks that we don't inadvertently eat non-option arguments in cmdline
    processing, which happened with some cmdline options that were inadvertently
    handled both directly in _readCommandLineOptionsAndSelectors and indirectly
    via being in BuildContext default Global Flags

    See bug 402509 -- https://bugs.kde.org/show_bug.cgi?id=402509
    """
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kdesrc-buildrc --stop-on-failure setmod3".split(" ")

    app = Application(args)
    moduleList = app.modules

    assert len(moduleList) == 1, "Right number of modules (just one)"
    assert moduleList[0].name == "setmod3", "mod list[2] == setmod3"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
