#!/bin/bash

pacman --sync --list --quiet > /tmp/pacman-list

KDE_BUILDER_TARGET=(
    "pulseaudio-qt"
    "workspace"
    "dolphin-plugins"
    "ffmpegthumbs"
    "kdegraphics-thumbnailers"
    "kimageformats"
    "kio-fuse"
    "kio-gdrive"
    "kpmcore"
    "spectacle"
    "xwaylandvideobridge"
    "partitionmanager"
    "kde-inotify-survey"
    "kdeconnect-kde"
    "kdenetwork-filesharing"
)

./kde-builder --generate-config
./kde-builder --metadata-only
./kde-builder --query branch | cut -d':' -f1 > /tmp/kde-builder-list-noargs
./kde-builder --query branch "${KDE_BUILDER_TARGET[@]}" | cut -d':' -f1 > /tmp/kde-builder-list-args

cat /tmp/kde-builder-list-noargs /tmp/kde-builder-list-args | sort | uniq > /tmp/kde-builder-list

cd repos
../gen-deps.py /tmp/pacman-list /tmp/kde-builder-list
