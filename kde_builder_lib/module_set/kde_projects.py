# SPDX-FileCopyrightText: 2013, 2016, 2017 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from .module_set import ModuleSet
from ..kb_exception import UnknownKdeProjectException
from ..debug import KBLogger
from ..kde_projects_reader import KDEProjectsReader
from ..module.module import Module
from ..util.util import Util

if TYPE_CHECKING:
    from ..build_context import BuildContext

logger_moduleset = KBLogger.getLogger("module-set")


class ModuleSetKDEProjects(ModuleSet):
    """
    Represents a collective grouping of modules that share common options, based on the KDE project repositories.

    Metadata for that repository is itself housed in a dedicated KDE.org git repository "sysadmin/repo-metadata",
    which this class uses to imbue Modules generated by this ModuleSet.

    The only changes here are to allow for expanding out module specifications
    (except for ignored modules), by using KDEProjectsReader.
    """

    def __init__(self, ctx: BuildContext, name: str):
        ModuleSet.__init__(self, ctx, name)
        self.projects_data_reader = None  # Will be filled in when we get fh

    @staticmethod
    def none_true(input_list: list) -> bool:
        return all(not element for element in input_list)

    @staticmethod
    def _create_metadata_module(ctx: BuildContext, module_name: str) -> Module:
        metadata_module = Module(ctx, re.sub("/", "-", module_name))

        # Hardcode the results instead of expanding out the project info
        metadata_module.set_option("repository", f"kde:{module_name}")  # The ~/.gitconfig should already have the "kde:" alias (otherwise we will get 128 exit code).
        # We do use alias (i.e. not the https address) here, because we want to support git push protocol for the metadata module (so it is easier to contribute to metadata in the future).
        metadata_module.set_option("#kde-project-path", module_name)
        metadata_module.set_scm_type("metadata")
        metadata_module.set_option("branch", "master")
        metadata_module.set_option("source-dir",  os.environ.get("XDG_STATE_HOME", os.environ["HOME"] + "/.local/state"))
        metadata_module.set_option("log-dir", "log")  # overwrite default value, because user may store his directories not under "~/kde"

        module_set = ModuleSetKDEProjects(ctx, "<kde-projects dependencies>")
        metadata_module.set_module_set(module_set)

        # Ensure we only ever try to update source, not build.
        metadata_module.phases.reset_to(["update"])

        return metadata_module

    @staticmethod
    def get_project_metadata_module(ctx_obj: BuildContext) -> Module:
        """
        Return a ``Module`` that can be used to download the "repo-metadata" module.

        The repo-metadata contains information on each
        repository in the KDE build system (though currently not
        dependencies). The module is meant to be held by the ``BuildContext``

        Args:
            ctx_obj: The ``BuildContext`` for this script execution.
        """
        from ..build_context import BuildContext
        ctx = Util.assert_isa(ctx_obj, BuildContext)
        return ModuleSetKDEProjects._create_metadata_module(ctx, "sysadmin/repo-metadata")

    def _expand_module_candidates(self, ctx: BuildContext, module_search_item: str) -> list[Module]:
        """
        Goes through the modules in our search list (assumed to be found in kde-projects), expands them into their equivalent modules, and returns the fully expanded list.

        Non kde-projects modules cause an error, as do modules that do not exist at all within the database.

        *Note*: Before calling this function, the kde-projects database itself must
        have been downloaded first. See get_project_metadata_module, which ties to the
        BuildContext.

        Modules that are part of a module-set requiring a specific branch, that don't
        have that branch, are still listed in the return result since there's no way
        to tell that the branch won't be there.  These should be removed later.

        Args:
            ctx: The ``BuildContext`` in use.
            module_search_item: The search description to expand in ``Module``s. See
                project_path_matches_wildcard_search for a description of the syntax.

        Returns:
            modules List of expanded git Modules.

        Raises:
            Runtime: if the kde-projects database was required but couldn't be downloaded or read.
            Runtime: if the git-push-protocol is unsupported.
            UnknownKdeProjectException: if an "assumed" kde-projects module was not actually one.
        """
        all_module_results = ctx.get_project_data_reader().get_modules_for_project(module_search_item)

        if not all_module_results:
            # Do not exit here, because there are third-party projects (such as taglib) mentioned in dependencies, and the situation when they
            # are not defined in config is normal.
            raise UnknownKdeProjectException(f"Unknown KDE project: {module_search_item}", module_search_item)

        # It's possible to match modules which are marked as inactive on
        # projects.kde.org, elide those.
        active_results = all_module_results
        if not ctx.get_option("use-inactive-projects"):
            active_results = [module for module in all_module_results if module.get("active")]

        if not active_results:
            logger_moduleset.warning(f" y[b[*] Module y[{module_search_item}] is apparently a KDE collection, but contains no\n" + "active modules to build!")

            if all_module_results:
                count = len(all_module_results)
                logger_moduleset.warning("\tAlthough no active modules are available, there were\n" + f"\t{count} inactive modules. Perhaps the git modules are not ready?")

        # Setup module options.
        module_list = []
        ignore_list = self.modules_to_ignore()

        for result in active_results:
            new_module = Module(ctx, result["name"])
            self._initialize_new_module(new_module)

            # Copy metadata from KDE project YAML file
            new_module.set_option("repository", result["repo"])
            new_module.set_option("#kde-project-path", result["full_name"])
            new_module.set_option("#kde-repo-path", result.get("invent_name", None))
            new_module.set_option("#found-by", result["found_by"])

            new_module.set_scm_type("proj")

            if self.none_true([KDEProjectsReader.project_path_matches_wildcard_search(result["full_name"], element) for element in ignore_list]):
                module_list.append(new_module)
            else:
                logger_moduleset.debug(f"--- Ignoring matched active module {new_module} in module set " + self.name)
        return module_list

    # @override
    def convert_to_modules(self, ctx: BuildContext) -> list[Module]:
        """
        Convert given module set to a list of Module.

        This function should be called after options are read and build metadata is available.
        Any modules ignored by this module set are excluded from the returned list.
        The modules returned have not been added to the build context.
        """
        module_list = []  # module names converted to `Module` objects.
        found_modules = {}

        # Setup default options for each module
        # Extraction of relevant kde-project modules will be handled immediately
        # after this phase of execution.
        for module_item in self.modules_to_find():
            # We might have already grabbed the right module recursively.
            if module_item in found_modules:
                continue

            candidate_modules = self._expand_module_candidates(ctx, module_item)
            module_names = [item.name for item in candidate_modules]
            found_modules = {module: 1 for module in module_names}
            module_list.extend(candidate_modules)

        if not len(module_list):
            logger_moduleset.warning("No modules were defined for the module-set " + self.name)
            logger_moduleset.warning("You should use the g[b[use-projects] option to make the module-set useful.")

        return module_list
