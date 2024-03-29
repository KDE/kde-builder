import os.path
import re
import textwrap
from ..Util.Conditional_Type_Enforced import conditional_type_enforced
# from overrides import override

from .BuildSystem import BuildSystem
from ..Util.Util import Util
from ..Debug import Debug


@conditional_type_enforced
class BuildSystem_Qt5(BuildSystem):
    """
    Build system for the Qt5 toolkit
    """
    
    @staticmethod
    # @override
    def configuredModuleFileName() -> str:
        return "Makefile"
    
    @staticmethod
    # @override
    def name() -> str:
        return "Qt5"
    
    # @override
    def configureInternal(self) -> bool:
        """
        Return value style: boolean
        """
        Util.assert_isa(self, BuildSystem_Qt5)
        module = self.module
        srcdir = module.fullpath("source")
        script = f"{srcdir}/configure"
        
        if not os.path.exists(script) and not Debug().pretending():
            Debug().error(f"\tMissing configure script for r[b[{module}]")
            return False
        
        commands = re.split(r"\s+", module.getOption("configure-flags"))
        commands.append("-confirm-license")
        commands.append("-opensource")
        commands.append("-nomake examples")
        commands.append("-nomake")
        commands.append("tests")
        
        # Get the user's CXXFLAGS
        cxxflags = module.getOption("cxxflags")
        module.buildContext().queueEnvironmentVariable("CXXFLAGS", cxxflags)
        
        installdir = module.getOption("install-dir")
        qt_installdir = module.getOption("qt-install-dir")
        
        if installdir and qt_installdir and installdir != qt_installdir:
            Debug().warning(textwrap.dedent(f"""\
                b[y[*]
                b[y[*] Building the Qt module, but the install directory for Qt is not set to the
                b[y[*] Qt directory to use.
                b[y[*]   install directory ('install-dir' option): b[{installdir}]
                b[y[*]   Qt install to use ('qt-install-dir'  option): b[{qt_installdir}]
                b[y[*]
                b[y[*] Try setting b[qt-install-dir] to the same setting as the Qt module's b[install-dir].
                b[y[*]
                """))
        
        if not installdir:
            installdir = qt_installdir  # Use qt-install-dir for install if install-dir not set
        
        # Some users have added -prefix manually to their flags, they
        # probably shouldn't anymore. :)
        
        if any(re.match(r"^-prefix(=.*)?$", command) for command in commands):
            Debug().warning(textwrap.dedent(f"""\
                b[y[*]
                b[y[*] You have the y[-prefix] option selected in your {module} configure flags.
                b[y[*] kde-builder will correctly add the -prefix option to match your Qt
                b[y[*] directory setting, so you do not need to use -prefix yourself.
                b[y[*]
                """))
        
        commands.append("-prefix")
        commands.append(installdir)
        commands.insert(0, script)
        
        builddir = module.fullpath("build")
        old_flags = module.getPersistentOption("last-configure-flags") or ""
        cur_flags = Util.get_list_digest(commands)
        
        if cur_flags == old_flags and not module.getOption("reconfigure") and os.path.exists(f"{builddir}/Makefile"):
            return True
        
        Debug().note(f"\tb[r[LGPL license selected for Qt].  See {srcdir}/LICENSE.LGPL")
        Debug().info("\tRunning g[configure]...")
        
        module.setPersistentOption("last-configure-flags", cur_flags)
        
        return Util.await_exitcode(Util.run_logged_p(module, "configure", builddir, commands))
