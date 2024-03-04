from ..Util.Conditional_Type_Enforced import conditional_type_enforced
from overrides import override

from ..BuildContext import BuildContext
# use ksb::BuildException;
from ..BuildSystem.Qt5 import BuildSystem_Qt5
# use ksb::Debug;
from ..Module.Module import Module
from ..Util.Util import Util
from .ModuleSet import ModuleSet


@conditional_type_enforced
class ModuleSet_Qt(ModuleSet):
    """
    Class: ModuleSet::Qt
    
    This represents a collection of Qt5 source code modules that are collectively
    kept up to date by Qt's init-repository script. This module set is
    essentially used to make sure that generated ksb::Modules use proper scm()
    and buildSystems()
    
    Use of this module-set is controlled by the 'repository' option being set to
    the magic value 'qt-projects', just as 'kde-projects' is used for KDE.
    """
    
    def _makeQt5Module(self, ctx) -> Module:
        Util.assert_isa(self, __class__)
        Util.assert_isa(ctx, BuildContext)
        
        newModule = Module(ctx, "Qt5")
        
        self._initializeNewModule(newModule)
        
        # Repo URL to the Qt5 "supermodule" that contains the documented
        # init-repository script.
        # See https://wiki.qt.io/Building_Qt_5_from_Git
        newModule.setOption({"repository": "https://invent.kde.org/qt/qt/qt5.git"})
        newModule.setScmType("qt5")
        newModule.setBuildSystem(BuildSystem_Qt5(newModule))
        
        # Convert the use-modules/ignore-modules entries into a form appropriate
        # for init-repository's module-subset option.
        modEntries = list(self.modulesToFind()) + ["-" + i for i in self.modulesToIgnore()]
        newModule.setOption({"use-qt5-modules": " ".join(modEntries)})
        
        return newModule
    
    @override
    def convertToModules(self, ctx) -> list[Module]:
        """
        This function should be called after options are read and build metadata is
        available in order to convert this module set to a list of ksb::Module.
        
        In our case, we will return ONLY ONE MODULE. That module will handle "sub
        modules" via the init-repository script so from kde-builder's perspective it
        is handled as a single unit.
        """
        return [self._makeQt5Module(ctx)]
