# SPDX-FileCopyrightText: 2013, 2016, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..BuildException import BuildException_Config
from ..Debug import kbLogger
from ..Module.Module import Module
from ..OptionsBase import OptionsBase
from ..PhaseList import PhaseList

if TYPE_CHECKING:
    from ..BuildContext import BuildContext

logger_moduleset = kbLogger.getLogger("module-set")


class ModuleSet(OptionsBase):
    """
    This represents a collective grouping of modules that share common options,
    and share a common repository (in this case, based on the git-repository-base
    option, but see also the more common ModuleSet_KDEProjects which is used for
    the special kde-projects repositories).

    This is parsed from module-set declarations in the rc-file.

    The major conceit here is several things:

    1. A dict of options to set for each module read into this module set.
    2. A list of module search declarations to be used to construct modules for
    this module set (in the case of kde-projects repository). For other
    repository types we can still consider it a "search", but with the
    understanding that it's a 1:1 mapping to the "found" module (which may not
    exist for real).
    3. A list of module search declarations to *ignore* from this module set,
    using the same syntax as used to search for them in 2. This is only really
    useful at this point for kde-projects repository as everything else requires
    you to manually specify modules one-by-one (module-sets are only useful here
    for option grouping as per 1.).
    4. A name, which must not be empty, although user-specified names cannot be
    assumed to be unique.
    5. A PhaseList describing what phases of the build a module should
    participate in by default.

    See also: git-repository-base, ModuleSet_KDEProjects, use-modules
    """

    def __init__(self, ctx: BuildContext, name: str):
        OptionsBase.__init__(self)
        self.create_id = None

        # newOptions:
        self.name = name or ""
        self.module_search_decls = []
        self.module_ignore_decls = []
        self.module_order = {}  # maps module names to position in list
        self.phase_list: PhaseList = PhaseList(ctx.phases.phaselist)

    def __str__(self):  # pl2py: In perl there were no stringify for module-set, but we will make it, for convenience.
        return self.name

    def modulesToFind(self) -> list[str]:
        return self.module_search_decls

    def setModulesToFind(self, moduleDecls: list[str]) -> None:
        declOrder = {moduleDecls[i]: i for i in range(len(moduleDecls))}

        self.module_search_decls = moduleDecls
        self.module_order = declOrder

    def moduleNamesToFind(self) -> list[str]:
        """
        Same as modulesToFind, but strips away any path components to leave just
        module names.
        E.g. a "use-modules kde/kdelibs juk.git" would give (kdelibs, juk) as the
        result list.
        """
        ret = [re.sub(r"([^/]+)$", r"\1", re.sub(r"\.git$", "", module)) for module in self.modulesToFind()]
        return ret

    def modulesToIgnore(self) -> list[str]:
        return self.module_ignore_decls

    def addModulesToIgnore(self, moduleDecls: list[str]) -> None:
        self.module_ignore_decls.extend(moduleDecls)

    def _initializeNewModule(self, newModule: Module) -> None:
        """
        Should be called for each new ``Module`` created in order to set up common
        module options.
        """
        newModule.setModuleSet(self)
        newModule.setScmType("git")
        newModule.phases.reset_to(self.phase_list.phaselist)
        newModule.mergeOptionsFrom(self)

        # used for dependency sorting tiebreakers, by giving a fallback sort based
        # on order the user declared modules in use-modules, especially for third
        # party modules. Indirect deps won't have an entry and are given the max value
        # to sort at the end within the module-set.
        startOrder = self.create_id if self.create_id else 0

        orderInList = self.module_order.get(f"{newModule}", len(self.module_search_decls))
        newModule.create_id = startOrder + orderInList

    # @override
    def setOption(self, options: dict) -> None:
        """
        Handles module-set specific options for OptionsBase's setOption
        """

        # Special-case handling
        if "use-modules" in options:
            modules = options["use-modules"].split(" ")
            if not modules:
                logger_moduleset.error("No modules were selected for module-set " + self.name)
                logger_moduleset.error("in the y[use-modules] entry.")
                raise BuildException_Config("use-modules", "Invalid use-modules")

            self.setModulesToFind(modules)
            del options["use-modules"]

        if "ignore-modules" in options:
            modules = options["ignore-modules"].split(" ")
            if not modules:
                logger_moduleset.error("No modules were selected for module-set " + self.name)
                logger_moduleset.error("in the y[ignore-modules] entry.")
                raise BuildException_Config("ignore-modules", "Invalid ignore-modules")

            self.addModulesToIgnore(modules)
            del options["ignore-modules"]

        # Actually set options.
        OptionsBase.setOption(self, options)

    def convertToModules(self, ctx: BuildContext) -> list[Module]:
        """
        This function should be called after options are read and build metadata is
        available in order to convert this module set to a list of Module.
        Any modules ignored by this module set are excluded from the returned list.
        The modules returned have not been added to the build context.
        """
        moduleList = []  # module names converted to `Module` objects.
        optionsRef = self.options

        # Note: This returns a hashref, not a string.
        repoSet = ctx.getOption("git-repository-base")

        # Setup default options for each module
        # If we're in this method, we must be using the git-repository-base method
        # of setting up a module-set, so there is no 'search' or 'ignore' to
        # handle, just create `Module` and dump options into them.
        for moduleItem in self.modulesToFind():
            moduleName = moduleItem
            moduleName = re.sub(r"\.git$", "", moduleName)

            newModule = Module(ctx, moduleName)

            self._initializeNewModule(newModule)

            moduleList.append(newModule)

            # Set up the only feature actually specific to a module-set, which is
            # the repository handling.
            selectedRepo = repoSet[optionsRef["repository"]]
            newModule.setOption({"repository": selectedRepo + moduleItem})

        if not self.modulesToFind():
            logger_moduleset.warning(f"No modules were defined for the module-set {self.name}")
            logger_moduleset.warning("You should use the g[b[use-modules] option to make the module-set useful.")

        return moduleList
