# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import sys


def setproctitle(title: str):
    # Calling setproctitle after fork in macOS is crashy.
    # See https://github.com/dvarrazzo/py-setproctitle/issues/127
    if sys.platform == "darwin":
        return

    try:
        import setproctitle
        setproctitle.setproctitle(title)
    except ImportError:
        pass
