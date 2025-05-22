# SPDX-FileCopyrightText: 2019 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from .module_set import ModuleSet
from ..build_context import BuildContext
from ..build_system.qt5 import BuildSystemQt5
from ..module.module import Module
from ..util.util import Util


class ModuleSetQt5(ModuleSet):
    """
    Represents a collection of Qt5 source code modules.

    They are collectively kept up to date by Qt's init-repository script. This module set is
    essentially used to make sure that generated Modules use proper scm()
    and buildSystems()

    Use of this module-set is controlled by the "repository" option being set to
    the magic value "qt-projects", just as "kde-projects" is used for KDE.
    """

    def _make_qt5_module(self, ctx: BuildContext) -> Module:
        Util.assert_isa(ctx, BuildContext)

        new_module = Module(ctx, "Qt5")

        self._initialize_new_module(new_module)

        # Repo URL to the Qt5 "supermodule" that contains the documented
        # init-repository script.
        # See https://wiki.qt.io/Building_Qt_5_from_Git
        new_module.set_scm_type("qt5")
        new_module.set_build_system(BuildSystemQt5(new_module))

        # Convert the use-projects/ignore-projects entries into a form appropriate
        # for init-repository's module-subset option.
        mod_entries = list(self.modules_to_find()) + ["-" + i for i in self.modules_to_ignore()]
        new_module.set_option("use-qt5-modules", " ".join(mod_entries))

        return new_module

    # @override
    def convert_to_modules(self, ctx) -> list[Module]:
        """
        Convert this module set to a list of ``Module``.

        This function should be called after options are read and build metadata is available.

        In our case, we will return ONLY ONE MODULE. That module will handle
        "submodules" via the init-repository script so from kde-builder's perspective it
        is handled as a single unit.
        """
        return [self._make_qt5_module(ctx)]
