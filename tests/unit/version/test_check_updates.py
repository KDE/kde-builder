# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
from typing import Any

import pytest

from kde_builder.debug import KBLogger
from kde_builder.version import InstallationType
from kde_builder.version import Version


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            {
                "current_ver": "Unknown",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "987fff6",
                "expected_log": "Cannot determine local version to check for updates",
            },
            id="cur_ver_unknown",
        ),
        pytest.param(
            {
                "current_ver": "2026.apr",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "987fff6",
                "expected_log": "Cannot parse local version",
            },
            id="cur_ver_unparsable",
        ),
        pytest.param(
            {
                "current_ver": "9.10",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "987fff6",
                "expected_log": "Your kde-builder version seems to be outdated",
            },
            id="outdated_release_major",
        ),
        pytest.param(
            {
                "current_ver": "26.03",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "987fff6",
                "expected_log": "Your kde-builder version seems to be outdated",
            },
            id="outdated_release_minor",
        ),
        pytest.param(
            {
                "current_ver": "26.04",
                "latest_remote_tag": "v26.04",
                "remote_tag_commit_hash": "1111",
                "latest_remote_hash": "2222",
                "expected_log": "Your kde-builder version seems to be outdated",
            },
            id="on_release_but_outdated_hash",
        ),
        pytest.param(
            {
                "current_ver": "26.04",
                "latest_remote_tag": "v26.04",
                "remote_tag_commit_hash": "1111",
                "latest_remote_hash": "1111",
                "expected_log": "Your kde-builder version is up-to-date",
            },
            id="on_release_and_up-to-date_hash",
        ),
        pytest.param(
            {
                "current_ver": "0.0",
                "latest_remote_tag": "v0.0",  # Means there were no tags
                "remote_tag_commit_hash": None,
                "latest_remote_hash": "1111",
                "expected_log": "Remote repo does not have tags",
            },
            id="on_zero_release_somehow_but_remote_missing_zero_tag",
        ),
        pytest.param(
            {
                "current_ver": "26.04",
                "latest_remote_tag": "v26.04",
                "remote_tag_commit_hash": None,
                "latest_remote_hash": "1111",
                "expected_log": "Cannot determine remote tag commit hash",
            },
            id="on_release_and_undetected_remote_tag_commit_hash_somehow",
        ),
        pytest.param(
            {
                "current_ver": "99.00",
                "latest_remote_tag": "v26.04",
                "remote_tag_commit_hash": None,
                "latest_remote_hash": "1111",
                "expected_log": "Your kde-builder version seems to not yet been released",
            },
            id="on_release_that_is_newer_than_remote_tag_somehow",
        ),
        pytest.param(
            {
                "current_ver": "10.10.post5+g123abc9",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "987fff6",
                "expected_log": "Your kde-builder version seems to be outdated",
            },
            id="outdated_release_major_with_post",
        ),
        pytest.param(
            {
                "current_ver": "26.04.post5+g123abc9",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": None,
                "expected_log": "Cannot determine remote commit hash",
            },
            id="by_hash_but_remote_unknown",
        ),
        pytest.param(
            {
                "current_ver": "26.04.post5+g123abc9",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "123abc9123",
                "expected_log": "Your kde-builder version is up-to-date",
            },
            id="up-to-date_hash",
        ),
        pytest.param(
            {
                "current_ver": "26.04.post5+g123abc9",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "99fed88",
                "expected_log": "Your kde-builder version seems to be outdated",
            },
            id="outdated_hash",
        ),
        pytest.param(
            {
                "current_ver": "26.04.post0+g123abc9.d20261010",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "99fed88",
                "expected_log": "Your kde-builder version seems to be outdated",
            },
            id="release_dirty_outdated_hash",
        ),
        pytest.param(
            {
                "current_ver": "26.04.post0+g123abc9.d20261010",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "123abc9123",
                "expected_log": "Your kde-builder version is up-to-date",
            },
            id="release_dirty_up-to-date_hash",
        ),
        pytest.param(
            {
                "current_ver": "26.04.post5+g123abc9.d20261010",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "99fed88",
                "expected_log": "Your kde-builder version seems to be outdated",
            },
            id="release_dirty_with_post_outdated_hash",
        ),
        pytest.param(
            {
                "current_ver": "26.04.post5+g123abc9.d20261010",
                "latest_remote_tag": "v26.04",
                "latest_remote_hash": "123abc9123",
                "expected_log": "Your kde-builder version is up-to-date",
            },
            id="release_dirty_with_post_up-to-date_hash",
        ),
    ],
)
def test_check_for_updates(monkeypatch, caplog, case: dict[str, Any]):
    logger_app = KBLogger.getLogger("application")
    logger_app.setLevel(logging.INFO)
    logger_app.addHandler(caplog.handler)

    monkeypatch.setattr(Version, "script_version", lambda: case["current_ver"])
    monkeypatch.setattr(Version, "latest_remote_tag", lambda: case["latest_remote_tag"])
    monkeypatch.setattr(Version, "remote_branch_head_commit_hash", lambda: case["latest_remote_hash"])
    monkeypatch.setattr(Version, "remote_tag_commit_hash", lambda x: case["remote_tag_commit_hash"])

    # Do not go with GIT installation route
    monkeypatch.setattr(Version, "detect_installation_type", lambda: InstallationType.UV)

    Version.check_for_updates()

    assert case["expected_log"] in caplog.text


def test_missing_remote_tags(monkeypatch):
    monkeypatch.setattr(Version, "_list_remote_tags", lambda: [])

    lrt = Version.latest_remote_tag()
    assert lrt == "v0.0"
