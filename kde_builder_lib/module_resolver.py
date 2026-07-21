# SPDX-FileCopyrightText: 2015, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from .kb_exception import KBException
from .kb_exception import KBRuntimeError
from .kb_exception import NoKDEProjectsFound
from .kb_exception import UnknownKdeProjectException
from .debug import KBLogger
from .module.module import Module
from .module_set.module_set import ModuleSet

if TYPE_CHECKING:
    from build_context import BuildContext
    from .metadata.kde_projects_reader import KDEProjectsReader

logger_modres = KBLogger.getLogger("module-resolver")


class ModuleResolver:
    """
    Handles general management tasks associated with the module build list.

    This includes option handling and resolution of module selectors into actual modules.
    """

    def __init__(self, ctx: BuildContext):
        self.context = ctx

        self.ignored_selectors: set[str] = set()
        """
        Holds selectors that should be ignored.
        """

        self.cmdline_per_project_options = {}
        """
        The options that should be applied to modules when they are created.

        A dict, where module-names are keys to values which are themselves dicts of option-name: value pairs:

          { mod1: {"cmake-options": "foo", ... },
            mod2: {}
          }
        """

        self.deferred_options: dict[str, dict] = {}
        """Holds options from "override" nodes for modules."""

        self.defined_projects: dict[str, Module] = {}
        """
        Holds created Module objects. Contains both kde and third-party projects.
        Initially populated because of declared "project <>" nodes in the config.
        Then populated because of expanding declared "groups <>" nodes in the config.
        Then populated because of following dependencies (only possible for kde projects).
        They are filled-in with their options, as in defined defaults or in config ("global" node, "group <>" nodes,
        "override <>" nodes) and command line. And then they could be finally used in run_all_module_phases().
        """

        self.defined_groups: dict[str, ModuleSet] = {}
        """Holds ModuleSet objects, created because of declared in "group <>" nodes in config."""

        self.explicit_kdeproject_selectors: list[str] = []
        self.explicit_group_selectors: list[str] = []
        self.explicit_thirdparty_selectors: list[str] = []

    def set_deferred_options(self, deferred_options: list[dict[str, str | dict]]) -> None:
        """
        Set options to apply later if a module set resolves to a named module, used for "override" nodes.

        Each object in the dict can be either options for a later :class:`Module`,
        or options for an entire set of :class:`Module` (as determined by use of
        repository/use-module items). We want to handle the latter first, since
        we assume single "override" nodes should still be able to override these.
        """
        proj_db: KDEProjectsReader = self.context.projects_db
        set_indices: list[int] = []
        final_opts: dict[str, dict] = {}

        for idx, deferred_entry in enumerate(deferred_options):
            opts = deferred_entry["opts"]
            referenced_modules = opts.get("use-projects", None)

            # Skip "override" nodes that don't reference module-sets
            if not referenced_modules:
                continue

            del opts["use-projects"]
            set_indices.append(idx)  # so we can delete this once loop complete

            # Use KDE project database to pull list of matching `Module`s
            for m in referenced_modules:
                _empty_list = []
                names: list[str] = proj_db.get_identifiers_for_selector(m, _empty_list)
                for name in names:
                    if name not in final_opts:
                        final_opts[name] = copy.deepcopy(opts)

        # Delete options for module sets, so we don't accidentally process them now
        # that use-projects/repository keys are gone. Must be done back-to-front so
        # indices don't change.
        set_indices.reverse()
        for index in set_indices:
            del deferred_options[index]

        # Go through list a second time (which should be only single module options)
        # and overlay any new options on

        for idx, deferred_entry in enumerate(deferred_options):
            name = deferred_entry["name"]
            opts = deferred_entry["opts"]

            if name in final_opts:
                final_opts[name].update(opts)
            else:
                final_opts[name] = opts

        self.deferred_options = final_opts

    def set_initial_projects_and_groups(self, projects_and_groups: list[Module | ModuleSet]) -> None:
        """
        Initial fill-up of lookup dictionaries.
        """
        for pr_or_gr in projects_and_groups:
            if isinstance(pr_or_gr, ModuleSet):
                self.defined_groups[pr_or_gr.name] = pr_or_gr
            elif isinstance(pr_or_gr, Module):
                self.defined_projects[pr_or_gr.name] = pr_or_gr

    def handle_initial_projects(self):
        """
        Apply command line and override options to projects directly-defined in config.
        """
        projects: list[Module] = [el for el in self.defined_projects.values()]
        self._apply_options(projects)

    def _apply_options(self, modules: list[Module | ModuleSet]) -> None:
        """
        Apply cmdline and deferred options to the given modules or module-sets.
        """
        for m in modules:
            name = m.name
            opts = copy.deepcopy(self.deferred_options.get(name, {}))

            # Apply deferred options first
            if m.options.get("#entry_num", 0) > opts.get("#entry_num", 0):
                # Our existing options were read in later so should not be overridden
                for key in m.options:
                    if key in opts:
                        del opts[key]

            for opt_name, opt_val in opts.items():
                m.set_option(opt_name, opt_val)

            # Most of the time cmdline per project options will be empty
            if self.cmdline_per_project_options:
                module_cmdline_args = {
                    **(self.cmdline_per_project_options.get(name, {}))
                }

                # Remove any options that would interfere with cmdline args
                # to avoid any override behaviors in set_option()
                for key in module_cmdline_args:
                    if key in m.options:
                        del m.options[key]

                # Reapply module-specific cmdline options
                for opt_name, opt_val in module_cmdline_args.items():
                    m.set_option(opt_name, opt_val)
        return

    def _resolve_single_selector(self, selector_name: str) -> list[Module]:
        """
        Return list of Module objects for a given selector.

        The selector may refer to a project or group, which means that the
        returned list may have several Module objects.
        """
        ctx = self.context
        results: list[Module] = []

        # Case 1: selector_name names a project (kde or third-party) that is already in self.defined_projects.
        if selector_name in self.defined_projects:
            project = self.defined_projects[selector_name]
            results.append(project)

        # Case 2: selector_name names a group from the config
        elif selector_name in self.defined_groups:
            group: ModuleSet = self.defined_groups[selector_name]
            # At this point, all groups are expanded. So just take its projects.
            projects: list[Module] = group.get_projects()
            results.extend(projects)

        # Case 3: selector_name names either kde project that is not yet in self.defined_projects, or is fully unrecognized.
        else:
            if selector_name not in self.context.projects_db.repositories:
                # Third-party projects must not be crafted this way.
                raise UnknownKdeProjectException(f"Unknown KDE project: {selector_name}", selector_name)

            is_active = self.context.projects_db.repositories[selector_name]["active"]

            if not is_active:
                raise UnknownKdeProjectException(f"Archived KDE project: {selector_name}", selector_name)

            project: Module = Module(ctx, selector_name)

            self._apply_options([project])
            self.defined_projects[selector_name] = project
            results.append(project)

        return results

    def expand_all_groups(self) -> None:
        """
        Expand every group, populate self.defined_projects when necessary, and apply override options.

        Takes every ModuleSet from self.defined_groups, and operates on it. Applies override options to it,
        expands it to Module objects, and also applies options to them.
        It takes existing Module object if it already exists in self.defined_projects, otherwise creates it and places there.
        """
        unexpanded_groups: list[ModuleSet] = list(self.defined_groups.values())
        unexpanded_groups.sort(key=lambda x: x.name)

        for unexpanded_group in unexpanded_groups:
            # Need to update group first, so it can then apply its settings to projects it creates.
            self._apply_options([unexpanded_group])
            project_results: list[Module] = unexpanded_group.convert_to_modules()
            self._apply_options(project_results)

            if not project_results:
                raise KBRuntimeError(f"{unexpanded_group.name} expanded to an empty list of projects!")

            self.defined_projects.update({project_result.name: project_result for project_result in project_results})

    def set_explicit_cmdline_selectors(self, cmdline_selectors: list[str]) -> None:
        proj_db = self.context.projects_db.repositories
        for el in cmdline_selectors:
            leaf = el.split("/")[-1]
            if leaf in proj_db:
                self.explicit_kdeproject_selectors.append(leaf)
            elif leaf in self.defined_groups:
                self.explicit_group_selectors.append(leaf)
            else:
                self.explicit_thirdparty_selectors.append(leaf)

    def resolve_selectors_into_modules(self, selectors: list[str]) -> list[Module]:
        """
        Resolve the given list of selectors into :class:`Module` objects.

        If you are just looking for a Module that should already be present, see
        resolve_module_if_present().
        """
        names: list[str] = []
        _empty_list = []
        for selector in selectors:
            try:
                # If selector is a full repopath of kde project, like "utilities/kcalc",
                # it will be converted to just project identifier "kcalc".
                # If selector is a gitlab group name, like "plasma/*",
                # it will be converted to identifiers from that group, like ["plasma-activities", "libplasma", ...].
                identifiers = self.context.projects_db.get_identifiers_for_selector(selector, _empty_list)
            except NoKDEProjectsFound:
                # This means either selector is a group name, or third-party project, or is unrecognized.
                identifiers = [selector]
            names.extend(identifiers)

        output_list: list[Module] = []
        for selector in names:
            selector_results = self._resolve_single_selector(selector)
            filtered_results = self.filter_out_unneeded_modules(selector_results)
            output_list.extend(filtered_results)

        return output_list

    def resolve_module_if_present(self, module_name: str) -> Module | None:
        """
        Similar to resolve_selectors_into_modules(), except that no exceptions are thrown if the module doesn't exist.

        Only a single module name is supported.
        """
        if self.defined_projects.get(module_name) is None:
            try:
                self._resolve_single_selector(module_name)
            except KBException:  # UnknownKdeProjectException for third party dependencies is caught here.
                pass

        ret: Module | None = self.defined_projects.get(module_name, None)
        if ret:
            out = self.filter_out_unneeded_modules([ret])
            ret = out[0] if out else None
        return ret

    def filter_out_unneeded_modules(self, modules: list[Module]) -> list[Module]:
        ignored_selectors = self.ignored_selectors
        filtered_modules: list[Module] = []
        for module in modules:
            module_set_name = module.module_set.name if module.module_set else ""

            if module.name in ignored_selectors:
                if module.name in [*self.explicit_kdeproject_selectors, *self.explicit_thirdparty_selectors]:
                    logger_modres.warning(f" y[*] Project y[{module.name}] was explicitly selected in command line, but removed due to being ignored.")
                else:
                    logger_modres.debug(f"Project y[{module.name}] was removed due to being ignored.")
                continue
            elif module_set_name in ignored_selectors:
                if module_set_name in self.explicit_group_selectors:
                    logger_modres.warning(f" y[*] Group y[{module_set_name}] was explicitly selected in command line, but is ignored, so project y[{module.name}] was removed.")
                else:
                    if module.name in [*self.explicit_kdeproject_selectors, *self.explicit_thirdparty_selectors]:
                        logger_modres.warning(f" y[*] Group y[{module_set_name}] is ignored, so project y[{module.name}] was removed.")
                    else:
                        logger_modres.debug(f"Group y[{module_set_name}] is ignored, so project y[{module.name}] was removed.")
                continue
            elif module_set_name in ["qt6-set"]:
                if module.get_option("install-dir") == "":
                    # User may have set their qt-install-dir option to empty string (the default), which means disabling building qt modules.
                    # But still user can accidentally request to build some qt modules (by explicitly specifying such modules in cmdline, or
                    # by building all). We should not allow building qt modules in such case.
                    # Otherwise, as their real "install-dir" is empty, their CMAKE_INSTALL_PREFIX will be incorrect (set to empty), and such
                    # modules could not pass cmake configure.
                    logger_modres.warning(f" y[*] Removing y[third-party]/y[{module.name}] due to qt-install-dir")
                    continue

            if module.is_kde_project():
                # Remove projects that are explicitly blanked out in their branch-group,
                # i.e. those projects where they *have* a branch-group, and it's set to be empty ("").
                ctx = self.context
                resolver = ctx.branch_group_resolver
                branch_group = ctx.get_option("branch-group")
                repopath = module.get_repopath()
                branch = resolver.resolve_branch_group(repopath, branch_group)
                if branch == "":  # Note that None means it was not mentioned, while "" means it was explicitly disabled
                    printpath = repopath
                    printpath = "y[" + printpath.replace("/", "]/y[") + "]"
                    message = f" y[*] Removing {printpath} due to branch-group"
                    if module.name in self.explicit_kdeproject_selectors:
                        logger_modres.warning(message)
                    else:
                        logger_modres.debug(message)
                    continue

            filtered_modules.append(module)

        return filtered_modules

