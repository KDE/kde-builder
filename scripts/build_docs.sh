#!/bin/bash

# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# This script is used to build documentation locally, to be able to preview it.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DOC_ROOT="${ROOT}/doc"

sphinx-build -M html "$DOC_ROOT" "$DOC_ROOT"/_build/
