# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

import kde_builder


@pytest.fixture(autouse=True)
def reset_pretending():
    """
    Disable pretending after test, to not influence on other tests.
    """
    yield
    kde_builder.is_pretending = False
