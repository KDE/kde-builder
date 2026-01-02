# SPDX-FileCopyrightText: 2012, 2013 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from .kde_project import UpdaterKDEProject
from ..debug import Debug
from ..ipc.null import IPCNull


class UpdaterKDEProjectMetadata(UpdaterKDEProject):
    """
    Updater used only to specifically update the "repo-metadata" module used for storing dependency information, among other things.

    Note: 2020-06-20 the previous "kde-build-metadata" module was combined into
    the "repo-metadata" module, under the "/dependencies" folder.
    """

    @staticmethod
    # @override(check_signature=False)
    def name() -> str:
        return "metadata"

    # @override(check_signature=False)
    def update_internal(self, ipc=IPCNull()) -> None:
        if Debug().is_testing():
            return

        super().update_internal(ipc)
