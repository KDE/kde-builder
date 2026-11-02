#!/bin/bash

# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# This script is used to build documentation locally, to be able to preview it.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DOC_ROOT="${ROOT}/doc"
DOC_BUILD="${DOC_ROOT}/_build"

ARG1="${1:-""}"
if [ "${ARG1}" == "--watch" ] ; then
    uv run --group docs sphinx-autobuild -M html "$DOC_ROOT" "$DOC_BUILD" \
        --port 0 --open-browser
else
    uv run --group docs sphinx-build -M html "$DOC_ROOT" "$DOC_BUILD"
fi
