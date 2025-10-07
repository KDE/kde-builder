# SPDX-FileCopyrightText: 2018 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.os_support import OSSupport


def test_ossupport():
    """
    Test OSSupport.
    """
    # Unit test of _read_os_release
    kv_pairs = OSSupport._read_os_release("tests/integration/fixtures/os-release")
    assert len(kv_pairs) == 4, "Right number of key/value pairs"
    opts = {kvPair[0]: kvPair[1] for kvPair in kv_pairs.items()}
    assert opts["NAME"] == "Totally Valid Name", "Right NAME"
    assert opts["ID"] == "kde-builder", "Right ID"
    assert opts["ID_LIKE"] == "sabayon gentoo-hardened gentoo", "Right ID_LIKE"
    assert opts["SPECIAL"] == "$VAR \\ ` \" is set", "Right SPECIAL"

    # Use tests
    os = OSSupport("tests/integration/fixtures/os-release")
    assert isinstance(os, OSSupport)

    os.supported_os_ids = ["arch", "kde-builder", "sabayon"]
    assert os._find_best_distro_match() == "kde-builder", "ID preferred"

    os.supported_os_ids = ["ubuntu", "fedora", "gentoo"]
    assert os._find_best_distro_match() == "gentoo", "ID_LIKE respected"

    os.supported_os_ids = ["fedora", "gentoo", "gentoo-hardened", "sabayon"]
    assert os._find_best_distro_match() == "sabayon", "ID_LIKE preference order proper"

    assert os.ID == "kde-builder", "Right ID"
