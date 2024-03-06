import os.path
from ..Util.Conditional_Type_Enforced import conditional_type_enforced
# from overrides import override
from promise import Promise

from ..BuildException import BuildException
from ..Util.Util import Util
from .Git import Updater_Git
from ..Debug import Debug


@conditional_type_enforced
class Updater_Qt5(Updater_Git):
    """
    Handles updating Qt 5 source code. Requires git but uses Qt 5's dedicated
    'init-repository' script to keep the source up to date and coherent.
    """
    
    @staticmethod
    # @override
    def name() -> str:
        return "qt5"
    
    def _updateRepository(self) -> int:
        """
        Handles calling init-repository to clone or update the appropriate Qt 5
        submodules.
        
        Returns number of commits updated (or rather, will...)
        """
        module = self.module
        srcdir = module.fullpath("source")
        
        if not Debug().pretending() and (not os.path.exists(f"{srcdir}/init-repository") or not os.access("_", os.X_OK)):
            BuildException.croak_runtime("The Qt 5 repository update script could not be found, or is not executable!")
        
        # See https://wiki.qt.io/Building_Qt_5_from_Git#Getting_the_source_code for
        # why we skip web engine by default. As of 2019-01-12 it is only used for
        # PIM or optionally within Plasma
        modules = module.getOption("use-qt5-modules").split(" ")
        if not modules:
            modules.extend(["default", "-qtwebengine"])
        
        subset_arg = ",".join(modules)
        
        # -f forces a re-update if necessary
        command = [f"{srcdir}/init-repository", "-f", f"--module-subset={subset_arg}"]
        Debug().note("\tUsing Qt 5 modules: ", ", ".join(modules))
        
        result = Util.await_exitcode(Util.run_logged_p(module, "init-repository", srcdir, command))
        
        if not result:
            BuildException.croak_runtime("Couldn't update Qt 5 repository submodules!")
        
        return 1  # TODO: Count commits
    
    # @override
    def updateExistingClone(self) -> Promise:
        """
        Updates an existing Qt5 super module checkout.
        Throws exceptions on failure, otherwise returns number of commits updated
        """
        Util.assert_isa(self, Updater_Qt5)
        
        # Update init-repository and the shell of the super module itself.
        promise = super().updateExistingClone()
        
        # updateRepository has init-repository work to update the source
        self._updateRepository()
        
        return promise
    
    # @override(check_signature=False)
    def updateCheckout(self) -> Promise | int:
        """
        Either performs the initial checkout or updates the current git checkout
        for git-using modules, as appropriate.
        
        If errors are encountered, an exception is raised.
        
        Returns the number of *commits* affected.
        """
        Util.assert_isa(self, Updater_Qt5)
        module = self.module
        srcdir = module.fullpath("source")
        
        if os.path.isdir(f"{srcdir}/.git"):
            # Note that this function will throw an exception on failure.
            return self.updateExistingClone()
        else:
            self._verifySafeToCloneIntoSourceDir(module, srcdir)
            
            self._clone(module.getOption("repository"))
            
            Debug().note("\tQt update script is installed, downloading remainder of Qt")
            Debug().note("\tb[y[THIS WILL TAKE SOME TIME]")
            
            # With the supermodule cloned, we then need to call into
            # init-repository to have it complete the checkout.
            return self._updateRepository()  # num commits
