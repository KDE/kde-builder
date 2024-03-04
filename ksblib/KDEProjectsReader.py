import os.path
import re
from .Util.Conditional_Type_Enforced import conditional_type_enforced
from pathlib import Path
import yaml

from .BuildException import BuildException
from .Debug import Debug


@conditional_type_enforced
class KDEProjectsReader:
    """
    Enumerates and provides basic metadata of KDE projects, based on
    the YAML metadata included in sysadmin/repo-management.
    """
    
    def __init__(self, projectMetadataModule):
        """
        Constructs a new KDEProjectsReader. This doesn't contradict any part of the class
        documentation which claims this class is a singleton however. This should be
        called as a method (e.g. KDEProjectsReader->new(...)).
        
        Parameters:
         $projectMetadataModule - ksb::Module reference to the repo-metadata module.
        """
        
        # pl2py: no need to check _verifyYAMLModuleLoaded()
        
        self.repositories = {}  # Maps short names to repo info blocks
        
        self._readProjectData(projectMetadataModule)
    
    def _readProjectData(self, projectMetadataModule) -> None:
        # The 'main' method for this class. Reads in *all* KDE projects and notes
        # their details for later queries.
        # Be careful, can throw exceptions.
        
        if Debug().isTesting():
            self._loadMockProjectData()
            return
        
        srcdir = projectMetadataModule.fullpath("source")
        
        if not os.path.isdir(srcdir):
            BuildException.croak_runtime(f"No such source directory {srcdir}!")
        
        # NOTE: This is approx 1280 entries as of Feb 2023.  Need to memoize this
        # so that only entries that are used end up being read.
        # The obvious thing of using path info to guess module name doesn't work
        # (e.g. maui-booth has a disk path of maui/booth in repo-metadata, not maui/maui-booth)
        repoMetaFiles = list(Path(f"{srcdir}/projects").resolve().rglob("metadata.yaml"))  # resolve /projects symlink first, then recurse through dir tree
        
        for metadataPath in repoMetaFiles:
            self._readYAML(metadataPath)
        
        if not len(repoMetaFiles) > 0:
            BuildException.croak_runtime(f"Failed to find KDE project entries from {srcdir}!")
    
    def _loadMockProjectData(self) -> None:
        # Load some sample projects for use in test mode
        # Should stay in sync with the data generated by _readYAML
        projects = ["kde-builder", "juk", "kcalc", "konsole", "dolphin"]
        
        for project in projects:
            repoData = {
                "fullName": f"test/{project}",
                "repo": f"kde:{project}.git",
                "name": project,
                "active": True,
                "found_by": "direct",
            }
            
            self.repositories[project] = repoData
    
    def _readYAML(self, filename) -> None:
        with open(filename, "r") as file:
            proj_data = yaml.safe_load(file)
        
        # This is already 'covered' as a special metadata module, ignore
        if proj_data["projectpath"] == "repo-management":
            return
        
        repoPath = proj_data["repopath"]
        repoName = proj_data["identifier"] if proj_data["identifier"] else repoPath
        
        # Keep in sync with _loadMockProjectData
        curRepository = {
            "fullName": proj_data["projectpath"],
            "inventName": repoPath,
            "repo": f"kde:{repoPath}.git",
            "name": repoName,
            "active": bool(proj_data["repoactive"]),
            "found_by": "direct"  # can be changed in getModulesForProject
        }
        
        # Find everything after last /
        inventSuffix = re.search(r"([^/]+$)", proj_data["repopath"]).group(1)
        legacySuffix = re.search(r"([^/]+$)", proj_data["projectpath"]).group(1)
        
        # We can print a message later for modules where the name will change if
        # the module is actually used
        if inventSuffix != legacySuffix:
            curRepository["nameChangingTo"] = inventSuffix
        
        self.repositories[repoName] = curRepository
    
    def getModulesForProject(self, proj: str) -> list:
        """
        Note on $proj: A /-separated path is fine, in which case we look
        for the right-most part of the full path which matches all of searchProject.
        e.g. kde/kdebase/kde-runtime would be matched by a proj of either
        "kdebase/kde-runtime" or simply "kde-runtime".
        """
        repositoryRef = self.repositories
        results = []
        
        def findResults():
            matchList = [key for key in sorted(repositoryRef.keys()) if KDEProjectsReader._projectPathMatchesWildcardSearch(repositoryRef[key]["fullName"], proj)]
            
            if re.search(r"\*", proj):
                for key in matchList:
                    repositoryRef[key]["found_by"] = "wildcard"
            
            results.extend(matchList)
        
        # Wildcard matches happen as specified if asked for.
        # Non-wildcard matches have an implicit "$proj/*" search as well for
        # compatibility with previous use-modules
        # Project specifiers ending in .git are forced to be non-wildcarded.
        if not re.search(r"\*", proj) and not re.search(r"\.git$", proj):
            # We have to do a search to account for over-specified module names
            # like phonon/phonon
            findResults()
            
            # Now setup for a wildcard search to find things like kde/kdelibs/baloo
            # if just 'kdelibs' is asked for.
            proj += "/*"
        
        proj = re.sub(r"\.git$", "", proj)
        
        # If still no wildcard and no '/' then we can use direct lookup by module
        # name.
        if not re.search(r"\*", proj) and not re.search(r"/", proj) and proj in repositoryRef:
            results.append(proj)
        else:
            findResults()
        
        # As we run findResults twice (for example, when proj is "workspace"), remove duplicates
        results = list(set(results))
        
        return [repositoryRef[result] for result in results]
    
    @staticmethod
    def _projectPathMatchesWildcardSearch(projectPath, searchItem) -> bool:
        """
        Utility subroutine, returns true if the given kde-project full path (e.g.
        kde/kdelibs/nepomuk-core) matches the given search item.
        
        The search item itself is based on path-components. Each path component in
        the search item must be present in the equivalent path component in the
        module's project path for a match. A '*' in a path component position for the
        search item matches any project path component.
        
        Finally, the search is pinned to search for a common suffix. E.g. a search
        item of 'kdelibs' would match a project path of 'kde/kdelibs' but not
        'kde/kdelibs/nepomuk-core'. However, 'kdelibs/*' would match
        'kde/kdelibs/nepomuk-core'.
        
        First parameter is the full project path from the kde-projects database.
        Second parameter is the search item.
        Returns true if they match, false otherwise.
        """
        
        searchParts = searchItem.split("/")
        nameStack = projectPath.split("/")
        
        if len(nameStack) >= len(searchParts):
            sizeDifference = len(nameStack) - len(searchParts)
            
            # We might have to loop if we somehow find the wrong start point for our search.
            # E.g. looking for a/b/* against a/a/b/c, we'd need to start with the second a.
            i = 0
            while i <= sizeDifference:
                # Find our common prefix, then ensure the remainder matches item-for-item.
                while i <= sizeDifference:
                    if nameStack[i] == searchParts[0]:
                        break
                    i += 1
                
                if i > sizeDifference:  # Not enough room to find it now
                    return False
                
                # At this point we have synched up nameStack to searchParts, ensure they
                # match item-for-item.
                found = 1
                j = 0
                while found and j < len(searchParts):
                    if searchParts[j] == "*":  # This always works
                        return True
                    if searchParts[j] != nameStack[i + j]:
                        found = 0
                    j += 1
                
                if found:  # We matched every item to the substring we found.
                    return True
                i += 1  # Try again
        return False
