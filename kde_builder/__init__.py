# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
A tool to streamline the process of setting up and maintaining development environment for KDE software.
"""

import os

KB_PACKAGE_DIR: str = os.path.abspath(os.path.dirname(__file__))
KB_REPO_DIR: str = os.path.normpath(KB_PACKAGE_DIR + "/..")
