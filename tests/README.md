<!--
    SPDX-License-Identifier: CC0-1.0
    SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
-->

# Tests

KDE Builder uses `pytest` for testing.

## Running tests

You need to add the sources root to the `PYTHONPATH` and run `pytest`:

```bash
cd kde-builder
PYTHONPATH="$PYTHONPATH:$(pwd)" pytest
```
