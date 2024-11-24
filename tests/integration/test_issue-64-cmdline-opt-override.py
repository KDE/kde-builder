# SPDX-FileCopyrightText: 2021 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Global options in the rc-file can be overridden on the command line just by
# using their option name in a cmdline argument (as long as the argument isn't
# already allocated, that is).
#
# This ensures that global options overridden in this fashion are applied
# before the rc-file is read.
#
# See issue #64

from kde_builder_lib.application import Application
from kde_builder_lib.debug import Debug


def test_no_cmdline_override():
    # The issue used num-cores as an example, but should work just as well with make-options

    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --all-config-projects".split(" ")
    app = Application(args)
    module_list = app.modules

    assert app.context.get_option("num-cores") == "8", "No cmdline option leaves num-cores value alone"

    assert len(module_list) == 4, "Right number of modules"
    assert module_list[0].name == "setmod1", "mod list[0] == setmod1"
    assert module_list[0].get_option("make-options") == "-j4", "make-options base value proper pre-override"

    assert module_list[3].name == "module2", "mod list[3] == module2"
    assert module_list[3].get_option("make-options") == "-j 8", "module-override make-options proper pre-override"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton


def test_cmdline_makeoption():
    # We can't seem to assign -j3 as Getopt::Long will try to understand the option and fail
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --all-config-projects --make-options j3".split(" ")

    app = Application(args)
    module_list = app.modules

    assert app.context.get_option("num-cores") == "8", "No cmdline option leaves num-cores value alone"

    assert len(module_list) == 4, "Right number of modules"
    assert module_list[0].name == "setmod1", "mod list[0] == setmod1"
    assert module_list[0].get_option("make-options") == "j3", "make-options base value proper post-override"

    # Policy discussion: Should command line options override *all* instances
    # of an option in kde-builder.yaml? Historically the answer has deliberately
    # been yes, so that's the behavior we enforce.
    assert module_list[3].name == "module2", "mod list[3] == module2"
    assert module_list[3].get_option("make-options") == "j3", "module-override make-options proper post-override"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton


def test_cmdline_numcores():
    # add another test of indirect option value setting
    args = "--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --all-config-projects --num-cores=5".split(" ")  # 4 is default, 8 is in rc-file, use something different

    app = Application(args)
    module_list = app.modules

    assert app.context.get_option("num-cores") == "5", "Updated cmdline option changes global value"

    assert len(module_list) == 4, "Right number of modules"
    assert module_list[0].name == "setmod1", "mod list[0] == setmod1"
    assert module_list[0].get_option("make-options") == "-j4", "make-options base value proper post-override (indirect value)"

    assert module_list[3].name == "module2", "mod list[3] == module2"
    assert module_list[3].get_option("make-options") == "-j 5", "module-override make-options proper post-override (indirect value)"
    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
