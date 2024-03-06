# from overrides import override
from ..Util.Conditional_Type_Enforced import conditional_type_enforced

from .BuildSystem import BuildSystem
from ..Util.Util import Util


@conditional_type_enforced
class BuildSystem_CMakeBootstrap(BuildSystem):
    """
    This is a module used to do only one thing: Bootstrap CMake onto a system
    that doesn't have it, or has only an older version of it.
    """
    
    @staticmethod
    # @override
    def name() -> str:
        return "cmake-bootstrap"
    
    @staticmethod
    # @override
    def requiredPrograms() -> list:
        return ["c++", "make"]
    
    # @override
    def configureInternal(self) -> bool:
        """
        Return value style: boolean
        """
        module = self.module
        sourcedir = module.fullpath("source")
        installdir = module.installationPath()
        
        # 'module'-limited option grabbing can return undef, so use //
        # to convert to empty string in that case.
        bootstrapOptions = Util.split_quoted_on_whitespace(module.getOption("configure-flags", "module") or "")
        
        builddir = module.fullpath("build")
        
        promise = Util.run_logged_p(module, "cmake-bootstrap", builddir, [f"{sourcedir}/bootstrap", f"--prefix={installdir}", *bootstrapOptions])
        
        return Util.await_exitcode(promise)
