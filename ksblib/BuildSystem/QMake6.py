import glob
import re
from ..Util.Conditional_Type_Enforced import conditional_type_enforced
from overrides import override

from ..Util.Util import Util
from ..BuildException import BuildException
from .BuildSystem import BuildSystem
from ..Debug import Debug


@conditional_type_enforced
class BuildSystem_QMake6(BuildSystem):
    """
    A build system used to build modules that use qmake
    """
    
    @staticmethod
    @override
    def name() -> str:
        return "qmake6"
    
    @staticmethod
    @override
    def requiredPrograms() -> list:
        return ["qmake"]
    
    @override(check_signature=False)
    def needsBuilddirHack(self) -> bool:
        """
        I've never had problems with modern QMake-using modules being built in a
        specific build directory, until I tried using QMake to build Qt5 modules
        (past qtbase).  Many seem fail with builddir != srcdir
        """
        module = self.module
        
        # Assume code.qt.io modules all need hack for now
        return bool(re.search(r"qt\.io", module.getOption("repository")))
    
    @staticmethod
    def absPathToQMake() -> str:
        """
        Returns the absolute path to 'qmake'. Note the actual executable name may
        not necessarily be 'qmake' as some distributions rename it to allow for
        co-installability with Qt 5
        If no suitable qmake can be found, undef is returned.
        This is a "static class method" i.e. use ksb::BuildSystem::QMake6::absPathToQMake()
        """
        possibilities = ["qmake-qt6", "qmake6", "qmake-mac", "qmake"]
        return next((p for p in possibilities if Util.locate_exe(p)), None)
    
    @override
    def configureInternal(self) -> bool:
        """
        Return value style: boolean
        """
        Util.assert_isa(self, BuildSystem_QMake6)
        module = self.module
        builddir = module.fullpath("build")
        sourcedir = builddir if self.needsBuilddirHack() else module.fullpath("source")
        
        qmakeOpts = module.getOption('qmake-options').split(" ")
        projectFiles = glob.glob(f"{sourcedir}/*.pro")
        
        if not projectFiles and Debug().pretending():
            projectFiles = [f"{module}.pro"]
        
        if not projectFiles or not projectFiles[0]:
            BuildException.croak_internal(f"No *.pro files could be found for {module}")
        
        if len(projectFiles) > 1:
            Debug().error(f" b[r[*] Too many possible *.pro files for {module}")
            return False
        
        qmake = self.absPathToQMake()
        
        if not qmake:
            return False
        
        Debug().info("\tRunning g[qmake]...")
        return Util.await_exitcode(Util.run_logged_p(module, "qmake6", builddir, [qmake, *qmakeOpts, projectFiles[0]]))
