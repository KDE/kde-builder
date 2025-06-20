# SPDX-FileCopyrightText: 2015, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Handle proper resolution of module selectors, including option
# handling.

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from .kb_exception import KBException
from .kb_exception import KBRuntimeError
from .module.module import Module
from .module_set.kde_projects import ModuleSetKDEProjects
from .module_set.module_set import ModuleSet

if TYPE_CHECKING:
    from build_context import BuildContext
    from kde_projects_reader import KDEProjectsReader


class ModuleResolver:
    """
    Handles general management tasks associated with the module build list.

    This includes option handling and resolution of module selectors into actual modules.
    """

    def __init__(self, ctx: BuildContext):
        self.context = ctx

        # Declares all selectors that should be ignored by default in the process of
        # expanding module sets. Any modules matching these selectors would be elided
        # from any expanded module sets by default.
        self.ignored_selectors: list[str] = []

        # Read in from rc-file
        self.input_modules_and_options: list[Module | ModuleSet] = []

        # The options that should be applied to modules when they are created.
        # No special handling for global options is performed here (but see
        # :meth:`OptionsBase.get_option` and its friends).
        #
        # A dict, where module-names are keys to values which
        # are themselves dicts of option-name: value pairs:
        #
        #  { mod1: {"cmake-options": "foo", ... },
        #    mod2: {}
        #  }
        self.cmdline_options = {}

        # Holds options from "override" nodes for modules
        self.deferred_options: dict[str, dict] = {}

        # Holds Modules defined in course of expanding module-sets
        self.defined_modules: dict[str, Module | ModuleSet] = {}

        # Holds use-module mentions with their source module-set
        self.referenced_modules: dict[str, ModuleSet] = {}

    def set_deferred_options(self, deferred_options: list[dict[str, str | dict]]) -> None:
        """
        Set options to apply later if a module set resolves to a named module, used for "override" nodes.

        Each object in the dict can be either options for a later :class:`Module`,
        or options for an entire set of :class:`Module` (as determined by use of
        repository/use-module items). We want to handle the latter first, since
        we assume single "override" nodes should still be able to override these.
        """
        proj_db: KDEProjectsReader = self.context.get_project_data_reader()
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
                mods: list[dict[str, str | bool]] = proj_db.get_modules_for_project(m)
                for mod in mods:
                    name = mod["name"]
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

    def set_input_modules_and_options(self, mod_opts: list[Module | ModuleSet]) -> None:
        """
        Declare the list of all modules and module-sets known to the program, along with their base options.
        """
        self.input_modules_and_options = mod_opts

        # Build lookup dictionaries
        self.defined_modules: dict[str, Module | ModuleSet] = {mod.name: mod for mod in mod_opts}
        self.referenced_modules: dict[str, ModuleSet] = self._list_referenced_modules(mod_opts)

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

            # Most of the time cmdline options will be empty
            if self.cmdline_options:
                module_cmdline_args = {
                    # order is important here
                    **(self.cmdline_options.get("global", {})),
                    **(self.cmdline_options.get(name, {}))
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

    @staticmethod
    def _list_referenced_modules(modules_and_modulesets: list[Module | ModuleSet]) -> dict[str, ModuleSet]:
        """
        Return a dict of all module names referenced in use-module declarations for any ModuleSet included within the input list.

        Each entry in the dict will map the referenced module name to the source ModuleSet.
        """
        set_entry_lookup_dict: dict[str, ModuleSet] = {}

        for module_set in [module_or_moduleset for module_or_moduleset in modules_and_modulesets if isinstance(module_or_moduleset, ModuleSet)]:
            results: list[str] = module_set.module_names_to_find()

            set_entry_lookup_dict.update({result: module_set for result in results})

        return set_entry_lookup_dict

    def _expand_single_module_set(self, needed_module_set: ModuleSet) -> list[Module]:
        """
        Expand out a single module-set listed in referenced_modules and places any Modules created as a result within the lookup dict of Modules.

        Returns the list of created Modules.
        """
        # expand_module_sets applies pending/cmdline options already.
        module_results: list[Module] = self.expand_module_sets([needed_module_set])
        if not module_results:
            raise KBRuntimeError(f"{needed_module_set.name} expanded to an empty list of projects!")

        # Copy entries into the lookup dict, especially in case they're
        # from case 3
        self.defined_modules.update({module_result.name: module_result for module_result in module_results})

        # Ensure Case 2 and Case 1 stays disjoint (our selectors should now be
        # in the lookup dict if it uniquely matches a module at all).
        module_set_referents: list[str] = [key for key, value in self.referenced_modules.items() if value == needed_module_set]

        for key in module_set_referents:
            del self.referenced_modules[key]

        return module_results

    def _resolve_single_selector(self, selector_name: str) -> list[Module | ModuleSet]:
        """
        Determine the most appropriate module to return for a given selector.

        The selector may refer to a module or module-set, which means that the
        return value may be a list of modules.
        """
        ctx = self.context
        selector: Module | ModuleSet | None = None
        results: list[Module | ModuleSet | None] = []  # Will default to the selector if unset by the end of function

        # In the remainder of this code, self.defined_modules is basically handling
        # case 1, while self.referenced_modules handles case 2. No `Module`s
        # are *both* case 1 and 2 at the same time, and a module-set can only
        # be case 1. We clean up and handle any case 3s (if any) at the end.

        # Module selectors beginning with "+" force treatment as a kde-projects
        # module, which means they won't be matched here (we're only looking for
        # sets).
        forced_to_kde_project: bool = selector_name[:1] == "+"

        if forced_to_kde_project:
            selector_name = selector_name[1:]

        # Checks cmdline options only.  This is intended to make
        # --no-include-dependencies suppress the action of include-dependencies in
        # the config file so make the absence of the flag imply
        # include-dependencies for now.
        def_including: bool = ctx.get_option("include-dependencies")
        including_deps: bool = self.cmdline_options["global"].get("include-dependencies", def_including)

        # See resolve_selectors_into_modules for what the 3 "cases" mentioned below are.

        # Case 2. We make these checks first since they may update lookup dict
        if selector_name in self.referenced_modules and selector_name not in self.defined_modules:
            needed_module_set: ModuleSet = self.referenced_modules[selector_name]
            module_results: list[Module] = self._expand_single_module_set(needed_module_set)

            if not including_deps:
                for module_result in module_results:
                    module_result.set_option("include-dependencies", False)

            # Now lookup dict should be updated with expanded modules.
            selector: Module | ModuleSet | None = self.defined_modules.get(selector_name, None)

            # If the selector doesn't match a name exactly it probably matches
            # a wildcard prefix. e.g. "kdeedu" as a selector would pull in all kdeedu/*
            # modules, but kdeedu is not a module-name itself anymore. In this
            # case just return all the modules in the expanded list.
            if not selector:
                # In _expand_single_module_set() it is ensured module_results is not empty.
                results.extend(module_results)

        # Case 1
        elif selector_name in self.defined_modules:
            selector: Module | ModuleSet = self.defined_modules[selector_name]

            if not isinstance(selector, ModuleSet) and not including_deps:
                # modules were manually selected on cmdline, so ignore
                # module-based include-dependencies, unless
                # include-dependencies also set on cmdline.
                selector.set_option("#include-dependencies", False)

        elif forced_to_kde_project:
            # Just assume it's a kde-projects module and expand away...
            selector: ModuleSetKDEProjects = ModuleSetKDEProjects(ctx, "forced_to_kde_project")
            selector.set_modules_to_find([selector_name])
            selector.set_option("#include-dependencies", including_deps)
        else:
            # Case 3?
            selector: Module = Module(ctx, selector_name)
            selector.phases.reset_to(ctx.phases.phaselist)

            selector.set_scm_type("proj")
            selector.set_option("#guessed-kde-project", True)
            selector.set_option("#include-dependencies", including_deps)

        # In case selector is None (may happen in case 2), results list for sure becomes non-empty,
        # so None (the value of selector variable) will not be placed to the results list. Return type annotation is correct.
        if not results:
            results.append(selector)

        return results

    def _expand_all_unexpanded_module_sets(self) -> None:
        unexpanded_module_sets: list[ModuleSet] = list(set(self.referenced_modules.values()))  # pl2py they used Util.unique_items, we do not need it
        unexpanded_module_sets.sort(key=lambda x: x.name)
        for unexpanded_module_set in unexpanded_module_sets:
            self._expand_single_module_set(unexpanded_module_set)

    def _resolve_guessed_modules(self, modules: list[Module]) -> list[Module]:
        ctx = self.context

        # We didn't necessarily fully expand all module-sets available in the
        # input_modules_and_options when we were resolving selectors.
        # Because of this we may need to go a step further and expand out all
        # remaining module-sets in rcFileModulesAndModuleSets if we have "guess"
        # modules still left over (since they might be Case 3), and see if we can
        # then successfully match.

        if not any(module.get_option("#guessed-kde-project", "module") for module in modules):
            return modules

        self._expand_all_unexpanded_module_sets()

        results: list[Module] = []

        # We use foreach since we *want* to be able to replace the iterated variable
        # if we find an existing module.
        for guessed_module in modules:
            if not guessed_module.get_option("#guessed-kde-project", "module"):
                results.append(guessed_module)
                continue

            # If the module we want could be found from within our rc-file
            # module-sets (even implicitly), use it. Otherwise, assume
            # kde-projects and evaluate now.
            if guessed_module.name in self.defined_modules:
                guessed_module: Module = self.defined_modules[guessed_module.name]
                results.append(guessed_module)
            else:
                mod_set = ModuleSetKDEProjects(ctx, "guessed_from_cmdline")
                mod_set.set_modules_to_find([guessed_module.name])

                set_results: list[Module] = self.expand_module_sets([mod_set])
                search_item: str = guessed_module.name
                if not set_results:
                    raise KBRuntimeError(f"{search_item} doesn't match any projects.")
                results.extend(set_results)

        return results

    def resolve_selectors_into_modules(self, selectors: list[str]) -> list[Module]:
        """
        Resolve the given list of module selectors into :class:`Module` objects.

        Uses the pending command-line options, ignore-selectors and available
        modules/module-sets.

        Selectors always choose an available :class:`Module` or :class:`ModuleSet` if
        present (based on the .name of each Module or ModuleSet, including any
        use-projects entries for ModuleSet objects). If a selector cannot be
        directly found then ModuleSet objects may be expanded into their
        constituent Module objects and the search performed again. If a selector
        still cannot be found an exception is thrown.

        Any embedded ModuleSets are expanded to Modules in the return value.

        The list of selected Modules is returned, in the approximate order of the
        input list (selectors for module-sets are expanded in arbitrary order).

        If you are just looking for a Module that should already be present, see
        resolve_module_if_present().

            modules = resolver.resolve_selectors_into_modules(["kdelibs", "juk"])

        Resolves already-stored module selectors into :class:`Module`, based on
        the options, modules, and module-sets set.

        Returns a list of :class:`Module` in build order, with any module-sets fully
        expanded. The desired options will be set for each :class:`Module` returned.
        """
        # Basically there are 3 types of selectors at this point:
        # 1. Directly named and defined modules or module-sets.
        # 2. Referenced (but undefined) modules. These are mentioned in a
        #    use-projects in a module set but not actually available as `Module`
        #    objects yet. But we know they will exist.
        # 3. Indirect modules. These are modules that do exist in the KDE project
        #    metadata, and will be pulled in once all module-sets are expanded
        #    (whether that's due to implicit wildcarding with use-projects, or due
        #    to dependency following). However, we don't even know the names for
        #    these yet.

        # We have to be careful to maintain order of selectors throughout.
        output_list: list[Module | ModuleSet] = []
        for selector in selectors:
            if selector in self.ignored_selectors:
                continue
            output_list.extend(self._resolve_single_selector(selector))

        modules: list[Module] = self.expand_module_sets(output_list)

        # If we have any "guessed" modules then they had no obvious source in the
        # rc-file. But they might still be implicitly from one of our module-sets
        # (Case 3).
        # We want them to use `Module`s from the rc-file modules/module-sets
        # instead of our shell Modules, if possible.
        modules: list[Module] = self._resolve_guessed_modules(modules)

        return modules

    def resolve_module_if_present(self, module_name: str) -> Module | None:
        """
        Similar to resolve_selectors_into_modules(), except that no exceptions are thrown if the module doesn't exist.

        Only a single module name is supported.
        """
        if self.referenced_modules:
            self._expand_all_unexpanded_module_sets()

        # We may not already know about modules that can be found in kde-projects,
        # so double-check by resolving module name into a kde-projects module-set
        # selector (the + syntax) and then expanding out the module-set so generated.
        if self.defined_modules.get(module_name) is None:
            try:
                self._expand_single_module_set(*self._resolve_single_selector("+" + module_name))
            except KBException:  # UnknownKdeProjectException for third party dependencies is caught here.
                pass

        ret: Module | None = self.defined_modules.get(module_name, None)
        return ret

    def expand_module_sets(self, build_module_list: list[Module | ModuleSet]) -> list[Module]:
        """
        Replace ModuleSets in the given list with their component Modules, and return the new list.

        Converts any :class:`ModuleSet` objects in the given list of Modules and
        ModuleSets into their component :class:`Module` objects (with proper options
        set, and ignored modules not present). These component objects are spliced
        into the list of module-type objects, replacing the ModuleSet they came
        from.

        The list of Module objects is then returned. The list passed in is
        not actually modified in this process.

        Similar to resolve_selectors_into_modules, except that in this case no
        "guessing" for Modules is allowed; the requested module is returned if
        present, or None otherwise. Also unlike resolve_selectors_into_modules, no
        exceptions are thrown if the module is not present.

        The only major side-effect is that all known module-sets are expanded if
        necessary before resorting to returning None.
        """
        ctx = self.context

        return_list: list[Module] = []
        for bm_set in build_module_list:
            results: list[Module | ModuleSet] = [bm_set]

            # If a module-set, need to update first so it can then apply its
            # settings to modules it creates, otherwise update Module directly.
            self._apply_options([bm_set])

            if isinstance(bm_set, ModuleSet):
                results: list[Module] = bm_set.convert_to_modules(ctx)
                self._apply_options(results)
            # else:
            #     pass

            return_list.extend(results)

        return return_list


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
registered into the project, the project uses the same build and scm types, is
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
in the rc-file). See expand_module_sets() and resolve_selectors_into_modules().

Each object so returned should already have the appropriate options
included (based on the cmdline_options member, which should be constructed
as the union of rc-file and cmdline options).

Note that dependency resolution is **not** handled by this class, see
:class:`DependencyResolver` for that.
"""
