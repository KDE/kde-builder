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

    "phonon-vlc"
    "kaccounts-providers"
    "signon-kwallet-extension"
)

./kde-builder --generate-config
./kde-builder --metadata-only
./kde-builder --query branch > /tmp/kde-builder-list-noargs
./kde-builder --query branch "${KDE_BUILDER_TARGET[@]}" > /tmp/kde-builder-list-args

./kde-builder --query branch --branch-group kf5-qt5 > /tmp/kde-builder-list-noargs-kf5-qt5
./kde-builder --query branch --branch-group kf5-qt5 "${KDE_BUILDER_TARGET[@]}" > /tmp/kde-builder-list-args-kf5-qt5

cat /tmp/kde-builder-list-noargs /tmp/kde-builder-list-args | sort | uniq > /tmp/kde-builder-list
cat /tmp/kde-builder-list-noargs-kf5-qt5 /tmp/kde-builder-list-args-kf5-qt5 | sort | uniq > /tmp/kde-builder-list-kf5-qt5

cd repos
../gen-deps.py /tmp/pacman-list /tmp/kde-builder-list /tmp/kde-builder-list-kf5-qt5 > deps.yaml