"""
This class uses a multi-pass option resolving system, in accordance with
the way kde-builder handles options. Consider a simple kde-builder.yaml:

 global:
   cmake-options: -DCMAKE_BUILD_TYPE=Debug
   ...

 group ms-foo:
   cmake-options: -DCMAKE_BUILD_TYPE=RelWithDebInfo
   repository: kde-projects
   use-projects:
     - kde/kdemultimedia
   include-dependencies: true

 override framework1:
   set-env:
     BUILD_DEBUG: 1

 project taglib:
   repository: git://...
   branch: 1.6

 override juk:
   cxxflags: -g3 -Og
   custom-build-command: ninja

In this case we'd expect that a project like taglib ends up with its
``cmake-options`` derived from the global section directly, while all projects
included from group ``ms-foo`` use the ``cmake-options`` defined in the
group.

At the same time we'd expect that juk has all the options listed in ms-foo, but
also the specific ``cxxflags`` and ``custom-build-command`` options shown,
`no matter how` the juk project had been referenced during the build.

There are many ways to convince kde-builder to add a project into its build list:

1. Mention it directly on the command line.

2. Include it in the kde-builder.yaml file, either as a new ``project`` block or
in a ``use-projects`` of a ``group``.

3. For KDE projects, mention a component of its project path in a
``use-projects`` declaration within a ``kde-projects``-based group. E.g. the
"kde/kdemultimedia" entry above, which will pull in the juk project even though
"juk" is not named directly.

4. For KDE projects, by being a dependency of a project included from a
``group`` where the ``include-dependencies`` option is set to ``true``. This
wouldn't apply to juk, but might apply to projects such as phonon. Note that
"taglib" in this example would **not** be a dependency of juk according to
kde-builder (although it is in reality), since taglib is not a KDE project.


This mission of this class is to ensure that, no matter `how` a project ended
up being selected by the user for the build list, that the same options are
registered into the project, the project uses the same build type, is
defaulted to the right build phases, etc.

To do this, this class takes the read-in options, projects, and groups from
the rc-file, the list of "selectors" requested by the user (via cmdline), any
changes to the options from the cmdline, and then takes pains to ensure that
any requested projects are returned via the appropriate group (and if no
group can source the project, via default options).

In doing so, the class must keep track of groups, the projects included
into each group, and modules that were mentioned somehow but not
already present in the known list of projects (or groups).

Since project sets can cause projects to be defined that are not mentioned
anywhere within an rc-file, it may be required to completely expand all
groups in order to verify that a referenced :class:`Module` is **not**
already known.

From the perspective of calling code, the "outputs" of this project are
lists of :class:`Module` objects, in the order they were selected (or mentioned
in the rc-file). See expand_all_groups() and resolve_selectors_into_modules().

Each object so returned should already have the appropriate options
included (based on the cmdline_options member, which should be constructed
as the union of rc-file and cmdline options).

Note that dependency resolution is **not** handled by this class, see
:class:`DependencyResolver` for that.
"""
