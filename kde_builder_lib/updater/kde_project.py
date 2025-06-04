# SPDX-FileCopyrightText: 2012, 2013, 2017 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from .updater import Updater


class UpdaterKDEProject(Updater):
    """
    An update class for KDE Project modules (i.e. those that use "repository kde-projects" in the configuration file).
    """

    @staticmethod
    # @override(check_signature=False)
    def name() -> str:
        return "proj"

    def _resolve_branch_group(self, branch_group: str) -> str | None:
        """
        Resolve the requested branch-group for this Updater's module.

        Returns the required branch name, or None if none is set.
        """
        module = self.module

        # If we're using a logical group we need to query the global build context
        # to resolve it.
        ctx = module.context
        resolver = ctx.module_branch_group_resolver()
        module_path = module.full_project_path()
        return resolver.find_module_branch(module_path, branch_group)

    @staticmethod
    # @override(check_signature=False)
    def _is_plausible_existing_remote(name: str, url: str, configured_url: str) -> bool:
        return url == configured_url or url.startswith("kde:")

    @staticmethod
    # @override
    def is_push_url_managed() -> bool:
        return True
