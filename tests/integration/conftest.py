# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from kde_builder.debug import Debug


@pytest.fixture(autouse=True)
def reset_pretending():
    """
    Disable pretending after test, to not influence on other tests, because Debug is singleton.
    """
    yield
    Debug().set_pretending(False)
