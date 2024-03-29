from ..Util.Conditional_Type_Enforced import conditional_type_enforced
# from overrides import override

from .KDECMake import BuildSystem_KDECMake


@conditional_type_enforced
class BuildSystem_Qt6(BuildSystem_KDECMake):
    """
    Class responsible for building Qt6 CMake-based modules.
    """
    
    @staticmethod
    # @override
    def name() -> str:
        return "Qt6"
    
    # @override
    def prepareModuleBuildEnvironment(self, ctx, module, prefix) -> None:
        # We're installing Qt6 modules, make sure our Qt directory matches our
        # install prefix so that environment variables are properly set.
        module.setOption({"qt-install-dir": prefix})
        return super().prepareModuleBuildEnvironment(ctx, module, prefix)
