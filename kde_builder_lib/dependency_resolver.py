# SPDX-FileCopyrightText: 2012, 2013, 2014, 2015, 2020, 2022, 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from functools import cmp_to_key
import json
import re
from types import FunctionType

from .build_exception import BuildException
from .debug import Debug
from .debug import kbLogger
from .module.module import Module
from .updater.updater import Updater
from .util.util import Util

logger_depres = kbLogger.getLogger("dependency-resolver")

class DependencyResolver:
    """
    This class handles resolving dependencies between modules. Each "module"
    from the perspective of this resolver is simply a module full name, as
    given by the KDE Project database (e.g. extragear/utils/kdesrc-build).
    """

    # sub uniq
    # {
    #     my %seen;
    #     return grep { ++($seen{$_}) == 1 } @_;
    # }

    def __init__(self, moduleFactoryRef):
        """
        Parameters:
            moduleFactoryRef: Function that creates :class:`Module` from
            kde-project module names. Used for :class:`Module` for which the user
            requested recursive dependency inclusion.

        Example:
        ::
            resolver = DependencyResolver(modNew)
            fh = os.open('file.txt', "r")
            resolver.read_dependency_data(fh)
            resolver.resolveDependencies(modules)
        """

        # hash table mapping short module names (m) to a hashref key by branch
        # name, the value of which is yet another hashref (see
        # read_dependency_data). Note that this assumes KDE git infrastructure
        # ensures that all full module names (e.g.
        # kde/workspace/plasma-workspace) map to a *unique* short name (e.g.
        # plasma-workspace) by stripping leading path components
        self.dependenciesOf = {}

        # hash table mapping a wildcarded module name with no branch to a
        # listref of module:branch dependencies.
        self.catchAllDependencies = {}

        # reference to a sub that will properly create a `Module` from a
        # given kde-project module name. Used to support automatically adding
        # dependencies to a build.
        self.moduleFactoryRef = moduleFactoryRef

    @staticmethod
    def _shorten_module_name(name) -> str:
        """
        This method returns the "short" module name of kde-project full project paths.
        E.g. "kde/kdelibs/foo" would be shortened to "foo".

        Parameters:
            name: A string holding the full module virtual path

        Returns:
            The module name.
        """
        name = re.sub(r"^.*/", "", name)  # Uses greedy capture by default
        return name

    def _add_dependency(self, depName, depBranch, srcName, srcBranch, depKey="+") -> None:
        """
        Adds an edge in the dependency graph from ``depName`` (at the given branch) to
        ``srcName`` (at its respective branch). Use ``*`` as the branch name if it is
        not important.
        """
        dependenciesOfRef = self.dependenciesOf

        # Initialize with hashref if not already defined. The hashref will hold
        #     - => [ ] (list of explicit *NON* dependencies of item:$branch),
        #     + => [ ] (list of dependencies of item:$branch)
        #
        # Each dependency item is tracked at the module:branch level, and there
        # is always at least an entry for module:*, where '*' means branch
        # is unspecified and should only be used to add dependencies, never
        # take them away.
        #
        # Finally, all (non-)dependencies in a list are also of the form
        # fullname:branch, where "*" is a valid branch.
        if f"{depName}:*" not in dependenciesOfRef:
            dependenciesOfRef[f"{depName}:*"] = {
                "-": [],
                "+": []
            }

        # Create actual branch entry if not present
        if f"{depName}:{depBranch}" not in dependenciesOfRef:
            dependenciesOfRef[f"{depName}:{depBranch}"] = {
                "-": [],
                "+": []
            }

        dependenciesOfRef[f"{depName}:{depBranch}"][depKey].append(f"{srcName}:{srcBranch}")

    def read_dependency_data(self, fh) -> None:
        """
        Reads in dependency data in a pseudo-Makefile format.
        See repo-metadata/dependencies/dependency-data.

        Parameters:
            fh: Filehandle to read dependencies from (should already be opened).

        Raises:
            Exception: Can throw an exception on I/O errors or malformed dependencies.
        """
        dependenciesOfRef = self.dependenciesOf
        dependencyAtom = re.compile(
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

            if not re.match(dependencyAtom, line):
                BuildException.croak_internal(f"Invalid line {line} when reading dependency data.")

            match = re.search(dependencyAtom, line)
            if match:
                dependentItem = match.group(1)
                dependentBranch = match.group(2)
                sourceItem = match.group(3)
                sourceBranch = match.group(4)
            else:
                dependentItem = None
                dependentBranch = None
                sourceItem = None
                sourceBranch = None

            # Ignore "catch-all" dependencies where the source is the catch-all
            if sourceItem.endswith("*"):
                logger_depres.warning("\tIgnoring dependency on wildcard module grouping " + f"on line {fh.filelineno()} of repo-metadata/dependencies/dependency-data")
                continue

            dependentBranch = dependentBranch or "*"  # If no branch, apply catch-all flag
            sourceBranch = sourceBranch or "*"

            # _shorten_module_name may remove negation marker so check now
            depKey = "-" if sourceItem.startswith("-") else "+"
            sourceItem = re.sub("^-", "", sourceItem)  # remove negation marker if name already short

            # Source can never be a catch-all, so we can shorten early. Also,
            # we *must* shorten early to avoid a dependency on a long path.
            sourceItem = self._shorten_module_name(sourceItem)

            # Handle catch-all dependent groupings
            if re.match(r"\*$", dependentItem):
                self.catchAllDependencies[dependentItem] = self.catchAllDependencies.get(dependentItem, [])
                self.catchAllDependencies[dependentItem].append(f"{sourceItem}:{sourceBranch}")
                continue

            dependentItem = self._shorten_module_name(dependentItem)

            self._add_dependency(dependentItem, dependentBranch, sourceItem, sourceBranch, depKey)

        self._canonicalize_dependencies()

    def read_dependency_data_v2(self, fh) -> None:
        """
        Reads in v2-format dependency data from KDE repository database, using the KDE
        "invent" repository naming convention.

        Throws exception on read failure.

        ::

            fh = open("/path/to/dependency-data.json", "r")
            resolver.read_dependency_data_v2(fh)
        """
        logger_depres.warning("b[***] USING y[b[V2 DEPENDENCY METADATA], BUILD IS UNSUPPORTED")

        json_data = fh.read()

        if not json_data:
            BuildException.croak_runtime("Unable to read JSON dependency data")

        dependencies = json.loads(json_data)

        if not dependencies:
            BuildException.croak_runtime("Unable to decode V2 dependencies")

        if not dependencies.get("metadata_version", 1) == 2:
            BuildException.croak_runtime("Unknown dependency version")

        if not dependencies["module_dependencies"]:
            BuildException.croak_runtime("V2 dependencies contain no dependencies")

        for depModule, srcList in dependencies["module_dependencies"].items():
            depName = self._shorten_module_name(depModule)
            for srcModule in srcList:
                srcName = self._shorten_module_name(srcModule)
                self._add_dependency(depName, "*", srcName, "*")

        self._canonicalize_dependencies()

    def _canonicalize_dependencies(self) -> None:
        """
        Ensures that all stored dependencies are stored in a way that allows for
        reproducable dependency ordering (assuming the same dependency items and same
        selectors are used).
        """
        dependenciesOfRef = self.dependenciesOf

        for dependenciesRef in dependenciesOfRef.values():
            dependenciesRef["-"] = sorted(dependenciesRef["-"])
            dependenciesRef["+"] = sorted(dependenciesRef["+"])

    def _lookup_direct_dependencies(self, path, branch) -> dict:
        dependenciesOfRef = self.dependenciesOf

        directDeps = []
        exclusions = []

        item = self._shorten_module_name(path)
        moduleDepEntryRef = dependenciesOfRef.get(f"{item}:*", None)

        if moduleDepEntryRef:
            logger_depres.debug(f"handling dependencies for: {item} without branch (*)")
            directDeps.extend(moduleDepEntryRef["+"])
            exclusions.extend(moduleDepEntryRef["-"])

        if branch and branch != "*":
            moduleDepEntryRef = dependenciesOfRef.get(f"{item}:{branch}", None)
            if moduleDepEntryRef:
                logger_depres.debug(f"handling dependencies for: {item} with branch ({branch})")
                directDeps.extend(moduleDepEntryRef["+"])
                exclusions.extend(moduleDepEntryRef["-"])

        # Apply catch-all dependencies but only for KDE modules, not third-party
        # modules. See _get_dependency_path_of for how this is detected.
        if not re.match(r"^third-party/", item):
            for catchAll, deps in self.catchAllDependencies.items():
                prefix = catchAll
                prefix = re.sub(r"\*$", "", prefix)

                if re.match(f"^{prefix}", path) or not prefix:
                    directDeps.extend(deps)

        for exclusion in exclusions:
            # Remove only modules at the exact given branch as a dep.
            # However catch-alls can remove catch-alls.
            # But catch-alls cannot remove a specific branch, such exclusions have
            # to also be specific.
            directDeps = [directDep for directDep in directDeps if directDep != exclusion]

        result = {
            "syntaxErrors": 0,
            "trivialCycles": 0,
            "dependencies": {}
        }

        for dep in directDeps:
            depPath, depBranch = re.match(r"^([^:]+):(.*)$", dep).groups()
            if not depPath:
                logger_depres.error(f"r[Invalid dependency declaration: b[{dep}]]")
                result["syntaxErrors"] += 1
                continue
            depItem = self._shorten_module_name(depPath)
            if depItem == item:
                logger_depres.debug((f"\tBreaking trivial cycle of b[{depItem}] -> b[{item}]"))
                result["trivialCycles"] += 1
                continue

            if depItem in result["dependencies"]:
                logger_depres.debug(f"\tSkipping duplicate direct dependency b[{depItem}] of b[{item}]")
            else:
                if not depBranch:
                    depBranch = ""
                # work-around: wildcard branches are a don't care, not an actual
                # branch name/value
                if depBranch == "" or depBranch == "*":
                    depBranch = None
                result["dependencies"][depItem] = {
                    "item": depItem,
                    "path": depPath,
                    "branch": depBranch
                }
        return result

    @staticmethod
    def _run_dependency_vote(moduleGraph) -> dict:
        for item in moduleGraph.keys():
            names = list(moduleGraph[item]["allDeps"]["items"].keys())
            for name in names:
                moduleGraph[name]["votes"][item] = moduleGraph[name]["votes"].get(item, 0) + 1
        return moduleGraph

    @staticmethod
    def _detect_dependency_cycle(moduleGraph, depItem, item):
        depModuleGraph = moduleGraph[depItem]
        if depModuleGraph.setdefault("traces", {}).get("status", None):
            if depModuleGraph["traces"]["status"] == 2:
                logger_depres.debug(f"Already resolved {depItem} -- skipping")
                return depModuleGraph["traces"]["result"]
            else:
                if not Debug().is_testing():
                    logger_depres.error(f"Found a dependency cycle at: {depItem} while tracing {item}")
                depModuleGraph["traces"]["result"] = 1
        else:
            depModuleGraph["traces"]["status"] = 1
            depModuleGraph["traces"]["result"] = 0

            names = list(depModuleGraph["deps"].keys())
            for name in names:
                if DependencyResolver._detect_dependency_cycle(moduleGraph, name, item):
                    depModuleGraph["traces"]["result"] = 1
        depModuleGraph["traces"]["status"] = 2
        return depModuleGraph["traces"]["result"]

    def _check_dependency_cycles(self, moduleGraph) -> int:
        errors = 0

        # sorted() is used for moduleGraph.keys() because in perl the hash keys are returned in random way.
        # So for reproducibility while debugging, the sort was added there.
        # In python 3.7 the keys are returned in the order of adding them.
        # To be able to easily compare perl and python versions, I (Andrew Shark) sorted keys as it is done there.
        # After we drop perl version, we can remove the unneeded sorting.

        for item in sorted(moduleGraph.keys()):
            if DependencyResolver._detect_dependency_cycle(moduleGraph, item, item):
                logger_depres.error(f"Somehow there is a circular dependency involving b[{item}]! :(")
                logger_depres.error("Please file a bug against repo-metadata about this!")
                errors += 1
        return errors

    @staticmethod
    def _copy_up_dependencies_for_module(moduleGraph, item) -> None:
        allDeps = moduleGraph[item]["allDeps"]

        if "done" in allDeps:
            logger_depres.debug(f"\tAlready copied up dependencies for b[{item}] -- skipping")
        else:
            logger_depres.debug(f"\tCopying up dependencies and transitive dependencies for item: b[{item}]")
            allDeps["items"] = {}

            names = moduleGraph[item]["deps"].keys()
            for name in names:
                if name in allDeps["items"]:
                    logger_depres.debug(f"\tAlready copied up (transitive) dependency on b[{name}] for b[{item}] -- skipping")
                else:
                    DependencyResolver._copy_up_dependencies_for_module(moduleGraph, name)
                    copied = list(moduleGraph[name]["allDeps"]["items"])
                    for copy in copied:
                        if copy in allDeps["items"]:
                            logger_depres.debug(f"\tAlready copied up (transitive) dependency on b[{copy}] for b[{item}] -- skipping")
                        else:
                            allDeps["items"][copy] = allDeps["items"].get(copy, 0) + 1
                    allDeps["items"][name] = allDeps["items"].get(name, 0) + 1
            allDeps["done"] = allDeps.get("done", 0) + 1

    @staticmethod
    def _copy_up_dependencies(moduleGraph: dict) -> dict:
        for item in moduleGraph.keys():
            DependencyResolver._copy_up_dependencies_for_module(moduleGraph, item)
        return moduleGraph

    @staticmethod
    def _detect_branch_conflict(moduleGraph, item, branch) -> str | None:
        if branch:
            subGraph = moduleGraph[item]
            previouslySelectedBranch = subGraph.get(branch, None)

            if previouslySelectedBranch and previouslySelectedBranch != branch:
                return previouslySelectedBranch

        return None

    @staticmethod
    def _get_dependency_path_of(module, item, path) -> str:
        if module:
            projectPath = module.full_project_path()

            if not module.is_kde_project():
                projectPath = f"third-party/{projectPath}"

            logger_depres.debug(f"\tUsing path: 'b[{projectPath}]' for item: b[{item}]")
            return projectPath

        logger_depres.debug(f"\tGuessing path: 'b[{path}]' for item: b[{item}]")
        return path

    def _resolve_dependencies_for_module_description(self, moduleGraph, moduleDesc) -> dict:
        module = moduleDesc["module"]
        if module:
            Util.assert_isa(module, Module)

        path = moduleDesc["path"]
        item = moduleDesc["item"]
        branch = moduleDesc["branch"]
        prettyBranch = f"{branch}" if branch else "*"
        includeDependencies = module.get_option("include-dependencies") if module else moduleDesc["includeDependencies"]

        errors = {
            "syntaxErrors": 0,
            "trivialCycles": 0,
            "branchErrors": 0
        }

        logger_depres.debug(f"Resolving dependencies for module: b[{item}]")

        for depItem in sorted(moduleGraph[item]["deps"].keys()):
            depInfo = moduleGraph[item]["deps"][depItem]
            depPath = depInfo["path"]
            depBranch = depInfo["branch"]

            prettyDepBranch = f"{depBranch}" if depBranch else "*"

            logger_depres.debug(f"\tdep-resolv: b[{item}:{prettyBranch}] depends on b[{depItem}:{prettyDepBranch}]")

            depModuleGraph = moduleGraph.get(depItem, None)

            if depModuleGraph:
                previouslySelectedBranch = self._detect_branch_conflict(moduleGraph, depItem, depBranch)
                if previouslySelectedBranch:
                    logger_depres.error(f"r[Found a dependency conflict in branches ('b[{previouslySelectedBranch}]' is not 'b[{prettyDepBranch}]') for b[{depItem}]! :(")
                    errors["branchErrors"] += 1
                else:
                    if depBranch:
                        depModuleGraph["branch"] = depBranch

            else:
                depModule = self.moduleFactoryRef(depItem)
                resolvedPath = DependencyResolver._get_dependency_path_of(depModule, depItem, depPath)
                # May not exist, e.g. misspellings or 'virtual' dependencies like kf5umbrella.
                if not depModule:
                    logger_depres.debug(f"\tdep-resolve: Will not build virtual or undefined module: b[{depItem}]\n")

                depLookupResult = self._lookup_direct_dependencies(resolvedPath, depBranch)

                errors["trivialCycles"] += depLookupResult["trivialCycles"]
                errors["syntaxErrors"] += depLookupResult["syntaxErrors"]

                moduleGraph[depItem] = {
                    "votes": {},
                    "path": resolvedPath,
                    "build": depModule and True if includeDependencies else False,
                    "branch": depBranch,
                    "deps": depLookupResult["dependencies"],
                    "allDeps": {},
                    "module": depModule,
                    "traces": {}
                }

                depModuleDesc = {
                    "includeDependencies": includeDependencies,
                    "module": depModule,
                    "item": depItem,
                    "path": resolvedPath,
                    "branch": depBranch
                }

                if not moduleGraph[depItem]["build"]:
                    logger_depres.debug(f" y[b[*] {item} depends on {depItem}, but no module builds {depItem} for this run.]")

                if depModule and depBranch and (self._get_branch_of(depModule) or "") != f"{depBranch}":
                    wrongBranch = self._get_branch_of(depModule) or "?"
                    logger_depres.error(f" r[b[*] {item} needs {depItem}:{prettyDepBranch}, not {depItem}:{wrongBranch}]")
                    errors["branchErrors"] += 1

                logger_depres.debug(f"Resolving transitive dependencies for module: b[{item}] (via: b[{depItem}:{prettyDepBranch}])")
                resolvErrors = self._resolve_dependencies_for_module_description(moduleGraph, depModuleDesc)

                errors["branchErrors"] += resolvErrors["branchErrors"]
                errors["syntaxErrors"] += resolvErrors["syntaxErrors"]
                errors["trivialCycles"] += resolvErrors["trivialCycles"]
        return errors

    def resolve_to_module_graph(self, modules: list[Module]) -> dict:
        graph = {}
        moduleGraph = graph

        result = {
            "graph": moduleGraph,
            "errors": {
                "branchErrors": 0,
                "pathErrors": 0,
                "trivialCycles": 0,
                "syntaxErrors": 0,
                "cycles": 0
            }
        }
        errors = result["errors"]

        for module in modules:
            item = module.name  # _shorten_module_name(path)
            branch = self._get_branch_of(module)
            path = DependencyResolver._get_dependency_path_of(module, item, "")

            if not path:
                logger_depres.error(f"r[Unable to determine project/dependency path of module: {item}]")
                errors["pathErrors"] += 1
                continue

            if item in moduleGraph and moduleGraph[item]:
                logger_depres.debug(f"Module pulled in previously through (transitive) dependencies: {item}")
                previouslySelectedBranch = self._detect_branch_conflict(moduleGraph, item, branch)
                if previouslySelectedBranch:
                    logger_depres.error(f"r[Found a dependency conflict in branches ('b[{previouslySelectedBranch}]' is not 'b[{branch}]') for b[{item}]! :(")
                    errors["branchErrors"] += 1
                elif branch:
                    moduleGraph[item][branch] = branch

                # May have been pulled in via dependencies but not yet marked for
                # build. Do so now, since it is listed explicitly in @modules
                moduleGraph[item]["build"] = True
            else:
                depLookupResult = self._lookup_direct_dependencies(path, branch)

                errors["trivialCycles"] += depLookupResult["trivialCycles"]
                errors["syntaxErrors"] += depLookupResult["syntaxErrors"]

                moduleGraph[item] = {
                    "votes": {},
                    "path": path,
                    "build": True,
                    "branch": branch,
                    "module": module,
                    "deps": depLookupResult["dependencies"],
                    "allDeps": {},
                    "traces": {}
                }

                moduleDesc = {
                    "includeDependencies": module.get_option("include-dependencies"),
                    "path": path,
                    "item": item,
                    "branch": branch,
                    "module": module
                }

                resolvErrors = self._resolve_dependencies_for_module_description(moduleGraph, moduleDesc)

                errors["branchErrors"] += resolvErrors["branchErrors"]
                errors["syntaxErrors"] += resolvErrors["syntaxErrors"]
                errors["trivialCycles"] += resolvErrors["trivialCycles"]

        pathErrors = errors["pathErrors"]
        if pathErrors:
            logger_depres.error(f"Total of items which were not resolved due to path lookup failure: {pathErrors}")

        branchErrors = errors["branchErrors"]
        if branchErrors:
            logger_depres.error(f"Total of branch conflicts detected: {branchErrors}")

        syntaxErrors = errors["syntaxErrors"]
        if syntaxErrors:
            logger_depres.error(f"Total of encountered syntax errors: {syntaxErrors}")

        if syntaxErrors or pathErrors or branchErrors:
            logger_depres.error("Unable to resolve dependency graph")

            result["graph"] = None
            return result

        trivialCycles = errors["trivialCycles"]

        if trivialCycles:
            logger_depres.debug(f"Total of 'trivial' dependency cycles detected & eliminated: {trivialCycles}")

        cycles = self._check_dependency_cycles(moduleGraph)

        if cycles:
            logger_depres.error(f"Total of items with at least one circular dependency detected: {errors}")
            logger_depres.error("Unable to resolve dependency graph")

            result["cycles"] = cycles
            result["graph"] = None
            return result
        else:
            result["graph"] = self._run_dependency_vote(DependencyResolver._copy_up_dependencies(moduleGraph))
            return result

    @staticmethod
    def _descend_module_graph(moduleGraph, callback, nodeInfo, context) -> None:
        depth = nodeInfo["depth"]
        index = nodeInfo["idx"]
        count = nodeInfo["count"]
        currentItem = nodeInfo["currentItem"]
        currentBranch = nodeInfo["currentBranch"]
        parentItem = nodeInfo["parentItem"]
        parentBranch = nodeInfo["parentBranch"]

        subGraph = moduleGraph[currentItem]
        callback(nodeInfo, subGraph["module"], context)

        depth += 1

        items = list(subGraph["deps"].keys())

        itemCount = len(items)
        itemIndex = 1

        for item in items:
            subGraph = moduleGraph[item]
            branch = subGraph.get("branch", "")
            itemInfo = {
                "build": subGraph["build"],
                "depth": depth,
                "idx": itemIndex,
                "count": itemCount,
                "currentItem": item,
                "currentBranch": branch,
                "parentItem": currentItem,
                "parentBranch": currentBranch
            }
            DependencyResolver._descend_module_graph(moduleGraph, callback, itemInfo, context)
            itemIndex += 1

    @staticmethod
    def walk_module_dependency_trees(moduleGraph, callback, context, modules) -> None:

        itemCount = len(modules)
        itemIndex = 1

        for module in modules:
            Util.assert_isa(module, Module)
            item = module.name
            subGraph = moduleGraph[item]
            branch = subGraph.get("branch", "")
            info = {
                "build": subGraph["build"],
                "depth": 0,
                "idx": itemIndex,
                "count": itemCount,
                "currentItem": item,
                "currentBranch": branch,
                "parentItem": "",
                "parentBranch": ""
            }
            DependencyResolver._descend_module_graph(moduleGraph, callback, info, context)
            itemIndex += 1

    @staticmethod
    def make_comparison_func(moduleGraph) -> FunctionType:

        def _compare_build_order_depends(a, b):
            # comparison results uses:
            # -1 if a < b
            # 0 if a == b
            # 1 if a > b

            aVotes = moduleGraph[a]["votes"]
            bVotes = moduleGraph[b]["votes"]

            # Enforce a strict dependency ordering.
            # The case where both are true should never happen, since that would
            # amount to a cycle, and cycle detection is supposed to have been
            # performed beforehand.

            bDependsOnA = aVotes.get(b, 0)
            aDependsOnB = bVotes.get(a, 0)
            order = -1 if bDependsOnA else (1 if aDependsOnB else 0)

            if order:
                return order

            # Assuming no dependency relation, next sort by 'popularity':
            # the item with the most votes (back edges) is depended on the most
            # so it is probably a good idea to build that one earlier to help
            # maximise the duration of time for which builds can be run in parallel

            votes = len(bVotes.keys()) - len(aVotes.keys())

            if votes:
                return votes

            # If there is no good reason to perfer one module over another,
            # simply sort by the order contained within the configuration file (if
            # present), which would be setup as the rc-file is read.

            aRcOrder = moduleGraph[a]["module"].create_id or 0
            bRcOrder = moduleGraph[b]["module"].create_id or 0
            configOrder = (aRcOrder > bRcOrder) - (aRcOrder < bRcOrder)

            if configOrder:
                return configOrder

            # If the rc-file is not present then sort by name to ensure a reproducible
            # build order that isn't influenced by randomization of the runtime.
            return (a > b) - (a < b)

        return _compare_build_order_depends

    @staticmethod
    def sort_modules_into_build_order(moduleGraph) -> list[Module]:
        resolved = list(moduleGraph.keys())
        built = [el for el in resolved if moduleGraph[el]["build"] and moduleGraph[el]["module"]]
        prioritised = sorted(built, key=cmp_to_key(DependencyResolver.make_comparison_func(moduleGraph)))
        modules = [moduleGraph[key]["module"] for key in prioritised]
        return modules

    @staticmethod
    def _get_branch_of(module) -> str | None:
        """
        This function extracts the branch of the given Module by calling its
        scm object's branch-determining method. It also ensures that the branch
        returned was really intended to be a branch (as opposed to a detached HEAD);
        None is returned when the desired commit is not a branch name, otherwise
        the user-requested branch name is returned.
        """

        scm = module.scm()

        # when the module's SCM is not git,
        # assume the default "no particular" branch wildcard

        if not isinstance(scm, Updater):
            return None

        branch, sourcetype = scm._determine_preferred_checkout_source(module)
        return branch if sourcetype == "branch" else None
