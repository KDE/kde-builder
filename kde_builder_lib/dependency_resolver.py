# SPDX-FileCopyrightText: 2012, 2013, 2014, 2015, 2020, 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Callable
from typing import TYPE_CHECKING

from .kb_exception import ProgramError
from .debug import Debug
from .debug import KBLogger
from .module.module import Module
from .updater.updater import Updater
from .util.util import Util

if TYPE_CHECKING:
    from fileinput import FileInput

logger_depres = KBLogger.getLogger("dependency-resolver")


class DependencyResolver:
    """
    Handle resolving dependencies between modules.

    Each "module" from the perspective of this resolver is simply a module full name, as
    given by the KDE Project database (e.g. extragear/utils/kdesrc-build).
    """

    # sub uniq
    # {
    #     my %seen;
    #     return grep { ++($seen{$_}) == 1 } @_;
    # }

    def __init__(self, module_factory):
        """
        Initialize DependencyResolver.

        Args:
            module_factory: Function that creates :class:`Module` from
            kde-project module names. Used for :class:`Module` for which the user
            requested recursive dependency inclusion.

        Example:
        ::
            resolver = DependencyResolver(modNew)
            fh = os.open("file.txt", "r")
            resolver.read_dependency_data(fh)
            resolver.resolveDependencies(modules)
        """
        # dict mapping short module names (m) to a dict key by branch
        # name, the value of which is yet another dict (see
        # read_dependency_data). Note that this assumes KDE git infrastructure
        # ensures that all full module names (e.g.
        # kde/workspace/plasma-workspace) map to a *unique* short name (e.g.
        # plasma-workspace) by stripping leading path components
        self.dependencies_of = {}

        # dict mapping a wildcarded module name with no branch to a
        # list of module:branch dependencies.
        self.catch_all_dependencies = {}

        # function that will properly create a `Module` from a
        # given kde-project module name. Used to support automatically adding
        # dependencies to a build.
        self.module_factory = module_factory

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

    def _add_dependency(self, dep_name: str, dep_branch: str, src_name: str, src_branch: str, dep_key: str | None = "+") -> None:
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

    def read_dependency_data(self, fh: FileInput) -> None:
        """
        Read in dependency data in a pseudo-Makefile format.

        See repo-metadata/dependencies/dependency-data.

        Args:
            fh: Filehandle to read dependencies from (should already be opened).

        Raises:
            Exception: Can throw an exception on I/O errors or malformed dependencies.
        """
        dependency_atom = re.compile(
            r"^\s*"  # Clear leading whitespace
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
            r"\s*$"  # Ensure no trailing cruft. Any whitespace should end line
        )

        for line in fh:
            # Strip comments, skip empty lines.
            line = re.sub(r"#.*$", "", line)
            if re.match(r"^\s*$", line):
                continue

            if not re.match(dependency_atom, line):
                raise ProgramError(f"Invalid line {line} when reading dependency data.")

            match = re.search(dependency_atom, line)
            if match:
                dependent_item = match.group(1)
                dependent_branch = match.group(2)
                source_item = match.group(3)
                source_branch = match.group(4)
            else:
                dependent_item = None
                dependent_branch = None
                source_item = None
                source_branch = None

            # Ignore "catch-all" dependencies where the source is the catch-all
            if source_item.endswith("*"):
                logger_depres.warning("\tIgnoring dependency on wildcard project grouping " + f"on line {fh.filelineno()} of repo-metadata/dependencies/dependency-data")
                continue

            dependent_branch = dependent_branch or "*"  # If no branch, apply catch-all flag
            source_branch = source_branch or "*"

            # _shorten_module_name may remove negation marker so check now
            dep_key = "-" if source_item.startswith("-") else "+"
            source_item = re.sub("^-", "", source_item)  # remove negation marker if name already short

            # Source can never be a catch-all, so we can shorten early. Also,
            # we *must* shorten early to avoid a dependency on a long path.
            source_item = self._shorten_module_name(source_item)

            # Handle catch-all dependent groupings
            if re.match(r"\*$", dependent_item):
                self.catch_all_dependencies[dependent_item] = self.catch_all_dependencies.get(dependent_item, [])
                self.catch_all_dependencies[dependent_item].append(f"{source_item}:{source_branch}")
                continue

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

    def _lookup_direct_dependencies(self, path: str, branch: str) -> dict:

        direct_deps = []
        exclusions = []

        item = self._shorten_module_name(path)
        module_dep_entry = self.dependencies_of.get(f"{item}:*", None)

        if module_dep_entry:
            logger_depres.debug(f"handling dependencies for: {item} without branch (*)")
            direct_deps.extend(module_dep_entry["+"])
            exclusions.extend(module_dep_entry["-"])

        if branch and branch != "*":
            module_dep_entry = self.dependencies_of.get(f"{item}:{branch}", None)
            if module_dep_entry:
                logger_depres.debug(f"handling dependencies for: {item} with branch ({branch})")
                direct_deps.extend(module_dep_entry["+"])
                exclusions.extend(module_dep_entry["-"])

        # Apply catch-all dependencies but only for KDE modules, not third-party
        # modules. See _get_dependency_path_of for how this is detected.
        if not re.match(r"^third-party/", item):
            for catch_all, deps in self.catch_all_dependencies.items():
                prefix = catch_all
                prefix = re.sub(r"\*$", "", prefix)

                if re.match(f"^{prefix}", path) or not prefix:
                    direct_deps.extend(deps)

        for exclusion in exclusions:
            # Remove only modules at the exact given branch as a dep.
            # However, catch-alls can remove catch-alls.
            # But catch-alls cannot remove a specific branch, such exclusions have
            # to also be specific.
            direct_deps = [directDep for directDep in direct_deps if directDep != exclusion]

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
            dep_item = self._shorten_module_name(dep_path)
            if dep_item == item:
                logger_depres.debug(f"\tBreaking trivial cycle of b[{dep_item}] -> b[{item}]")
                result["trivial_cycles"] += 1
                continue

            if dep_item in result["dependencies"]:
                logger_depres.debug(f"\tSkipping duplicate direct dependency b[{dep_item}] of b[{item}]")
            else:
                if not dep_branch:
                    dep_branch = ""
                # work-around: wildcard branches are a don't care, not an actual
                # branch name/value
                if dep_branch == "" or dep_branch == "*":
                    dep_branch = None
                result["dependencies"][dep_item] = {
                    "item": dep_item,
                    "path": dep_path,
                    "branch": dep_branch
                }
        return result

    @staticmethod
    def _run_dependency_vote(module_graph: dict) -> dict:
        for item in module_graph.keys():
            names = list(module_graph[item]["all_deps"]["items"].keys())
            for name in names:
                module_graph[name]["votes"][item] = module_graph[name]["votes"].get(item, 0) + 1
        return module_graph

    @staticmethod
    def _detect_dependency_cycle(module_graph, dep_item, item):
        dep_module_graph = module_graph[dep_item]
        if dep_module_graph.setdefault("traces", {}).get("status", None):
            if dep_module_graph["traces"]["status"] == 2:
                logger_depres.debug(f"Already resolved {dep_item} -- skipping")
                return dep_module_graph["traces"]["result"]
            else:
                if not Debug().is_testing():
                    logger_depres.error(f"Found a dependency cycle at: {dep_item} while tracing {item}")
                dep_module_graph["traces"]["result"] = 1
        else:
            dep_module_graph["traces"]["status"] = 1
            dep_module_graph["traces"]["result"] = 0

            names = list(dep_module_graph["deps"].keys())
            for name in names:
                if DependencyResolver._detect_dependency_cycle(module_graph, name, item):
                    dep_module_graph["traces"]["result"] = 1
        dep_module_graph["traces"]["status"] = 2
        return dep_module_graph["traces"]["result"]

    @staticmethod
    def _check_dependency_cycles(module_graph: dict) -> int:
        errors = 0

        # sorted() is used for module_graph.keys() because in perl the dict keys are returned in random way.
        # So for reproducibility while debugging, the sort was added there.
        # In python 3.7 the keys are returned in the order of adding them.
        # To be able to easily compare perl and python versions, I (Andrew Shark) sorted keys as it is done there.
        # After we drop perl version, we can remove the unneeded sorting.

        for item in sorted(module_graph.keys()):
            if DependencyResolver._detect_dependency_cycle(module_graph, item, item):
                logger_depres.error(f"Somehow there is a circular dependency involving b[{item}]! :(")
                logger_depres.error("Please file a bug against repo-metadata about this!")
                errors += 1
        return errors

    @staticmethod
    def _copy_up_dependencies_for_module(module_graph: dict, item: str) -> None:
        all_deps = module_graph[item]["all_deps"]

        if "done" in all_deps:
            logger_depres.debug(f"\tAlready copied up dependencies for b[{item}] -- skipping")
        else:
            logger_depres.debug(f"\tCopying up dependencies and transitive dependencies for item: b[{item}]")
            all_deps["items"] = {}

            names = module_graph[item]["deps"].keys()
            for name in names:
                if name in all_deps["items"]:
                    logger_depres.debug(f"\tAlready copied up (transitive) dependency on b[{name}] for b[{item}] -- skipping")
                else:
                    DependencyResolver._copy_up_dependencies_for_module(module_graph, name)
                    copied = list(module_graph[name]["all_deps"]["items"])
                    for copy in copied:
                        if copy in all_deps["items"]:
                            logger_depres.debug(f"\tAlready copied up (transitive) dependency on b[{copy}] for b[{item}] -- skipping")
                        else:
                            all_deps["items"][copy] = all_deps["items"].get(copy, 0) + 1
                    all_deps["items"][name] = all_deps["items"].get(name, 0) + 1
            all_deps["done"] = all_deps.get("done", 0) + 1

    @staticmethod
    def _copy_up_dependencies(module_graph: dict) -> dict:
        for item in module_graph.keys():
            DependencyResolver._copy_up_dependencies_for_module(module_graph, item)
        return module_graph

    @staticmethod
    def _detect_branch_conflict(module_graph: dict, item: str, branch: str | None) -> str | None:
        if branch:
            sub_graph = module_graph[item]
            previously_selected_branch = sub_graph.get(branch, None)

            if previously_selected_branch and previously_selected_branch != branch:
                return previously_selected_branch

        return None

    @staticmethod
    def _get_dependency_path_of(module: Module, item: str, path: str) -> str:
        if module:
            project_path = module.full_project_path()

            if not module.is_kde_project():
                project_path = f"third-party/{project_path}"

            logger_depres.debug(f"\tUsing path: \"b[{project_path}]\" for item: b[{item}]")
            return project_path

        logger_depres.debug(f"\tGuessing path: \"b[{path}]\" for item: b[{item}]")
        return path

    def _resolve_dependencies_for_module_description(self, module_graph: dict, module_desc: dict) -> dict:
        module = module_desc["module"]
        if module:
            Util.assert_isa(module, Module)

        item = module_desc["item"]
        branch = module_desc["branch"]
        pretty_branch = branch if branch else "*"
        include_dependencies = module.get_option("include-dependencies") if module else module_desc["include_dependencies"]

        errors = {
            "syntax_errors": 0,
            "trivial_cycles": 0,
            "branch_errors": 0
        }

        logger_depres.debug(f"Resolving dependencies for project: b[{item}]")

        for dep_item in sorted(module_graph[item]["deps"].keys()):
            dep_info = module_graph[item]["deps"][dep_item]
            dep_path = dep_info["path"]
            dep_branch = dep_info["branch"]

            pretty_dep_branch = dep_branch if dep_branch else "*"

            logger_depres.debug(f"\tdep-resolv: b[{item}:{pretty_branch}] depends on b[{dep_item}:{pretty_dep_branch}]")

            dep_module_graph = module_graph.get(dep_item, None)

            if dep_module_graph:
                previously_selected_branch = self._detect_branch_conflict(module_graph, dep_item, dep_branch)
                if previously_selected_branch:
                    logger_depres.error(f"r[Found a dependency conflict in branches (\"b[{previously_selected_branch}]\" is not \"b[{pretty_dep_branch}]\") for b[{dep_item}]! :(")
                    errors["branch_errors"] += 1
                else:
                    if dep_branch:
                        dep_module_graph["branch"] = dep_branch

            else:
                dep_module = self.module_factory(dep_item)
                resolved_path = DependencyResolver._get_dependency_path_of(dep_module, dep_item, dep_path)
                # May not exist, e.g. misspellings or "virtual" dependencies like kf5umbrella.
                if not dep_module:
                    logger_depres.debug(f"\tdep-resolve: Will not build virtual or undefined project: b[{dep_item}]\n")

                dep_lookup_result = self._lookup_direct_dependencies(resolved_path, dep_branch)

                errors["trivial_cycles"] += dep_lookup_result["trivial_cycles"]
                errors["syntax_errors"] += dep_lookup_result["syntax_errors"]

                module_graph[dep_item] = {
                    "votes": {},
                    "path": resolved_path,
                    "build": dep_module and True if include_dependencies else False,
                    "branch": dep_branch,
                    "deps": dep_lookup_result["dependencies"],
                    "all_deps": {},
                    "module": dep_module,
                    "traces": {}
                }

                dep_module_desc = {
                    "include_dependencies": include_dependencies,
                    "module": dep_module,
                    "item": dep_item,
                    "path": resolved_path,
                    "branch": dep_branch
                }

                if not module_graph[dep_item]["build"]:
                    logger_depres.debug(f" y[b[*] {item} depends on {dep_item}, but no project builds {dep_item} for this run.]")

                if dep_module and dep_branch and (self._get_branch_of(dep_module) or "") != dep_branch:
                    wrong_branch = self._get_branch_of(dep_module) or "?"
                    logger_depres.error(f" r[b[*] {item} needs {dep_item}:{pretty_dep_branch}, not {dep_item}:{wrong_branch}]")
                    errors["branch_errors"] += 1

                logger_depres.debug(f"Resolving transitive dependencies for project: b[{item}] (via: b[{dep_item}:{pretty_dep_branch}])")
                resolv_errors = self._resolve_dependencies_for_module_description(module_graph, dep_module_desc)

                errors["branch_errors"] += resolv_errors["branch_errors"]
                errors["syntax_errors"] += resolv_errors["syntax_errors"]
                errors["trivial_cycles"] += resolv_errors["trivial_cycles"]
        return errors

    def resolve_to_module_graph(self, modules: list[Module]) -> dict:
        module_graph = {}

        result = {
            "graph": module_graph,
            "errors": {
                "branch_errors": 0,
                "path_errors": 0,
                "trivial_cycles": 0,
                "syntax_errors": 0,
                "cycles": 0
            }
        }
        errors = result["errors"]

        for module in modules:
            item = module.name  # _shorten_module_name(path)
            branch = self._get_branch_of(module)
            path = DependencyResolver._get_dependency_path_of(module, item, "")

            if not path:
                logger_depres.error(f"r[Unable to determine project/dependency path of project: {item}]")
                errors["path_errors"] += 1
                continue

            if item in module_graph and module_graph[item]:
                logger_depres.debug(f"Project pulled in previously through (transitive) dependencies: {item}")
                previously_selected_branch = self._detect_branch_conflict(module_graph, item, branch)
                if previously_selected_branch:
                    logger_depres.error(f"r[Found a dependency conflict in branches (\"b[{previously_selected_branch}]\" is not \"b[{branch}]\") for b[{item}]! :(")
                    errors["branch_errors"] += 1
                elif branch:
                    module_graph[item][branch] = branch

                # May have been pulled in via dependencies but not yet marked for
                # build. Do so now, since it is listed explicitly in @modules
                module_graph[item]["build"] = True
            else:
                dep_lookup_result = self._lookup_direct_dependencies(path, branch)

                errors["trivial_cycles"] += dep_lookup_result["trivial_cycles"]
                errors["syntax_errors"] += dep_lookup_result["syntax_errors"]

                module_graph[item] = {
                    "votes": {},
                    "path": path,
                    "build": True,
                    "branch": branch,
                    "module": module,
                    "deps": dep_lookup_result["dependencies"],
                    "all_deps": {},
                    "traces": {}
                }

                module_desc = {
                    "include_dependencies": module.get_option("include-dependencies"),
                    "path": path,
                    "item": item,
                    "branch": branch,
                    "module": module
                }

                resolv_errors = self._resolve_dependencies_for_module_description(module_graph, module_desc)

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

            result["graph"] = None
            return result

        trivial_cycles = errors["trivial_cycles"]

        if trivial_cycles:
            logger_depres.debug(f"Total of \"trivial\" dependency cycles detected & eliminated: {trivial_cycles}")

        cycles = self._check_dependency_cycles(module_graph)

        if cycles:
            logger_depres.error(f"Total of items with at least one circular dependency detected: {errors}")
            logger_depres.error("Unable to resolve dependency graph")

            result["cycles"] = cycles
            result["graph"] = None
            return result
        else:
            result["graph"] = self._run_dependency_vote(DependencyResolver._copy_up_dependencies(module_graph))
            return result

    @staticmethod
    def _descend_module_graph(module_graph, callback, node_info, context) -> None:
        depth = node_info["depth"]
        current_item = node_info["current_item"]
        current_branch = node_info["current_branch"]

        sub_graph = module_graph[current_item]
        callback(node_info, sub_graph["module"], context)

        depth += 1

        items = list(sub_graph["deps"].keys())

        item_count = len(items)
        item_index = 1

        for item in items:
            sub_graph = module_graph[item]
            branch = sub_graph.get("branch", "")
            item_info = {
                "build": sub_graph["build"],
                "depth": depth,
                "idx": item_index,
                "count": item_count,
                "current_item": item,
                "current_branch": branch,
                "parent_item": current_item,
                "parent_branch": current_branch
            }
            DependencyResolver._descend_module_graph(module_graph, callback, item_info, context)
            item_index += 1

    @staticmethod
    def walk_module_dependency_trees(module_graph: dict, callback: Callable, context: dict, modules: list[Module]) -> None:

        item_count = len(modules)
        item_index = 1

        for module in modules:
            Util.assert_isa(module, Module)
            item = module.name
            sub_graph = module_graph[item]
            branch = sub_graph.get("branch", "")
            info = {
                "build": sub_graph["build"],
                "depth": 0,
                "idx": item_index,
                "count": item_count,
                "current_item": item,
                "current_branch": branch,
                "parent_item": "",
                "parent_branch": ""
            }
            DependencyResolver._descend_module_graph(module_graph, callback, info, context)
            item_index += 1

    @staticmethod
    def make_comparison_func(module_graph: dict) -> Callable:

        def _compare_build_order_depends(a, b):
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

            votes = len(b_votes.keys()) - len(a_votes.keys())

            if votes:
                return votes

            # If there is no good reason to perfer one module over another,
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

        return _compare_build_order_depends

    @staticmethod
    def sort_modules_into_build_order(module_graph: dict) -> list[Module]:
        resolved = list(module_graph.keys())
        built = [el for el in resolved if module_graph[el]["build"] and module_graph[el]["module"]]
        prioritised = sorted(built, key=cmp_to_key(DependencyResolver.make_comparison_func(module_graph)))
        modules = [module_graph[key]["module"] for key in prioritised]
        return modules

    @staticmethod
    def _get_branch_of(module: Module) -> str | None:
        """
        Extract the branch of the given Module by calling its scm object's branch-determining method.

        It also ensures that the branch
        returned was really intended to be a branch (as opposed to a detached HEAD);
        None is returned when the desired commit is not a branch name, otherwise
        the user-requested branch name is returned.
        """
        scm = module.scm()

        # when the module's SCM is not git,
        # assume the default "no particular" branch wildcard

        if not isinstance(scm, Updater):
            return None

        branch, sourcetype = scm.determine_preferred_checkout_source(module)
        return branch if sourcetype == "branch" else None
