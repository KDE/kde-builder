from __future__ import annotations
# from overrides import override

from .KDECMake import BuildSystem_KDECMake
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..Module.Module import Module
    from ..BuildContext import BuildContext


class BuildSystem_Qt6(BuildSystem_KDECMake):
    """
    Class responsible for building Qt6 CMake-based modules.
    """
    
    @staticmethod
    # @override
    def name() -> str:
        return "Qt6"
    
    # @override
    def prepareModuleBuildEnvironment(self, ctx: BuildContext, module: Module, prefix: str) -> None:
        # We're installing Qt6 modules, make sure our Qt directory matches our
        # install prefix so that environment variables are properly set.
        module.setOption({"qt-install-dir": prefix})
        return super().prepareModuleBuildEnvironment(ctx, module, prefix)
