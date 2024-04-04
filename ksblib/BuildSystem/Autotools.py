import os
# from overrides import override
from promise import Promise

from .BuildSystem import BuildSystem
from ..Util.Util import Util
from ..Debug import Debug


class BuildSystem_Autotools(BuildSystem):
    """
    This is a module used to support configuring with autotools.
    """
    
    @staticmethod
    # @override
    def name() -> str:
        return "autotools"
    
    def _findConfigureCommands(self) -> Promise:
        """
        Returns a promise that resolves to the specific configure command to use.
        
        This may execute commands to re-run autoconf to generate the script.
        
        If these commands fail the promise will reject.
        """
        module = self.module
        sourcedir = module.fullpath("source")
        
        configureCommand = next((item for item in ["configure", "autogen.sh"] if os.path.exists(f"{sourcedir}/{item}")), None)
        configureInFile = next((item for item in ["configure.in", "configure.ac"] if os.path.exists(f"{sourcedir}/{item}")), None)
        
        if configureCommand != "autogen.sh" and configureInFile:
            return Promise.resolve(configureCommand)
        
        # If we have a configure.in or configure.ac but configureCommand is autogen.sh
        # we assume that configure is created by autogen.sh as usual in some GNU Projects.
        # So we run autogen.sh first to create the configure command and
        # recheck for that.
        if configureInFile and configureCommand == "autogen.sh":
            promise = Util.run_logged_p(module, "autogen", sourcedir, [f"{sourcedir}/{configureCommand}"])
            
            def _then1(exitcode):
                if exitcode != 0:
                    print(f"Autogen failed with exit code {exitcode}")
                    exit(1)
            
            promise = promise.then(_then1)
            
            def _then2(_):
                # Cleanup any stray Makefiles that may be present, if generated
                if os.path.exists(f"{sourcedir}/Makefile"):
                    return Util.run_logged_p(module, "distclean", sourcedir, ["make", "distclean"])
                
                # nothing to do, return successful exit code
                return 0
            
            promise = promise.then(_then2)
            
            def _then3(exitcode):
                if exitcode != 0:
                    print(f"Failed to run make distclean, exit code {exitcode}")
                    exit(1)
            
            promise = promise.then(_then3)
            
            def _then4(_):
                # Now recheck
                configureCommand = next((item for item in ["configure", "autogen.sh"] if os.path.exists(f"{sourcedir}/{item}")), None)
                return configureCommand
            
            promise = promise.then(_then4)
            
            return promise
        
        if not configureCommand:
            return Promise.reject('No configure command available')
        
        return Promise.resolve(configureCommand)
    
    # @override
    def configureInternal(self) -> bool:
        """
        Return value style: boolean
        """
        module = self.module
        sourcedir = module.fullpath("source")
        builddir = module.fullpath("build")
        installdir = module.installationPath()
        
        # 'module'-limited option grabbing can return undef, so use //
        # to convert to empty string in that case.
        bootstrapOptions = Util.split_quoted_on_whitespace(module.getOption("configure-flags", "module") or "")
        
        result = None
        promise = self._findConfigureCommands()
        
        def _then1(configureCommand):
            Util.p_chdir(module.fullpath("build"))
            
            return Util.run_logged_p(module, "configure", builddir, [f"{sourcedir}/{configureCommand}", f"--prefix={installdir}", *bootstrapOptions])
        
        promise = promise.then(_then1)
        
        def _then2(exitcode):
            nonlocal result
            result = exitcode
        
        promise = promise.then(_then2)
        
        def _catch(err):
            Debug().error(f"\tError configuring {module}: r[b[{err}]")
            return 0
        
        promise = promise.catch(_catch)
        Promise.wait(promise)
        
        return result == 0
