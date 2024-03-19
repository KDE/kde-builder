#!/bin/bash

# This script is used to build documentation locally, to be able to preview it.

DOC_ROOT="../doc"

sphinx-build -M html "$DOC_ROOT" "$DOC_ROOT"/_build/
