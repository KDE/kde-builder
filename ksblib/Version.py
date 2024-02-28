import subprocess
import os
from .Util.Conditional_Type_Enforced import conditional_type_enforced


@conditional_type_enforced
class Version:
    """
    This package is just a place to put the kdesrc-build version number
    in one spot, so it only needs changed in one place for a version bump.
    """
    
    # It is expected that future git tags will be in the form 'YY.MM' and will
    # be time-based instead of event-based as with previous releases.
    VERSION = "22.07"
    SCRIPT_PATH = ""  # For auto git-versioning
    SCRIPT_VERSION = VERSION
    
    @staticmethod
    def setBasePath(newPath: str) -> None:
        """
        Should be called before using ``scriptVersion`` to set the base path for the
        script.  This is needed to auto-detect the version in git for kdesrc-build
        instances running from a git repo.
        """
        Version.SCRIPT_PATH = newPath if newPath else Version.SCRIPT_PATH
    
    @staticmethod
    def scriptVersion() -> str:
        """
        Call this function to return the kdesrc-build version.
        ::
        
            version = ksblib.Version.scriptVersion()  # "22.07"
        
        If the script is running from within its git repository (and ``setBasePath`` has
        been called), this function will try to auto-detect the git SHA1 ID of the
        current checkout and append the ID (in ``git-describe`` format) to the output
        string as well.
        """
        can_run_git = subprocess.call("type " + "git", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
        if Version.SCRIPT_PATH and can_run_git and os.path.isdir(f"{Version.SCRIPT_PATH}/.git"):
            result = subprocess.run(["git", f"--git-dir={Version.SCRIPT_PATH}/.git", "describe"], shell=False, capture_output=True, check=False)
            output = result.stdout.decode("utf-8").removesuffix("\n")
            ok = result.returncode == 0
            if ok and output:
                return f"{Version.SCRIPT_VERSION} ({output})"
        return Version.SCRIPT_VERSION
