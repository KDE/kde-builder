# SPDX-FileCopyrightText: 2013, 2016, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..kb_exception import ConfigError
from ..kb_exception import SetOptionError
from ..debug import KBLogger
from ..module.module import Module
from ..options_base import OptionsBase
from ..phase_list import PhaseList
from ..util.textwrap_mod import textwrap

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

    See also: git-repository-base, ModuleSetKDEProjects, use-projects
    """

    def __init__(self, ctx: BuildContext, name: str):
        OptionsBase.__init__(self)
        self.start_for_create_id: int = 0
        self.options["repository"] = "kde-projects"

        # newOptions:
        self.name: str = name or ""
        self.module_search_decls: list[str] = []
        self.module_ignore_decls: list[str] = []
        self.module_order: dict[str, int] = {}  # maps module names to position in list
        self.phase_list: PhaseList = PhaseList(ctx.phases.phaselist)
        self.context: BuildContext = ctx

    def __str__(self):  # pl2py: In perl there were no stringify for module-set, but we will make it, for convenience.
        return self.name

    def modules_to_find(self) -> list[str]:
        return self.module_search_decls

    def set_modules_to_find(self, module_decls: list[str]) -> None:
        decl_order: dict[str, int] = {module_decls[i]: i for i in range(len(module_decls))}

        self.module_search_decls = module_decls
        self.module_order = decl_order

    def module_names_to_find(self) -> list[str]:
        """
        Get module names to find.

        Same as modules_to_find, but strips away any path components to leave just module names.
        E.g. a "use-projects kde/kdelibs juk.git" would give (kdelibs, juk) as the result list.
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
        new_module.phases.reset_to(self.phase_list.phaselist)
        new_module.merge_options_from(self)

        # used for dependency sorting tiebreakers, by giving a fallback sort based
        # on order the user declared modules in use-projects, especially for third
        # party modules. Indirect deps won't have an entry and are given the max value
        # to sort at the end within the module-set.
        start_order = self.start_for_create_id

        order_in_list: int = self.module_order.get(f"{new_module}", len(self.module_search_decls))
        new_module.create_id = start_order + order_in_list

    # @override
    def set_option(self, opt_name: str, opt_val) -> None:
        """
        Handle module-set specific options for OptionsBase's set_option.
        """
        # Special-case handling
        if opt_name == "use-projects":
            assert isinstance(opt_val, list)
            modules = opt_val
            if not modules:
                logger_moduleset.error("No projects were selected for group " + self.name)
                logger_moduleset.error("in the y[use-projects] entry.")
                raise SetOptionError("use-projects", "Invalid use-projects")

            self.set_modules_to_find(modules)
            return

        if opt_name == "ignore-projects":
            assert isinstance(opt_val, list)
            modules = opt_val
            if not modules:
                logger_moduleset.error("No projects were selected for group " + self.name)
                logger_moduleset.error("in the y[ignore-projects] entry.")
                raise SetOptionError("ignore-projects", "Invalid ignore-projects")

            self.add_modules_to_ignore(modules)
            return

        # Actually set options.
        OptionsBase.set_option(self, opt_name, opt_val)

    def convert_to_modules(self, ctx: BuildContext) -> list[Module]:
        """
        Convert this module set to a list of Module.

        This function should be called after options are read and build metadata is available.
        Any modules ignored by this module set are excluded from the returned list.
        The modules returned have not been added to the build context.
        """
        module_list = []  # module names converted to `Module` objects.

        # Setup default options for each module
        # If we're in this method, we must be using the git-repository-base method
        # of setting up a module-set, so there is no "search" or "ignore" to
        # handle, just create `Module` and dump options into them.
        for module_item in self.modules_to_find():
            module_name = module_item
            module_name = re.sub(r"\.git$", "", module_name)

            new_module = Module(ctx, module_name)

            self._initialize_new_module(new_module)
            new_module.set_scm_type("git")
            module_list.append(new_module)

        if not self.modules_to_find():
            logger_moduleset.warning(f"No projects were defined for the group {self.name}")
            logger_moduleset.warning("You should use the g[b[use-projects] option to make the group useful.")

        return module_list

    # @override
    def verify_option_value_type(self, option_name, option_value) -> None:
        """
        Ensure we are setting the correct type for value of option.
        """
        self.context.verify_option_value_type(option_name, option_value)
