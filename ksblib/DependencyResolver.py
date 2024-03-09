from __future__ import annotations

import re
import json
from .Util.Conditional_Type_Enforced import conditional_type_enforced
from functools import cmp_to_key
from types import FunctionType

from .BuildException import BuildException
from .Util.Util import Util
from .Updater.Git import Updater_Git
from .Module.Module import Module
from .Debug import Debug


@conditional_type_enforced
class DependencyResolver:
    """
    Class: DependencyResolver
    
    This module handles resolving dependencies between modules. Each "module"
    from the perspective of this resolver is simply a module full name, as
    given by the KDE Project database.  (e.g. extragear/utils/kdesrc-build)
    """
    
    # sub uniq
    # {
    #     my %seen;
    #     return grep { ++($seen{$_}) == 1 } @_;
    # }
    
    def __init__(self, moduleFactoryRef):
        """
        Constructor: new
        
        Constructs a new <DependencyResolver>.
        
        Parameters:
        
          moduleFactoryRef - Reference to a sub that creates ksb::Modules from
            kde-project module names. Used for ksb::Modules for which the user
            requested recursive dependency inclusion.
        
        Synposis:
        
        > my $resolver = new DependencyResolver($modNewRef);
        > $resolver->readDependencyData(open my $fh, '<', 'file.txt');
        > $resolver->resolveDependencies(@modules);
        """
        
        # hash table mapping short module names (m) to a hashref key by branch
        # name, the value of which is yet another hashref (see
        # readDependencyData). Note that this assumes KDE git infrastructure
        # ensures that all full module names (e.g.
        # kde/workspace/plasma-workspace) map to a *unique* short name (e.g.
        # plasma-workspace) by stripping leading path components
        self.dependenciesOf = {}
        
        # hash table mapping a wildcarded module name with no branch to a
        # listref of module:branch dependencies.
        self.catchAllDependencies = {}
        
        # reference to a sub that will properly create a ksb::Module from a
        # given kde-project module name. Used to support automatically adding
        # dependencies to a build.
        self.moduleFactoryRef = moduleFactoryRef
    
    @staticmethod
    def _shortenModuleName(name) -> str:
        """
        Internal:
        
        This method returns the 'short' module name of kde-project full project paths.
        E.g. 'kde/kdelibs/foo' would be shortened to 'foo'.
        
        This is a static function, not an object method.
        
        Parameters:
        
         path - A string holding the full module virtual path
        
        Returns:
        
         The module name.
        """
        name = re.sub(r"^.*/", "", name)  # Uses greedy capture by default
        return name
    
    def _addDependency(self, depName, depBranch, srcName, srcBranch, depKey="+") -> None:
        """
        Adds an edge in the dependency graph from C<$depName> (at the given branch) to
        C<$srcName> (at its respective branch). Use C<*> as the branch name if it is
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
    
    def readDependencyData(self, fh) -> None:
        """
        Method: readDependencyData
        
        Reads in dependency data in a pseudo-Makefile format.
        See repo-metadata/dependencies/dependency-data.
        
        Parameters:
         $self - The DependencyResolver object.
         $fh   - Filehandle to read dependencies from (should already be open).
        
        Exceptions:
         Can throw an exception on I/O errors or malformed dependencies.
        """
        Util.assert_isa(self, DependencyResolver)
        
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
                Debug().warning("\tIgnoring dependency on wildcard module grouping " + f"on line {fh.filelineno()} of repo-metadata/dependencies/dependency-data")
                continue
            
            dependentBranch = dependentBranch or "*"  # If no branch, apply catch-all flag
            sourceBranch = sourceBranch or "*"
            
            # _shortenModuleName may remove negation marker so check now
            depKey = "-" if sourceItem.startswith("-") else "+"
            sourceItem = re.sub("^-", "", sourceItem)  # remove negation marker if name already short
            
            # Source can never be a catch-all, so we can shorten early. Also,
            # we *must* shorten early to avoid a dependency on a long path.
            sourceItem = self._shortenModuleName(sourceItem)
            
            # Handle catch-all dependent groupings
            if re.match(r"\*$", dependentItem):
                self.catchAllDependencies[dependentItem] = self.catchAllDependencies.get(dependentItem, [])
                self.catchAllDependencies[dependentItem].append(f"{sourceItem}:{sourceBranch}")
                continue
            
            dependentItem = self._shortenModuleName(dependentItem)
            
            self._addDependency(dependentItem, dependentBranch, sourceItem, sourceBranch, depKey)
        
        self._canonicalizeDependencies()
    
    def readDependencyData_v2(self, fh) -> None:
        """
        Reads in v2-format dependency data from KDE repository database, using the KDE
        'invent' repository naming convention.
        
        Throws exception on read failure.
        
         open my $fh, '<', "/path/to/dependency-data.json" or die;
         $resolver->readDependencyData_v2($fh);
        """
        Debug().note("b[***] USING y[b[V2 DEPENDENCY METADATA], BUILD IS UNSUPPORTED")
        
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
            depName = self._shortenModuleName(depModule)
            for srcModule in srcList:
                srcName = self._shortenModuleName(srcModule)
                self._addDependency(depName, "*", srcName, "*")
        
        self._canonicalizeDependencies()
    
    def _canonicalizeDependencies(self) -> None:
        """
        Function: _canonicalizeDependencies
        
        Ensures that all stored dependencies are stored in a way that allows for
        reproducable dependency ordering (assuming the same dependency items and same
        selectors are used).
        
        Parameters: none
        
        Returns: none
        """
        dependenciesOfRef = self.dependenciesOf
        
        for dependenciesRef in dependenciesOfRef.values():
            dependenciesRef["-"] = sorted(dependenciesRef["-"])
            dependenciesRef["+"] = sorted(dependenciesRef["+"])
    
    def _lookupDirectDependencies(self, path, branch) -> dict:
        Util.assert_isa(self, DependencyResolver)
        
        dependenciesOfRef = self.dependenciesOf
        
        directDeps = []
        exclusions = []
        
        item = self._shortenModuleName(path)
        moduleDepEntryRef = dependenciesOfRef.get(f"{item}:*", None)
        
        if moduleDepEntryRef:
            Debug().debug(f"handling dependencies for: {item} without branch (*)")
            directDeps.extend(moduleDepEntryRef["+"])
            exclusions.extend(moduleDepEntryRef["-"])
        
        if branch and branch != "*":
            moduleDepEntryRef = dependenciesOfRef.get(f"{item}:{branch}", None)
            if moduleDepEntryRef:
                Debug().debug(f"handling dependencies for: {item} with branch ({branch})")
                directDeps.extend(moduleDepEntryRef["+"])
                exclusions.extend(moduleDepEntryRef["-"])
        
        # Apply catch-all dependencies but only for KDE modules, not third-party
        # modules. See _getDependencyPathOf for how this is detected.
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
                Debug().error(f"r[Invalid dependency declaration: b[{dep}]]")
                result["syntaxErrors"] += 1
                continue
            depItem = self._shortenModuleName(depPath)
            if depItem == item:
                Debug().debug(f"\tBreaking trivial cycle of b[{depItem}] -> b[{item}]")
                result["trivialCycles"] += 1
                continue
            
            if depItem in result["dependencies"]:
                Debug().debug(f"\tSkipping duplicate direct dependency b[{depItem}] of b[{item}]")
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
    def _runDependencyVote(moduleGraph) -> dict:
        for item in moduleGraph.keys():
            names = list(moduleGraph[item]["allDeps"]["items"].keys())
            for name in names:
                moduleGraph[name]["votes"][item] = moduleGraph[name]["votes"].get(item, 0) + 1
        return moduleGraph
    
    @staticmethod
    def _detectDependencyCycle(moduleGraph, depItem, item):
        depModuleGraph = moduleGraph[depItem]
        if depModuleGraph.setdefault("traces", {}).get("status", None):
            if depModuleGraph["traces"]["status"] == 2:
                Debug().debug(f"Already resolved {depItem} -- skipping")
                return depModuleGraph["traces"]["result"]
            else:
                if not Debug().isTesting():
                    Debug().error(f"Found a dependency cycle at: {depItem} while tracing {item}")
                depModuleGraph["traces"]["result"] = 1
        else:
            depModuleGraph["traces"]["status"] = 1
            depModuleGraph["traces"]["result"] = 0
            
            names = list(depModuleGraph["deps"].keys())
            for name in names:
                if DependencyResolver._detectDependencyCycle(moduleGraph, name, item):
                    depModuleGraph["traces"]["result"] = 1
        depModuleGraph["traces"]["status"] = 2
        return depModuleGraph["traces"]["result"]
    
    def _checkDependencyCycles(self, moduleGraph) -> int:
        errors = 0
        
        # sorted() is used for moduleGraph.keys() because in perl the hash keys are returned in random way.
        # So for reproducibility while debugging, the sort was added there.
        # In python 3.7 the keys are returned in the order of adding them.
        # To be able to easily compare perl and python versions, I (Andrew Shark) sorted keys as it is done there.
        # After we drop perl version, we can remove the unneeded sorting.
        
        for item in sorted(moduleGraph.keys()):
            if DependencyResolver._detectDependencyCycle(moduleGraph, item, item):
                Debug().error(f"Somehow there is a circular dependency involving b[{item}]! :(")
                Debug().error("Please file a bug against repo-metadata about this!")
                errors += 1
        return errors
    
    @staticmethod
    def _copyUpDependenciesForModule(moduleGraph, item) -> None:
        allDeps = moduleGraph[item]["allDeps"]
        
        if "done" in allDeps:
            Debug().debug(f"\tAlready copied up dependencies for b[{item}] -- skipping")
        else:
            Debug().debug(f"\tCopying up dependencies and transitive dependencies for item: b[{item}]")
            allDeps["items"] = {}
            
            names = moduleGraph[item]["deps"].keys()
            for name in names:
                if name in allDeps["items"]:
                    Debug().debug(f"\tAlready copied up (transitive) dependency on b[{name}] for b[{item}] -- skipping")
                else:
                    DependencyResolver._copyUpDependenciesForModule(moduleGraph, name)
                    copied = list(moduleGraph[name]["allDeps"]["items"])
                    for copy in copied:
                        if copy in allDeps["items"]:
                            Debug().debug(f"\tAlready copied up (transitive) dependency on b[{copy}] for b[{item}] -- skipping")
                        else:
                            allDeps["items"][copy] = allDeps["items"].get(copy, 0) + 1
                    allDeps["items"][name] = allDeps["items"].get(name, 0) + 1
            allDeps["done"] = allDeps.get("done", 0) + 1
    
    @staticmethod
    def _copyUpDependencies(moduleGraph: dict) -> dict:
        for item in moduleGraph.keys():
            DependencyResolver._copyUpDependenciesForModule(moduleGraph, item)
        return moduleGraph
    
    @staticmethod
    def _detectBranchConflict(moduleGraph, item, branch) -> str | None:
        if branch:
            subGraph = moduleGraph[item]
            previouslySelectedBranch = subGraph.get(branch, None)
            
            if previouslySelectedBranch and previouslySelectedBranch != branch:
                return previouslySelectedBranch
        
        return None
    
    @staticmethod
    def _getDependencyPathOf(module, item, path) -> str:
        if module:
            projectPath = module.fullProjectPath()
            
            if not module.isKDEProject():
                projectPath = f"third-party/{projectPath}"
            
            Debug().debug(f"\tUsing path: 'b[{projectPath}]' for item: b[{item}]")
            return projectPath
        
        Debug().debug(f"\tGuessing path: 'b[{path}]' for item: b[{item}]")
        return path
    
    def _resolveDependenciesForModuleDescription(self, moduleGraph, moduleDesc) -> dict:
        
        Util.assert_isa(self, DependencyResolver)
        module = moduleDesc["module"]
        if module:
            Util.assert_isa(module, Module)
        
        path = moduleDesc["path"]
        item = moduleDesc["item"]
        branch = moduleDesc["branch"]
        prettyBranch = f"{branch}" if branch else "*"
        includeDependencies = module.getOption("include-dependencies") if module else moduleDesc["includeDependencies"]
        
        errors = {
            "syntaxErrors": 0,
            "trivialCycles": 0,
            "branchErrors": 0
        }
        
        Debug().debug(f"Resolving dependencies for module: b[{item}]")
        
        for depItem in sorted(moduleGraph[item]["deps"].keys()):
            depInfo = moduleGraph[item]["deps"][depItem]
            depPath = depInfo["path"]
            depBranch = depInfo["branch"]
            
            prettyDepBranch = f"{depBranch}" if depBranch else "*"
            
            Debug().debug(f"\tdep-resolv: b[{item}:{prettyBranch}] depends on b[{depItem}:{prettyDepBranch}]")
            
            depModuleGraph = moduleGraph.get(depItem, None)
            
            if depModuleGraph:
                previouslySelectedBranch = self._detectBranchConflict(moduleGraph, depItem, depBranch)
                if previouslySelectedBranch:
                    Debug().error(f"r[Found a dependency conflict in branches ('b[{previouslySelectedBranch}]' is not 'b[{prettyDepBranch}]') for b[{depItem}]! :(")
                    errors["branchErrors"] += 1
                else:
                    if depBranch:
                        depModuleGraph["branch"] = depBranch
            
            else:
                depModule = self.moduleFactoryRef(depItem)
                resolvedPath = DependencyResolver._getDependencyPathOf(depModule, depItem, depPath)
                # May not exist, e.g. misspellings or 'virtual' dependencies like kf5umbrella.
                if not depModule:
                    Debug().debug(f"\tdep-resolve: Will not build virtual or undefined module: b[{depItem}]\n")
                
                depLookupResult = self._lookupDirectDependencies(resolvedPath, depBranch)
                
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
                    Debug().debug(f" y[b[*] {item} depends on {depItem}, but no module builds {depItem} for this run.]")
                
                if depModule and depBranch and (self._getBranchOf(depModule) or "") != f"{depBranch}":
                    wrongBranch = self._getBranchOf(depModule) or "?"
                    Debug().error(f" r[b[*] {item} needs {depItem}:{prettyDepBranch}, not {depItem}:{wrongBranch}]")
                    errors["branchErrors"] += 1
                
                Debug().debug(f"Resolving transitive dependencies for module: b[{item}] (via: b[{depItem}:{prettyDepBranch}])")
                resolvErrors = self._resolveDependenciesForModuleDescription(moduleGraph, depModuleDesc)
                
                errors["branchErrors"] += resolvErrors["branchErrors"]
                errors["syntaxErrors"] += resolvErrors["syntaxErrors"]
                errors["trivialCycles"] += resolvErrors["trivialCycles"]
        return errors
    
    def resolveToModuleGraph(self, modules) -> dict:
        
        Util.assert_isa(self, DependencyResolver)
        
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
            item = module.name  # _shortenModuleName($path);
            branch = self._getBranchOf(module)
            path = DependencyResolver._getDependencyPathOf(module, item, "")
            
            if not path:
                Debug().error(f"r[Unable to determine project/dependency path of module: {item}]")
                errors["pathErrors"] += 1
                continue
            
            if item in moduleGraph and moduleGraph[item]:
                Debug().debug(f"Module pulled in previously through (transitive) dependencies: {item}")
                previouslySelectedBranch = self._detectBranchConflict(moduleGraph, item, branch)
                if previouslySelectedBranch:
                    Debug().error(f"r[Found a dependency conflict in branches ('b[{previouslySelectedBranch}]' is not 'b[{branch}]') for b[{item}]! :(")
                    errors["branchErrors"] += 1
                elif branch:
                    moduleGraph[item][branch] = branch
                
                # May have been pulled in via dependencies but not yet marked for
                # build. Do so now, since it is listed explicitly in @modules
                moduleGraph[item]["build"] = True
            else:
                depLookupResult = self._lookupDirectDependencies(path, branch)
                
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
                    "includeDependencies": module.getOption("include-dependencies"),
                    "path": path,
                    "item": item,
                    "branch": branch,
                    "module": module
                }
                
                resolvErrors = self._resolveDependenciesForModuleDescription(moduleGraph, moduleDesc)
                
                errors["branchErrors"] += resolvErrors["branchErrors"]
                errors["syntaxErrors"] += resolvErrors["syntaxErrors"]
                errors["trivialCycles"] += resolvErrors["trivialCycles"]
        
        pathErrors = errors["pathErrors"]
        if pathErrors:
            Debug().error(f"Total of items which were not resolved due to path lookup failure: {pathErrors}")
        
        branchErrors = errors["branchErrors"]
        if branchErrors:
            Debug().error(f"Total of branch conflicts detected: {branchErrors}")
        
        syntaxErrors = errors["syntaxErrors"]
        if syntaxErrors:
            Debug().error(f"Total of encountered syntax errors: {syntaxErrors}")
        
        if syntaxErrors or pathErrors or branchErrors:
            Debug().error("Unable to resolve dependency graph")
            
            result["graph"] = None
            return result
        
        trivialCycles = errors["trivialCycles"]
        
        if trivialCycles:
            Debug().whisper(f"Total of 'trivial' dependency cycles detected & eliminated: {trivialCycles}")
        
        cycles = self._checkDependencyCycles(moduleGraph)
        
        if cycles:
            Debug().error(f"Total of items with at least one circular dependency detected: {errors}")
            Debug().error("Unable to resolve dependency graph")
            
            result["cycles"] = cycles
            result["graph"] = None
            return result
        else:
            result["graph"] = self._runDependencyVote(DependencyResolver._copyUpDependencies(moduleGraph))
            return result
    
    @staticmethod
    def _descendModuleGraph(moduleGraph, callback, nodeInfo, context) -> None:
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
            DependencyResolver._descendModuleGraph(moduleGraph, callback, itemInfo, context)
            itemIndex += 1
    
    @staticmethod
    def walkModuleDependencyTrees(moduleGraph, callback, context, modules) -> None:
        
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
            DependencyResolver._descendModuleGraph(moduleGraph, callback, info, context)
            itemIndex += 1
    
    @staticmethod
    def make_comparison_func(moduleGraph) -> FunctionType:
        
        def _compareBuildOrder_depends(a, b):
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
        
        return _compareBuildOrder_depends
    
    @staticmethod
    def sortModulesIntoBuildOrder(moduleGraph) -> list:
        resolved = list(moduleGraph.keys())
        built = [el for el in resolved if moduleGraph[el]["build"] and moduleGraph[el]["module"]]
        prioritised = sorted(built, key=cmp_to_key(DependencyResolver.make_comparison_func(moduleGraph)))
        modules = [moduleGraph[key]["module"] for key in prioritised]
        return modules
    
    @staticmethod
    def _getBranchOf(module) -> str | None:
        """
        Function: getBranchOf
        
        Internal:
        
        This function extracts the branch of the given Module by calling its
        scm object's branch-determining method. It also ensures that the branch
        returned was really intended to be a branch (as opposed to a detached HEAD);
        undef is returned when the desired commit is not a branch name, otherwise
        the user-requested branch name is returned.
        """
        
        scm = module.scm()
        
        # when the module's SCM is not git,
        # assume the default "no particular" branch wildcard
        
        if not isinstance(scm, Updater_Git):
            return None
        
        branch, sourcetype = scm._determinePreferredCheckoutSource(module)
        return branch if sourcetype == "branch" else None
