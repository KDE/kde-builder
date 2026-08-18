# SPDX-FileCopyrightText: 2012, 2013, 2014, 2015, 2020, 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from functools import cmp_to_key
import re
from io import TextIOWrapper

from kde_builder.kb_exception import KBRuntimeError
from kde_builder.debug import Debug
from kde_builder.debug import KBLogger
from kde_builder.module.module import Module
from kde_builder.module_resolver import ModuleResolver


logger_depres = KBLogger.getLogger("dependency-resolver")


class DependencyResolver:
    """
    Handle resolving dependencies between modules.

    Each "module" from the perspective of this resolver is simply a module full name, as
    given by the KDE Project database (e.g. extragear/utils/kdesrc-build).
    """

    def __init__(self, module_resolver: ModuleResolver):
        self.dependencies_of = {}

        self.module_resolver = module_resolver
        """
        ModuleResolver object, that will properly create a `Module` from a given kde-project module name. Used to support automatically adding dependencies to a build.
        """

        self.dependency_graph = {}

    @staticmethod
    def _shorten_module_name(name: str) -> str:
        """
        Return the "short" module name of kde-project full project paths.

        E.g. "kde/kdelibs/foo" would be shortened to "foo".

        Args:
            name: A string holding the full module virtual path

        Returns:
            The module name.
        """
        name = re.sub(r"^.*/", "", name)  # Uses greedy capture by default
        return name

    def _add_dependency(self, dep_name: str, dep_branch: str, src_name: str, src_branch: str, dep_key: str = "+") -> None:
        """
        Add an edge in the dependency graph from ``dep_name`` (at the given branch) to ``src_name`` (at its respective branch).

        Use ``*`` as the branch name if it is not important.
        """
        # Initialize with dict if not already defined. The dict will hold
        #     "-": []  # list of explicit *NON* dependencies of item:branch
        #     "+": []  # list of dependencies of item:branch
        #
        # Each dependency item is tracked at the module:branch level, and there
        # is always at least an entry for module:*, where "*" means branch
        # is unspecified and should only be used to add dependencies, never
        # take them away.
        #
        # Finally, all (non-)dependencies in a list are also of the form
        # fullname:branch, where "*" is a valid branch.
        if f"{dep_name}:*" not in self.dependencies_of:
            self.dependencies_of[f"{dep_name}:*"] = {
                "-": [],
                "+": []
            }

        # Create actual branch entry if not present
        if f"{dep_name}:{dep_branch}" not in self.dependencies_of:
            self.dependencies_of[f"{dep_name}:{dep_branch}"] = {
                "-": [],
                "+": []
            }

        self.dependencies_of[f"{dep_name}:{dep_branch}"][dep_key].append(f"{src_name}:{src_branch}")

    def read_dependency_data(self, fh: TextIOWrapper) -> None:
        """
        Read in dependency data in a pseudo-Makefile format.

        See repo-metadata/kde-dependencies/.

        Args:
            fh: Filehandle to read dependencies from (should already be opened).

        Raises:
            KBRuntimeError: On malformed dependencies.
        """
        dependency_atom = re.compile(
            r"([^\[:\s]+)"  # (1) Capture anything not a [, :, or whitespace (dependent item)
            r"\s*"  # Clear whitespace we didn't capture
            r"(?:\["  # Open a non-capture group...
            r"([^]:\s]+)"  # (2) Capture branch name without brackets
            r"])?"  # Close group, make optional
            r"\s*"  # Clear whitespace we didn't capture
            r":"
            r"\s*"
            r"([^\s\[]+)"  # (3) Capture all non-whitespace (source item)
            r"(?:\s*\["  # Open a non-capture group...
            r"([^]\s]+)"  # (4) Capture branch name without brackets
            r"])?"  # Close group, make optional
            r"$"  # Ensure no trailing cruft.
        )

        for line in fh:
            line = line.split("#", 1)[0].strip()  # Remove comments, leading and trailing whitespace and newlines
            if not line:
                continue

            match = dependency_atom.match(line)
            if not match:
                raise KBRuntimeError(f"Invalid line {line} when reading dependency data.")

            dependent_item, dependent_branch, source_item, source_branch = match.groups()

            dependent_branch = dependent_branch or "*"  # If no branch, apply catch-all flag
            source_branch = source_branch or "*"

            # _shorten_module_name may remove negation marker so check now
            dep_key = "-" if source_item.startswith("-") else "+"
            source_item = source_item.removeprefix("-")  # remove negation marker if name already short

            source_item = self._shorten_module_name(source_item)
            dependent_item = self._shorten_module_name(dependent_item)

            self._add_dependency(dependent_item, dependent_branch, source_item, source_branch, dep_key)

        self._canonicalize_dependencies()

    def _canonicalize_dependencies(self) -> None:
        """
        Ensure that all stored dependencies are stored in a way that allows for reproducible dependency ordering.

        Assuming the same dependency items and same selectors are used.
        """
        for dependencies in self.dependencies_of.values():
            dependencies["-"] = sorted(dependencies["-"])
            dependencies["+"] = sorted(dependencies["+"])

    def _lookup_direct_dependencies(self, module_name: str, branch: str) -> dict:

        direct_deps = []
        exclusions = []

        module_dep_entry = self.dependencies_of.get(f"{module_name}:*", None)

        if module_dep_entry:
            logger_depres.debug(f"handling dependencies for: {module_name} without branch (*)")
            direct_deps.extend(module_dep_entry["+"])
            exclusions.extend(module_dep_entry["-"])

        if branch and branch != "*":
            module_dep_entry = self.dependencies_of.get(f"{module_name}:{branch}", None)
            if module_dep_entry:
                logger_depres.debug(f"handling dependencies for: {module_name} with branch ({branch})")
                direct_deps.extend(module_dep_entry["+"])
                exclusions.extend(module_dep_entry["-"])

        for exclusion in exclusions:
            # Remove only modules at the exact given branch as a dep.
            # However, catch-alls can remove catch-alls.
            # But catch-alls cannot remove a specific branch, such exclusions have
            # to also be specific.
            direct_deps = [direct_dep for direct_dep in direct_deps if direct_dep != exclusion]

        result = {
            "syntax_errors": 0,
            "trivial_cycles": 0,
            "dependencies": {}
        }

        for dep in direct_deps:
            dep_path, dep_branch = re.match(r"^([^:]+):(.*)$", dep).groups()
            if not dep_path:
                logger_depres.error(f"r[Invalid dependency declaration: b[{dep}]]")
                result["syntax_errors"] += 1
                continue
            dep_module_name = self._shorten_module_name(dep_path)
            if dep_module_name == module_name:
                logger_depres.debug(f"\tBreaking trivial cycle of b[{dep_module_name}] -> b[{module_name}]")
                result["trivial_cycles"] += 1
                continue

            if dep_module_name in result["dependencies"]:
                logger_depres.debug(f"\tSkipping duplicate direct dependency b[{dep_module_name}] of b[{module_name}]")
            else:
                if not dep_branch:
                    dep_branch = ""
                # work-around: wildcard branches are a don't care, not an actual
                # branch name/value
                if dep_branch == "" or dep_branch == "*":
                    dep_branch = None
                result["dependencies"][dep_module_name] = {
                    "branch": dep_branch
                }
        return result

    def _run_dependency_vote(self) -> None:
        module_graph = self.dependency_graph
        for module_name in module_graph.keys():
            names = list(module_graph[module_name]["all_deps"]["items"].keys())
            for name in names:
                module_graph[name]["votes"][module_name] = module_graph[name]["votes"].get(module_name, 0) + 1
        return

    def _detect_dependency_cycle(self, dep_module_name, module_name):
        module_graph = self.dependency_graph
        dep_module_graph = module_graph[dep_module_name]
        if dep_module_graph.setdefault("traces", {}).get("status", None):
            if dep_module_graph["traces"]["status"] == 2:
                logger_depres.debug(f"Already resolved {dep_module_name} -- skipping")
                return dep_module_graph["traces"]["result"]
            else:
                if not Debug().is_testing():
                    logger_depres.error(f"Found a dependency cycle at: {dep_module_name} while tracing {module_name}")
                dep_module_graph["traces"]["result"] = 1
        else:
            dep_module_graph["traces"]["status"] = 1
            dep_module_graph["traces"]["result"] = 0

            names = list(dep_module_graph["deps"].keys())
            for name in names:
                if self._detect_dependency_cycle(name, module_name):
                    dep_module_graph["traces"]["result"] = 1
        dep_module_graph["traces"]["status"] = 2
        return dep_module_graph["traces"]["result"]

    def _check_dependency_cycles(self) -> int:
        module_graph = self.dependency_graph
        errors = 0

        # sorted() is used for module_graph.keys() because in perl the dict keys are returned in random way.
        # So for reproducibility while debugging, the sort was added there.
        # In python 3.7 the keys are returned in the order of adding them.
        # To be able to easily compare perl and python versions, I (Andrew Shark) sorted keys as it is done there.
        # After we drop perl version, we can remove the unneeded sorting.

        for module_name in sorted(module_graph.keys()):
            if self._detect_dependency_cycle(module_name, module_name):
                logger_depres.error(f"Somehow there is a circular dependency involving b[{module_name}]! :(")
                logger_depres.error("Please file a bug against repo-metadata about this!")
                errors += 1
        return errors

    def _copy_up_dependencies_for_module(self, module_name: str) -> None:
        module_graph = self.dependency_graph
        all_deps = module_graph[module_name]["all_deps"]

        if "done" in all_deps:
            logger_depres.debug(f"\tAlready copied up dependencies for b[{module_name}] -- skipping")
        else:
            logger_depres.debug(f"\tCopying up dependencies and transitive dependencies for item: b[{module_name}]")
            all_deps["items"] = {}

            names = module_graph[module_name]["deps"].keys()
            for name in names:
                if name in all_deps["items"]:
                    logger_depres.debug(f"\tAlready copied up (transitive) dependency on b[{name}] for b[{module_name}] -- skipping")
                else:
                    self._copy_up_dependencies_for_module(name)
                    copied = list(module_graph[name]["all_deps"]["items"])
                    for copy in copied:
                        if copy in all_deps["items"]:
                            logger_depres.debug(f"\tAlready copied up (transitive) dependency on b[{copy}] for b[{module_name}] -- skipping")
                        else:
                            all_deps["items"][copy] = all_deps["items"].get(copy, 0) + 1
                    all_deps["items"][name] = all_deps["items"].get(name, 0) + 1
            all_deps["done"] = all_deps.get("done", 0) + 1

    def _copy_up_dependencies(self) -> None:
        module_graph = self.dependency_graph
        for module_name in module_graph.keys():
            self._copy_up_dependencies_for_module(module_name)
        return

    def _detect_branch_conflict(self, module_name: str, branch: str | None) -> str | None:
        module_graph = self.dependency_graph
        if branch:
            sub_graph = module_graph[module_name]
            previously_selected_branch = sub_graph.get(branch, None)

            if previously_selected_branch and previously_selected_branch != branch:
                return previously_selected_branch

        return None

    @staticmethod
    def _get_dependency_path_of(module: Module) -> str:
        if module.is_kde_project():
            project_path = module.get_repopath()
        else:
            project_path = f"third-party/{module.name}"
        return project_path

    def _resolve_dependencies_for_module_description(self, module_desc: dict) -> dict:
        module_graph = self.dependency_graph
        module = module_desc["module"]
        module_name = module_desc["module_name"]
        branch = module_desc["branch"]
        pretty_branch = branch if branch else "*"
        include_dependencies = module.get_option("include-dependencies") if module else False

        errors = {
            "syntax_errors": 0,
            "trivial_cycles": 0,
            "branch_errors": 0
        }

        logger_depres.debug(f"Resolving dependencies for project: b[{module_name}]")

        for dep_module_name in sorted(module_graph[module_name]["deps"].keys()):
            dep_info = module_graph[module_name]["deps"][dep_module_name]
            dep_branch = dep_info["branch"]

            pretty_dep_branch = dep_branch if dep_branch else "*"

            logger_depres.debug(f"\tdep-resolv: b[{module_name}:{pretty_branch}] depends on b[{dep_module_name}:{pretty_dep_branch}]")

            dep_module_graph = module_graph.get(dep_module_name, None)

            if dep_module_graph:
                previously_selected_branch = self._detect_branch_conflict(dep_module_name, dep_branch)
                if previously_selected_branch:
                    logger_depres.error(f"r[Found a dependency conflict in branches (\"b[{previously_selected_branch}]\" is not \"b[{pretty_dep_branch}]\") for b[{dep_module_name}]! :(")
                    errors["branch_errors"] += 1
                else:
                    if dep_branch:
                        dep_module_graph["branch"] = dep_branch

            else:
                dep_module: Module | None = self.module_resolver.resolve_module_if_present(dep_module_name)
                if not dep_module:
                    # Still, we will place the graph entry, so that --dependency-tree could show the not-built project in tree.
                    module_graph[dep_module_name] = {
                        "votes": {},
                        "build": False,
                        "branch": "",
                        "deps": {},
                        "all_deps": {},
                        "module": None,
                        "traces": {}
                    }

                    continue

                dep_lookup_result = self._lookup_direct_dependencies(dep_module_name, dep_branch)

                errors["trivial_cycles"] += dep_lookup_result["trivial_cycles"]
                errors["syntax_errors"] += dep_lookup_result["syntax_errors"]

                module_graph[dep_module_name] = {
                    "votes": {},
                    "build": include_dependencies,
                    "branch": dep_branch,
                    "deps": dep_lookup_result["dependencies"],
                    "all_deps": {},
                    "module": dep_module,
                    "traces": {}
                }

                dep_module_desc = {
                    "module": dep_module,
                    "module_name": dep_module_name,
                    "branch": dep_branch
                }

                if not module_graph[dep_module_name]["build"]:
                    # Even if dep_module_name is not _yet_ selected to be built, it still may be marked to be built in this run,
                    # if other projects include it as a dependency, or if it selected in command line.
                    logger_depres.debug(f" y[b[*] {module_name} depends on {dep_module_name}, but {dep_module_name} is not marked to be built (at least yet).")

                if dep_branch and (self._get_branch_of(dep_module) or "") != dep_branch:
                    wrong_branch = self._get_branch_of(dep_module) or "?"
                    logger_depres.error(f" r[b[*] {module_name} needs {dep_module_name}:{pretty_dep_branch}, not {dep_module_name}:{wrong_branch}]")
                    errors["branch_errors"] += 1

                logger_depres.debug(f"Resolving transitive dependencies for project: b[{module_name}] (via: b[{dep_module_name}:{pretty_dep_branch}])")
                resolv_errors = self._resolve_dependencies_for_module_description(dep_module_desc)

                errors["branch_errors"] += resolv_errors["branch_errors"]
                errors["syntax_errors"] += resolv_errors["syntax_errors"]
                errors["trivial_cycles"] += resolv_errors["trivial_cycles"]
        return errors

    def resolve_to_module_graph(self, modules: list[Module]) -> None:
        module_graph = self.dependency_graph

        errors = {
            "branch_errors": 0,
            "path_errors": 0,
            "trivial_cycles": 0,
            "syntax_errors": 0,
            "cycles": 0
        }

        for module in modules:
            module_name = module.name
            branch = self._get_branch_of(module)

            if module_name in module_graph and module_graph[module_name]:
                logger_depres.debug(f"Project pulled in previously through (transitive) dependencies: {module_name}")
                previously_selected_branch = self._detect_branch_conflict(module_name, branch)
                if previously_selected_branch:
                    logger_depres.error(f"r[Found a dependency conflict in branches (\"b[{previously_selected_branch}]\" is not \"b[{branch}]\") for b[{module_name}]! :(")
                    errors["branch_errors"] += 1
                elif branch:
                    module_graph[module_name]["branch"] = branch

                # May have been pulled in via dependencies but not yet marked for
                # build. Do so now, since it is listed explicitly in modules list.
                module_graph[module_name]["build"] = True
            else:
                dep_lookup_result = self._lookup_direct_dependencies(module_name, branch)

                errors["trivial_cycles"] += dep_lookup_result["trivial_cycles"]
                errors["syntax_errors"] += dep_lookup_result["syntax_errors"]

                module_graph[module_name] = {
                    "votes": {},
                    "build": True,
                    "branch": branch,
                    "module": module,
                    "deps": dep_lookup_result["dependencies"],
                    "all_deps": {},
                    "traces": {}
                }

                module_desc = {
                    "module_name": module_name,
                    "branch": branch,
                    "module": module
                }

                resolv_errors = self._resolve_dependencies_for_module_description(module_desc)

                errors["branch_errors"] += resolv_errors["branch_errors"]
                errors["syntax_errors"] += resolv_errors["syntax_errors"]
                errors["trivial_cycles"] += resolv_errors["trivial_cycles"]

        path_errors = errors["path_errors"]
        if path_errors:
            logger_depres.error(f"Total of items which were not resolved due to path lookup failure: {path_errors}")

        branch_errors = errors["branch_errors"]
        if branch_errors:
            logger_depres.error(f"Total of branch conflicts detected: {branch_errors}")

        syntax_errors = errors["syntax_errors"]
        if syntax_errors:
            logger_depres.error(f"Total of encountered syntax errors: {syntax_errors}")

        if syntax_errors or path_errors or branch_errors:
            logger_depres.error("Unable to resolve dependency graph")
            module_graph.clear()
            return

        trivial_cycles = errors["trivial_cycles"]

        if trivial_cycles:
            logger_depres.debug(f"Total of \"trivial\" dependency cycles detected & eliminated: {trivial_cycles}")

        cycles = self._check_dependency_cycles()

        if cycles:
            logger_depres.error(f"Total of items with at least one circular dependency detected: {errors}")
            logger_depres.error("Unable to resolve dependency graph")

            errors["cycles"] = cycles
            module_graph.clear()
            return

        self._copy_up_dependencies()
        self._run_dependency_vote()
        return

    def _descend_module_graph(self, mode: str, node_info, context) -> None:
        module_graph = self.dependency_graph
        depth = node_info["depth"]
        current_module_name = node_info["current_module_name"]
        current_branch = node_info["current_branch"]

        sub_graph = module_graph[current_module_name]
        if mode == "tree":
            self._yield_module_dependency_tree_entry(node_info, sub_graph["module"], context)
        else:
            self._yield_module_dependency_tree_entry_full_path(node_info, sub_graph["module"], context)

        depth += 1

        module_names = list(sub_graph["deps"].keys())

        item_count = len(module_names)
        item_index = 1

        for module_name in module_names:
            sub_graph = module_graph[module_name]
            branch = sub_graph.get("branch", "")
            item_info = {
                "build": sub_graph["build"],
                "depth": depth,
                "idx": item_index,
                "count": item_count,
                "current_module_name": module_name,
                "current_branch": branch,
                "parent_module_name": current_module_name,
                "parent_branch": current_branch
            }
            self._descend_module_graph(mode, item_info, context)
            item_index += 1

    def walk_module_dependency_trees(self, mode: str, modules: list[Module]) -> None:
        module_graph = self.dependency_graph
        item_count = len(modules)
        item_index = 1

        context = {
            "stack": [""],
            "depth": 0,
            "report": lambda *args: print(*args, sep="", end="\n")
        }

        for module in modules:
            module_name = module.name
            sub_graph = module_graph[module_name]
            branch = sub_graph.get("branch", "")
            info = {
                "build": sub_graph["build"],
                "depth": 0,
                "idx": item_index,
                "count": item_count,
                "current_module_name": module_name,
                "current_branch": branch,
                "parent_module_name": "",
                "parent_branch": ""
            }
            self._descend_module_graph(mode, info, context)
            item_index += 1

    def _compare_build_order_depends(self, a, b):
        module_graph = self.dependency_graph

        # comparison results uses:
        # -1 if a < b
        # 0 if a == b
        # 1 if a > b

        a_votes = module_graph[a]["votes"]
        b_votes = module_graph[b]["votes"]

        # Enforce a strict dependency ordering.
        # The case where both are true should never happen, since that would
        # amount to a cycle, and cycle detection is supposed to have been
        # performed beforehand.

        b_depends_on_a = a_votes.get(b, 0)
        a_depends_on_b = b_votes.get(a, 0)
        order = -1 if b_depends_on_a else (1 if a_depends_on_b else 0)

        if order:
            return order

        # Assuming no dependency relation, next sort by "popularity":
        # the item with the most votes (back edges) is depended on the most
        # so it is probably a good idea to build that one earlier to help
        # maximise the duration of time for which builds can be run in parallel

        votes = len(b_votes) - len(a_votes)

        if votes:
            return votes

        # If there is no good reason to prefer one module over another,
        # simply sort by the order contained within the configuration file (if
        # present), which would be setup as the rc-file is read.

        a_rc_order: int = module_graph[a]["module"].create_id
        b_rc_order: int = module_graph[b]["module"].create_id
        config_order = (a_rc_order > b_rc_order) - (a_rc_order < b_rc_order)

        if config_order:
            return config_order

        # If the rc-file is not present then sort by name to ensure a reproducible
        # build order that isn't influenced by randomization of the runtime.
        return (a > b) - (a < b)

    def sort_modules_into_build_order(self) -> list[Module]:
        module_graph = self.dependency_graph
        resolved = list(module_graph.keys())
        built = [el for el in resolved if module_graph[el]["build"] and module_graph[el]["module"]]
        prioritised = sorted(built, key=cmp_to_key(self._compare_build_order_depends))
        modules = [module_graph[key]["module"] for key in prioritised]
        return modules

    @staticmethod
    def _get_branch_of(module: Module) -> str | None:
        """
        Determine checkout source of the given Module, ensure that the ref type is "branch" (as opposed to a detached HEAD), and return the branch name.

        When the ref_type is "branch", the branch name is returned. Otherwise, None is returned.
        """
        scm = module.scm

        ref_value, ref_type = scm.determine_preferred_checkout_source()
        if ref_type == "branch":
            return ref_value
        return None

    @staticmethod
    def _yield_module_dependency_tree_entry(node_info: dict, module: Module, context: dict) -> None:
        depth = node_info["depth"]
        index = node_info["idx"]
        count = node_info["count"]
        build = node_info["build"]
        current_module_name = node_info["current_module_name"]
        current_branch = node_info["current_branch"]

        build_status = "built" if build else "not built"
        status_info = f"({build_status}: {current_branch})" if current_branch else f"({build_status})"

        connector_stack = context["stack"]

        prefix = connector_stack.pop()

        while context["depth"] > depth:
            prefix = connector_stack.pop()
            context["depth"] -= 1

        connector_stack.append(prefix)

        if depth == 0:
            connector = prefix + " ── "
            connector_stack.append(prefix + (" " * 4))
        else:
            connector = prefix + ("└── " if index == count else "├── ")
            connector_stack.append(prefix + (" " * 4 if index == count else "│   "))

        context["depth"] = depth + 1
        context["report"](connector + current_module_name + " " + status_info)

    @staticmethod
    def _yield_module_dependency_tree_entry_full_path(node_info: dict, module: Module, context: dict) -> None:
        depth = node_info["depth"]
        current_module_name = node_info["current_module_name"]

        connector_stack = context["stack"]

        prefix = connector_stack.pop()

        while context["depth"] > depth:
            prefix = connector_stack.pop()
            context["depth"] -= 1

        connector_stack.append(prefix)

        connector = prefix
        connector_stack.append(prefix + current_module_name + "/")

        context["depth"] = depth + 1
        context["report"](connector + current_module_name)
