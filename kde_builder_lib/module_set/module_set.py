# SPDX-FileCopyrightText: 2013, 2016, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..kb_exception import SetOptionError
from ..debug import KBLogger
from ..module.module import Module
from ..options_base import OptionsBase
from ..phase_list import PhaseList

if TYPE_CHECKING:
    from ..build_context import BuildContext

logger_moduleset = KBLogger.getLogger("module-set")


class ModuleSet(OptionsBase):
    """
    Represents a collective grouping of modules that share common options.

    Also, they share a common repository (in this case, based on the git-repository-base
    option, but see also the more common ModuleSetKDEProjects which is used for
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

    See also: git-repository-base, ModuleSetKDEProjects, use-modules
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
        self.ctx = ctx

    def __str__(self):  # pl2py: In perl there were no stringify for module-set, but we will make it, for convenience.
        return self.name

    def modules_to_find(self) -> list[str]:
        return self.module_search_decls

    def set_modules_to_find(self, module_decls: list[str]) -> None:
        decl_order = {module_decls[i]: i for i in range(len(module_decls))}

        self.module_search_decls = module_decls
        self.module_order = decl_order

    def module_names_to_find(self) -> list[str]:
        """
        Get module names to find.

        Same as modules_to_find, but strips away any path components to leave just module names.
        E.g. a "use-modules kde/kdelibs juk.git" would give (kdelibs, juk) as the result list.
        """
        ret = [re.sub(r"([^/]+)$", r"\1", re.sub(r"\.git$", "", module)) for module in self.modules_to_find()]
        return ret

    def modules_to_ignore(self) -> list[str]:
        return self.module_ignore_decls

    def add_modules_to_ignore(self, module_decls: list[str]) -> None:
        self.module_ignore_decls.extend(module_decls)

    def _initialize_new_module(self, new_module: Module) -> None:
        """
        Initialize new module.

        Should be called for each new ``Module`` created in order to set up common module options.
        """
        new_module.set_module_set(self)
        new_module.set_scm_type("git")
        new_module.phases.reset_to(self.phase_list.phaselist)
        new_module.merge_options_from(self)

        # used for dependency sorting tiebreakers, by giving a fallback sort based
        # on order the user declared modules in use-modules, especially for third
        # party modules. Indirect deps won't have an entry and are given the max value
        # to sort at the end within the module-set.
        start_order = self.create_id if self.create_id else 0

        order_in_list = self.module_order.get(f"{new_module}", len(self.module_search_decls))
        new_module.create_id = start_order + order_in_list

    # @override
    def set_option(self, options: dict) -> None:
        """
        Handle module-set specific options for OptionsBase's set_option.
        """
        # Special-case handling
        if "use-modules" in options:
            modules = options["use-modules"].split(" ")
            if not modules:
                logger_moduleset.error("No modules were selected for module-set " + self.name)
                logger_moduleset.error("in the y[use-modules] entry.")
                raise SetOptionError("use-modules", "Invalid use-modules")

            self.set_modules_to_find(modules)
            del options["use-modules"]

        if "ignore-modules" in options:
            modules = options["ignore-modules"].split(" ")
            if not modules:
                logger_moduleset.error("No modules were selected for module-set " + self.name)
                logger_moduleset.error("in the y[ignore-modules] entry.")
                raise SetOptionError("ignore-modules", "Invalid ignore-modules")

            self.add_modules_to_ignore(modules)
            del options["ignore-modules"]

        # Actually set options.
        OptionsBase.set_option(self, options)

    def convert_to_modules(self, ctx: BuildContext) -> list[Module]:
        """
        Convert this module set to a list of Module.

        This function should be called after options are read and build metadata is available.
        Any modules ignored by this module set are excluded from the returned list.
        The modules returned have not been added to the build context.
        """
        module_list = []  # module names converted to `Module` objects.
        options = self.options

        # Note: This returns a dict, not a string.
        repo_set = ctx.get_option("git-repository-base")

        # Setup default options for each module
        # If we're in this method, we must be using the git-repository-base method
        # of setting up a module-set, so there is no "search" or "ignore" to
        # handle, just create `Module` and dump options into them.
        for module_item in self.modules_to_find():
            module_name = module_item
            module_name = re.sub(r"\.git$", "", module_name)

            new_module = Module(ctx, module_name)

            self._initialize_new_module(new_module)

            module_list.append(new_module)

            # Set up the only feature actually specific to a module-set, which is
            # the repository handling.
            selected_repo = repo_set[options["repository"]]
            new_module.set_option({"repository": selected_repo + module_item})

        if not self.modules_to_find():
            logger_moduleset.warning(f"No modules were defined for the module-set {self.name}")
            logger_moduleset.warning("You should use the g[b[use-modules] option to make the module-set useful.")

        return module_list

    # @override
    def verify_option_value_type(self, option_name, option_value) -> None:
        """
        Ensure we are setting the correct type for value of option.
        """
        self.ctx.verify_option_value_type(option_name, option_value)
