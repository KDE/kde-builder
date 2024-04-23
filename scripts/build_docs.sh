#!/bin/bash

# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# This script is used to build documentation locally, to be able to preview it.

DOC_ROOT="../doc"

sphinx-build -M html "$DOC_ROOT" "$DOC_ROOT"/_build/
