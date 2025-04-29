# SPDX-FileCopyrightText: 2025 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import textwrap
import re

"""
In KDE Builder there are places where we want to create a multi-line strings
starting with "\t", and then dedent only whitespaces in them (preserving "\t").

The authors of textwrap did not want such behavior, see
https://github.com/python/cpython/issues/133090.

With this module, we can use textwrap.dedent() like that.
"""

textwrap._whitespace_only_re = re.compile('^ +$', re.MULTILINE)
textwrap._leading_whitespace_re = re.compile('(^ *)[^ \n]', re.MULTILINE)
