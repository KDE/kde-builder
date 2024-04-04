import re
import json
# from overrides import override

from ..BuildException import BuildException
from ..Debug import Debug
from ..IPC.Null import IPC_Null
from ..Util.Util import Util
from .KDEProject import Updater_KDEProject


class Updater_KDEProjectMetadata(Updater_KDEProject):
    """
    Updater used only to specifically update the "repo-metadata" module
    used for storing dependency information, among other things.
    
    Note: 2020-06-20 the previous "kde-build-metadata" module was combined into
    the "repo-metadata" module, under the '/dependencies' folder.
    """
    
    @staticmethod
    # @override(check_signature=False)
    def name() -> str:
        return "metadata"
    
    def ignoredModules(self) -> list:
        """
        Returns a list of the full kde-project paths for each module to ignore.
        """
        Util.assert_isa(self, Updater_KDEProjectMetadata)
        path = self.module.fullpath("source") + "/dependencies/build-script-ignore"
        
        # Now that we in theory have up-to-date source code, read in the
        # ignore file and propagate that information to our context object.
        
        fh = Util.pretend_open(path) or BuildException.croak_internal(f"Unable to read ignore data from {path}")
        
        ctx = self.module.buildContext()
        ignoreModules = []
        for line in fh:
            # 1 Remove comments
            line = re.sub(f"#.*$", "", line)
            
            # 2 Filter empty lines
            if not line.strip():
                continue
            
            # 3 Remove newlines
            line = line.rstrip("\n")
            
            ignoreModules.append(line)
        fh.close()
        return ignoreModules
    
    def logicalModuleGroups(self) -> dict:
        """
        If JSON support is present, and the metadata has already been downloaded
        (e.g. with ->updateInternal), returns a hashref to the logical module group
        data contained within the kde-build-metadata, decoded from its JSON format.
        See https://community.kde.org/Infrastructure/Project_Metadata
        """
        path = self.module.fullpath("source") + "/dependencies/logical-module-structure.json"
        
        # The {} is an empty JSON obj to support pretend mode
        fh = Util.pretend_open(path, "{}") or BuildException.croak_internal("Unable to read logical module structure")
        
        try:
            json_string = fh.read()  # slurps the whole file
            json_hashref = json.loads(json_string)
            fh.close()
        except BuildException as e:
            BuildException.croak_runtime(f"Unable to load module group data from {path}! :(\n\t{e}")
        return json_hashref
    
    # @override(check_signature=False)
    def updateInternal(self, ipc=IPC_Null()) -> None:
        if Debug().isTesting():
            return self._mockTestMetadata()
        
        super().updateInternal(ipc)
    
    @staticmethod
    def _mockTestMetadata() -> None:
        """
        Nothing to do currently, mock data is handled directly by
        ksb::Application (dependencies) or ksb::KDEProjectReader (project
        metadata).
        """
        pass
