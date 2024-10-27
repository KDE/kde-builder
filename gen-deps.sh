#!/bin/bash

pacman --sync --list --quiet > /tmp/pacman-list

./kde-builder --generate-config
./kde-builder --metadata-only
./kde-builder --query branch | cut -d':' -f1 > /tmp/kde-builder-list

cd repos
../gen-deps.py /tmp/pacman-list /tmp/kde-builder-list