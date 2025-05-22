# SPDX-FileCopyrightText: 2025 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.application import Application
from kde_builder_lib.debug import Debug


def test_repository_resolution():
    """
    Verify that "repository" option is resolved correctly for first-party and third-party projects.
    """
    args = "--pretend --rc-file tests/integration/fixtures/kde-projects/kde-builder-repository-resolving.yaml --all-config-projects".split(" ")
    app = Application(args)
    module_list = app.modules
    for module in module_list:
        module.set_resolved_repository()

    assert len(module_list) == 12, "Right number of modules (all defined in config)"

    assert module_list[0].name == "kcalc", "Right order: kcalc before juk (test dep data)"
    assert module_list[1].name == "juk", "Right order: juk after kcalc (test dep data), and as in config order"
    assert module_list[2].name == "konsole", "Right order: as in config order"
    assert module_list[3].name == "dolphin", "Right order: as in config order, and dolphin after konsole (test dep data)"
    assert module_list[4].name == "kde-builder", "Right order: as in config order, and kde-builder after juk (test dep data)"
    assert module_list[5].name == "gnome-calc", "Right order: third party project (ordered as placed in config)"
    assert module_list[6].name == "gnome-texteditor", "Right order: third party project (ordered as placed in config)"
    assert module_list[7].name == "gnome-imageeditor", "Right order: third party project (ordered as placed in config)"
    assert module_list[8].name == "gnome-audioeditor", "Right order: third party project (ordered as placed in config)"
    assert module_list[9].name == "gnome-videoeditor", "Right order: third party project (ordered as placed in config)"
    assert module_list[10].name == "gnome-binaryeditor", "Right order: third party project (ordered as placed in config)"
    assert module_list[11].name == "elisa", "Right order: kde project expanded from group (ordered as placed in config)"

    assert module_list[0].get_option("#resolved-repository") == "kde:kcalc.git", "First party project, and explicitly using \"kde-projects\" magic value"
    assert module_list[1].get_option("#resolved-repository") == "kde:juk.git", "First party project, and implicitly using \"kde-projects\" magic value"
    assert module_list[2].get_option("#resolved-repository") == "https://github.com/torvalds/konsole", "First party project, but using one of defined git-repository-bases"
    assert module_list[3].get_option("#resolved-repository") == "", "First party project, but set empty repository"
    assert module_list[4].get_option("#resolved-repository") == "https://example.com/kde-builder-fork", "First party project, and set to non-empty, but not magic, and not from git-repository-base"
    assert module_list[5].get_option("#resolved-repository") == "", "Third party project, but implicitly using \"kde-projects\" magic value"
    assert module_list[6].get_option("#resolved-repository") == "", "Third party project, but explicitly using \"kde-projects\" magic value"
    assert module_list[7].get_option("#resolved-repository") == "https://github.com/torvalds/gnome-imageeditor", "Third party project, and using one of defined git-repository-bases"
    assert module_list[8].get_option("#resolved-repository") == "", "Third party project, but set empty repository"
    assert module_list[9].get_option("#resolved-repository") == "https://example.com/gnome-text-editor", "Third party project, and set to non-empty, but not magic and not from git-repository-base - assumed full url"
    assert module_list[10].get_option("#resolved-repository") == "gnome-gh", "Third party project, and set to non-empty, but not magic and not from git-repository-base - assumed repository base, but not defined"
    assert module_list[11].get_option("#resolved-repository") == "kde:elisa.git", "Group implicitly using \"kde-projects\" magic value, which is inherited by projects expanded from it"

    Debug().set_pretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
