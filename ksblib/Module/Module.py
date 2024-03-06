import glob
import os
import re
import shutil
import sys
import textwrap
import traceback
from ..Util.Conditional_Type_Enforced import conditional_type_enforced
from ..Util.Conditional_Type_Enforced import WithSubclasses
# from overrides import override
import copy

from ..OptionsBase import OptionsBase
from ..IPC.IPC import IPC
from ..Util.Util import Util
from ..Debug import Debug

from ..Updater.Git import Updater_Git
from ..Updater.KDEProject import Updater_KDEProject
from ..Updater.KDEProjectMetadata import Updater_KDEProjectMetadata
from ..Updater.Qt5 import Updater_Qt5

from ksblib.BuildException import BuildException, BuildException_Config

from ..BuildSystem.BuildSystem import BuildSystem
from ..BuildSystem.Autotools import BuildSystem_Autotools
from ..BuildSystem.QMake import BuildSystem_QMake
from ..BuildSystem.QMake6 import BuildSystem_QMake6
from ..BuildSystem.Qt4 import BuildSystem_Qt4
from ..BuildSystem.Qt5 import BuildSystem_Qt5
from ..BuildSystem.Qt6 import BuildSystem_Qt6
from ..BuildSystem.KDECMake import BuildSystem_KDECMake
from ..BuildSystem.CMakeBootstrap import BuildSystem_CMakeBootstrap
from ..BuildSystem.Meson import BuildSystem_Meson


@conditional_type_enforced
class Module(OptionsBase):
    """
    DESCRIPTION
    
    A subclass of :class:`OptionsBase`, which represents a source code module of some
    sort that can be updated, built, tested and installed.
    
    This uses abstract interfaces to represent the buildsystem and the source code
    version control system (:class:`BuildSystem` and :class:`Updater` respectively).
    
    Includes a stringifying overload and can be sorted amongst other ksblib.Modules.
    
    SYNOPSIS
    ::
    
        module = ksblib.Module(ctx, 'module-name')
        module.update() or die "no update!"
        module.build() or die "no build/install!"
    
        modulesFromSet = moduleSet.convertToModules(ctx)
        for module in modulesFromSet:
            print(f"module name: {module}")
    """
    
    def __init__(self, ctx, name):
        self.ctx = ctx
        self.name = name
        
        if not self.name:
            BuildException.croak_internal("Empty Module constructed")
        
        OptionsBase.__init__(self)
        
        # If building a BuildContext instead of a ksb::Module, then the context
        # can't have been setup yet...
        if self.__class__.__name__ != "BuildContext" and ctx.__class__.__name__ != "BuildContext":
            BuildException.croak_internal(f"Invalid context {ctx}")
        
        phases = None
        if ctx:
            # Clone the passed-in phases so we can be different. They may be modified later in setOption.
            phases = copy.copy(ctx.phases)
        
        # newOptions:
        self.name = name
        self.scm_obj = None
        self.build_obj = None
        self.phases = phases
        self.context = ctx
        self.module_set = None  # in perl it was called module-set (i.e. via "-")
        self.post_build_msgs = []
        
        # Record current values of what would be last source/build dir, if present,
        # before they are potentially reset during the module build.
        self.setOption({"#last-source-dir": self.getPersistentOption("source-dir") or ""})
        self.setOption({"#last-build-dir": self.getPersistentOption("build-dir") or ""})
        self.scm_obj = None
    
    def __str__(self) -> str:  # Add stringify operator.
        return self.toString()
    
    def phases(self):
        return self.phases
    
    def moduleSet(self):
        from ..ModuleSet.Null import ModuleSet_Null
        if not self.module_set:
            self.module_set = ModuleSet_Null()
        return self.module_set
    
    def setModuleSet(self, moduleSet) -> None:
        from ..ModuleSet.ModuleSet import ModuleSet
        Util.assert_isa(moduleSet, ModuleSet)
        self.module_set = moduleSet
    
    def getSubdirPath(self, subdirOption) -> str:
        """
        Subroutine to retrieve a subdirectory path with tilde-expansion and
        relative path handling.
        The parameter is the option key (e.g. build-dir or log-dir) to read and
        interpret.
        """
        directory = self.getOption(subdirOption)
        
        # If build-dir starts with a slash, it is an absolute path.
        if directory.startswith("/"):
            return directory
        
        # Make sure we got a valid option result.
        if not directory:
            raise ValueError(f"Reading option for {subdirOption} gave empty directory!")
        
        # If it starts with a tilde, expand it out.
        if directory.startswith("~"):
            directory = re.sub(r"^~", os.getenv("HOME"), directory)
        else:
            # Relative directory, tack it on to the end of kdesrcdir.
            kdesrcdir = self.getOption("source-dir")
            directory = f"{kdesrcdir}/{directory}"
        
        return directory
    
    def getInstallPathComponents(self, dirtype) -> dict:
        """
        Returns the directory that a module should be installed in.
        
        NOTE: The return value is a hash. The key 'module' will return the final
        module name, the key 'path' will return the full path to the module. The
        key 'fullpath' will return their concatenation.
        
        For example, with $module == 'KDE/kdelibs', and no change in the dest-dir
        option, you'd get something like:
        
        > {
        >   'path'     => '/home/user/kdesrc/KDE',
        >   'module'   => 'kdelibs',
        >   'fullpath' => '/home/user/kdesrc/KDE/kdelibs'
        > }
        
        If dest-dir were changed to e.g. extragear-multimedia, you'd get:
        
        > {
        >   'path'     => '/home/user/kdesrc',
        >   'module'   => 'extragear-multimedia',
        >   'fullpath' => '/home/user/kdesrc/extragear-multimedia'
        > }
        
        Parameters:
          pathType - Either 'source' or 'build'.
        
        Returns:
          hash (Not a hashref; See description).
        """
        module = self
        Util.assert_isa(module, Module)
        
        destdir = module.destDir()
        srcbase = module.getSourceDir()
        if dirtype == "build":
            srcbase = module.getSubdirPath("build-dir")
        
        combined = f"{srcbase}/{destdir}"
        
        # Remove dup //
        combined = re.sub("/+", "/", combined)
        
        parts = combined.split("/")
        result = {"module": parts.pop(), "path": "/".join(parts)}
        result["fullpath"] = f"""{result["path"]}/{result["module"]}"""
        
        # We used to have code here to migrate very old directory layouts. It was
        # removed as of about 2013-09-29.
        
        return result
    
    def getSourceDir(self) -> str:
        """
        Do note that this returns the *base* path to the source directory,
        without the module name or kde_projects stuff appended. If you want that
        use subroutine fullpath().
        """
        return self.getSubdirPath("source-dir")
    
    # pl2py: perl specific
    # def name(self):
    #     return self.name
    
    def scm(self):
        
        if self.scm_obj:
            return self.scm_obj
        
        if not self.scm_obj:
            self.scm_obj = Updater_Git(self)
        return self.scm_obj
    
    def setScmType(self, scmType) -> None:
        newType = None
        if scmType == "git":
            newType = Updater_Git(self)
        elif scmType == "proj":
            newType = Updater_KDEProject(self)
        elif scmType == "metadata":
            newType = Updater_KDEProjectMetadata(self)
        elif scmType == "qt5":
            newType = Updater_Qt5(self)
        else:
            newType = None
        
        self.scm_obj = newType
    
    def scmType(self) -> str:
        """
        Returns a string describing the scm platform of the given module.
        Return value: 'git' at this point, as appropriate.
        """
        return self.scm().name()
    
    def currentScmRevision(self) -> str:
        return self.scm().currentRevisionInternal()
    
    def buildSystemFromName(self, name) -> WithSubclasses(BuildSystem):
        """
        Returns a new build system object, given the appropriate name.
        This is a sub-optimal way to fix the problem of allowing users to override
        the detected build system (we could instead use introspection to figure out
        available build systems at runtime). However, KISS...
        """
        buildSystemClasses = {
            "generic": BuildSystem,
            "qmake": BuildSystem_QMake,
            "qmake6": BuildSystem_QMake6,
            "cmake-bootstrap": BuildSystem_CMakeBootstrap,
            "kde": BuildSystem_KDECMake,
            "qt": BuildSystem_Qt4,
            "qt5": BuildSystem_Qt5,
            "qt6": BuildSystem_Qt6,
            "autotools": BuildSystem_Autotools,
            "meson": BuildSystem_Meson,
        }
        
        class_name = buildSystemClasses[name.lower()] or None
        if not class_name:
            BuildException.croak_runtime(f"Invalid build system {name} requested")
        return class_name(self)
    
    def buildSystem(self) -> WithSubclasses(BuildSystem):
        if self.build_obj and self.build_obj.name() != "generic":
            return self.build_obj
        
        if userBuildSystem := self.getOption("override-build-system"):
            self.build_obj = self.buildSystemFromName(userBuildSystem)
            return self.build_obj
        
        # If not set, let's guess.
        buildType = None
        sourceDir = self.fullpath("source")
        
        # This test must come before the KDE buildsystem's as cmake's own
        # bootstrap system also has CMakeLists.txt
        if not buildType and os.path.exists(f"{sourceDir}/CMakeLists.txt") and os.path.exists(f"{sourceDir}/bootstrap"):
            buildType = BuildSystem_CMakeBootstrap(self)
        
        if not buildType and (os.path.exists(f"{sourceDir}/CMakeLists.txt") or self.isKDEProject()):
            buildType = BuildSystem_KDECMake(self)
        
        # We have to assign to an array to force glob to return all results,
        # otherwise it acts like a non-reentrant generator whose output depends on
        # how many times it's been called...
        if not buildType and (files := glob.glob(f"{sourceDir}/*.pro")):
            buildType = BuildSystem_QMake(self)
        
        # 'configure' is a popular fall-back option even for other build
        # systems so ensure we check last for autotools.
        if not buildType and (os.path.exists(f"{sourceDir}/configure") or os.path.exists(f"{sourceDir}/autogen.sh")):
            buildType = BuildSystem_Autotools(self)
        
        # Someday move this up, but for now ensure that Meson happens after
        # configure/autotools support is checked for.
        if not buildType and os.path.exists(f"{sourceDir}/meson.build"):
            buildType = BuildSystem_Meson(self)
        
        # Don't just assume the build system is KDE-based...
        if not buildType:
            buildType = BuildSystem(self)
        
        self.build_obj = buildType
        return self.build_obj
    
    def setBuildSystem(self, obj) -> None:
        """
        Sets the build system **object**, although you can find the build system
        type afterwards (see buildSystemType).
        """
        Util.assert_isa(obj, BuildSystem)
        self.build_obj = obj
    
    def buildSystemType(self) -> str:
        """
        Current possible build system types:
        KDE (i.e. cmake), Qt, autotools (either
        configure or autogen.sh). A final possibility is 'pendingSource' which
        simply means that we don't know yet.
        
        If the build system type is not set ('pendingSource' counts as being
        set!) when this function is called then it will be autodetected if
        possible, but note that not all possible types will be detected this way.
        If in doubt use setBuildSystemType
        """
        return self.buildSystem().name()
    
    def build(self) -> bool:
        """
        Subroutine to build this module.
        Returns boolean false on failure, boolean true on success.
        """
        Util.assert_isa(self, Module)
        moduleName = self.name
        pathinfo = self.getInstallPathComponents("build")
        builddir = pathinfo["fullpath"]
        buildSystem = self.buildSystem()
        
        if buildSystem.name() == "generic" and not Debug().pretending() and not self.hasOption("custom-build-command"):
            Debug().error(f"\tr[b[{self}] does not seem to have a build system to use.")
            return False
        
        # Ensure we're in a known directory before we start; some options remove
        # the old build directory that a previous module might have been using.
        Util().super_mkdir(pathinfo["path"])
        Util.p_chdir(pathinfo["path"])
        
        if not self.setupBuildSystem():
            return False
        if self.getOption("build-system-only"):
            return True
        
        buildResults = buildSystem.buildInternal()
        if not buildResults["was_successful"]:
            return False
        
        self.setPersistentOption("last-build-rev", self.currentScmRevision())
        
        # TODO: This should be a simple phase to run.
        if self.getOption("run-tests"):
            self.buildSystem().runTestsuite()
        
        if not buildResults.get("work_done", None) and not self.getOption("refresh-build") and self.getPersistentOption("last-install-rev") is not None:
            Debug().info("\tNo changes from build, skipping install (--refresh-build this module to force install)")
            return True
        elif not self.getOption("install-after-build"):
            Debug().info("\tSkipping install due to install-after-build setting")
            return True
        
        # TODO: Likewise this should be a phase to run.
        return self.install()
    
    def setupBuildSystem(self) -> bool:
        """
        Subroutine to setup the build system in a directory.
        Returns boolean true on success, boolean false (0) on failure.
        """
        Util.assert_isa(self, Module)
        moduleName = self.name
        
        buildSystem = self.buildSystem()
        
        if buildSystem.name() == "generic" and self.hasOption("custom-build-command"):
            Debug().info(f" b[*] No build system detected for b[y[{self}], assuming custom build command will handle")
            return True
        
        if buildSystem.name() == "generic" and not Debug().pretending():
            BuildException.croak_internal("Build system determination still pending when build attempted.")
        
        # Check if a previous build has happened in a different directory (which
        # can happen due to name changes on KDE.org side or flat-layout option
        # toggled)
        builddir = self.fullpath("build")
        oldBuildDir = self.getOption("#last-build-dir")
        if not Debug().pretending() and builddir != oldBuildDir and os.path.isdir(oldBuildDir) and not os.path.exists(builddir):
            Debug().note(f" y[b[*] Build directory setting has changed to {builddir}.")
            Debug().note(f" y[b[*] Moving old build directory at {oldBuildDir} to the new location.")
            
            try:
                shutil.move(oldBuildDir, builddir)
            except Exception as e:
                Debug().warning(textwrap.dedent(f"""\
                    r[b[*] Unable to move {oldBuildDir}
                    r[b[*] to {builddir}
                    r[b[*] Error: {e}
                    y[b[*]
                    y[b[*] Will proceed, generating a new build dir.
                    """))
        
        refreshReason = buildSystem.needsRefreshed()
        if refreshReason != "":
            # The build system needs created, either because it doesn't exist, or
            # because the user has asked that it be completely rebuilt.
            Debug().info(f"\tPreparing build system for y[{self}].")
            
            # Check to see if we're actually supposed to go through the
            # cleaning process.
            if not self.getOption("#cancel-clean") and not buildSystem.cleanBuildSystem():
                Debug().warning(f"\tUnable to clean r[{self}]!")
                return False
        
        result = Util.await_result(buildSystem.createBuildSystem())
        if not result:
            Debug().error(f"\tError creating r[{self}]'s build system!")
            return False
        
        # Now we're in the checkout directory
        # So, switch to the build dir.
        # builddir is automatically set to the right value for qt
        Util.p_chdir(builddir)
        
        if not buildSystem.configureInternal():
            Debug().error(f"\tUnable to configure r[{self}] with " + self.buildSystemType())
            
            # Add undocumented ".refresh-me" file to build directory to flag
            # for --refresh-build for this module on next run. See also the
            # "needsRefreshed" subroutine.
            if fh := open(".refresh-me", "w"):
                print("# Build directory will be re-generated next kde-builder run", file=fh)
                print("# due to failing to complete configuration on the last run", file=fh)
                fh.close()
            return False
        return True
    
    def install(self) -> bool:
        """
        Responsible for installing the module (no update, build, etc.)
        Returns boolean false on failure, boolean true on success.
        Exceptions may be thrown for abnormal conditions (e.g. no build dir exists)
        """
        Util.assert_isa(self, Module)
        builddir = self.fullpath("build")
        buildSysFile = self.buildSystem().configuredModuleFileName()
        
        if not Debug().pretending() and not os.path.exists(f"{builddir}/{buildSysFile}"):
            Debug().warning(f"\tThe build system doesn't exist for r[{self}].")
            Debug().warning("\tTherefore, we can't install it. y[:-(].")
            return False
        
        self.setupEnvironment()
        
        makeInstallOpts = self.getOption("make-install-prefix").split(" ")
        makeInstallOpts = [el for el in makeInstallOpts if el != ""]  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it.
        
        # We can optionally uninstall prior to installing
        # to weed out old unused files.
        if self.getOption("use-clean-install") and self.getPersistentOption("last-install-rev"):
            if not self.buildSystem().uninstallInternal(makeInstallOpts):
                Debug().warning(f"\tUnable to uninstall r[{self}] before installing the new build.")
                Debug().warning("\tContinuing anyways...")
            else:
                self.unsetPersistentOption("last-install-rev")
        
        if not self.buildSystem().installInternal(makeInstallOpts):
            Debug().error(f"\tUnable to install r[{self}]!")
            self.buildContext().markModulePhaseFailed("install", self)
            return False
        
        if Debug().pretending():
            Debug().pretend(f"\tWould have installed g[{self}]")
            return True
        
        # Past this point we know we've successfully installed, for real.
        
        self.setPersistentOption("last-install-rev", self.currentScmRevision())
        
        remove_setting = self.getOption("remove-after-install")
        
        # Possibly remove the srcdir and builddir after install for users with
        # a little bit of HD space.
        if remove_setting == "all":
            # Remove srcdir
            srcdir = self.fullpath("source")
            Debug().note(f"\tRemoving b[r[{self} source].")
            Util.safe_rmtree(srcdir)
        
        if remove_setting == "builddir" or remove_setting == "all":
            # Remove builddir
            Debug().note(f"\tRemoving b[r[{self} build directory].")
            Util.safe_rmtree(builddir)
            
            # We're likely already in the builddir, so chdir back to the root
            os.chdir("/")
        return True
    
    def uninstall(self) -> bool:
        """
        Handles uninstalling this module
        
        Returns boolean false on failure, boolean true on success.
        """
        Util.assert_isa(self, Module)
        builddir = self.fullpath("build")
        buildSysFile = self.buildSystem().configuredModuleFileName()
        
        if not Debug().pretending() and not os.path.exists(f"{builddir}/{buildSysFile}"):
            Debug().warning(f"\tThe build system doesn't exist for r[{self}].")
            Debug().warning("\tTherefore, we can't uninstall it.")
            return False
        
        self.setupEnvironment()
        
        makeInstallOpts = self.getOption("make-install-prefix").split(" ")
        
        if not self.buildSystem().uninstallInternal(makeInstallOpts):
            Debug().error(f"\tUnable to uninstall r[{self}]!")
            self.buildContext().markModulePhaseFailed("install", self)
            return False
        
        if Debug().pretending():
            Debug().pretend(f"\tWould have uninstalled g[{self}]")
            return True
        
        self.unsetPersistentOption("last-install-rev")
        return True
    
    def buildContext(self):
        return self.context
    
    def applyUserEnvironment(self) -> None:
        """
        Integrates 'set-env' option to the build context environment
        """
        Util.assert_isa(self, Module)
        ctx = self.buildContext()
        
        # Let's see if the user has set env vars to be set.
        # Note the global set-env must be checked separately anyways, so
        # we limit inheritance when searching.
        if ctx.name == self.name:
            env_hash_ref = ctx.getOption("set-env")
        else:
            env_hash_ref = self.getOption("set-env", "module")
        
        for key, value in env_hash_ref.items():
            ctx.queueEnvironmentVariable(key, value)
    
    def setupEnvironment(self) -> None:
        """
        Establishes proper build environment in the build context. Should be run
        before forking off commands for e.g. updates, builds, installs, etc.
        """
        ctx = self.buildContext()
        prefix = self.installationPath()
        
        # Add global set-envs and context
        self.buildContext().applyUserEnvironment()
        
        # Build system's environment injection
        buildSystem = self.buildSystem()
        
        # Suppress injecting qt-install-dir/install-dir related environment variables if a toolchain is also set
        # Let the toolchain files/definitions take care of themselves.
        if buildSystem.hasToolchain():
            Debug().whisper(f"\tNot setting environment variables for b[{self}]: a custom toolchain is used")
        else:
            installdir = self.getOption("install-dir")
            qt_installdir = self.getOption("qt-install-dir")
            libname = self.getOption("libname")  # e.g. "lib" or "lib64"
            
            # Ensure the platform libraries we're building can be found, as long as they
            # are not the system's own libraries.
            for platformDir in [qt_installdir, installdir]:
                if not platformDir:  # OK, assume system platform is usable
                    continue
                if platformDir == "/usr":  # Don't 'fix' things if system platform manually set
                    continue
                
                ctx.prependEnvironmentValue("PKG_CONFIG_PATH", f"{platformDir}/{libname}/pkgconfig")
                ctx.prependEnvironmentValue("LD_LIBRARY_PATH", f"{platformDir}/{libname}")
                ctx.prependEnvironmentValue("PATH", f"{platformDir}/bin")
            
            binpath = self.getOption("binpath")
            libpath = self.getOption("libpath")
            
            if binpath:
                ctx.prependEnvironmentValue("PATH", binpath)
            if libpath:
                ctx.prependEnvironmentValue("LD_LIBRARY_PATH", libpath)
        
        buildSystem.prepareModuleBuildEnvironment(ctx, self, prefix)
        
        # Read in user environment defines
        if self.name != ctx.name:  # pl2py: in perl the compare function was called here. See comment there. We just compare here without that function.
            self.applyUserEnvironment()
    
    def getLogDir(self) -> str:
        """
        Returns the path to the log directory used during this run for this
        ksb::Module, based on an autogenerated unique id. The id doesn't change
        once generated within a single run of the script.
        """
        return self.buildContext().getLogDirFor(self)
    
    def getLogPath(self, path) -> str:
        """
        Returns a full path that can be open()'d to write a log
        file, based on the given basename (with extension).
        Updates the 'latest' symlink as well, unlike getLogDir
        Use when you know you're going to create a new log
        """
        return self.buildContext().getLogPathFor(self, path)
    
    def toString(self) -> str:
        return self.name
    
    # This is left here only for reference. todo After dropping perl version, we can delete this comment.
    # def compare(self, other):
    #     # pl2py: the only place where this function was called in perl was the comparison operator in the end of setupEnvironment function.
    #     # It returned -1, 0, 1 depending on if self.name is less, equal or bigger than ctx.name.
    #     # The interesting thing is that despite function returns some value, when it arrives to statement `my $n = $self == $ctx;` it became "converted" to the wanted.
    #     # For example, when names are different, and -1 is returned by compare, $n gets the empty string (which reads as false).
    #     # And if names are the same, (for example, I intentionally made a module called "global", 0 is returned, and 1 is arrived to $n (which reads as true).
    #     # So instead of using this function, we will just compare as needed in the place where that comparison was invoked.
    #     # But I (Andrew Shark) will place the code which was the effect of calling this comparison here, for reference.
    #     return self.name == other.name
    
    def update(self, ipc, ctx) -> bool:
        moduleName = self.name
        module_src_dir = self.getSourceDir()
        kdesrc = ctx.getSourceDir()
        
        if kdesrc != module_src_dir:
            # This module has a different source directory, ensure it exists.
            if not Util().super_mkdir(module_src_dir):
                Debug().error(f"Unable to create separate source directory for r[{self}]: {module_src_dir}")
                ipc.sendIPCMessage(IPC.MODULE_FAILURE, moduleName)
        
        # Check for whether path to source dir has changed due to directory-layout
        # option or changes to metadata.
        fullpath = self.fullpath("source")
        oldSourceDir = self.getOption("#last-source-dir")
        if not Debug().pretending() and fullpath != oldSourceDir and os.path.isdir(oldSourceDir) and not os.path.exists(fullpath):
            Debug().note(f" y[b[*] Source directory setting has changed to {fullpath}.")
            Debug().note(f" y[b[*] Moving old source directory at {oldSourceDir} to the new location.")
            
            try:
                shutil.move(oldSourceDir, fullpath)
            except Exception as e:
                Debug().warning(textwrap.dedent(f"""
                    r[b[*] Unable to move {oldSourceDir}
                    r[b[*] to {fullpath}
                    r[b[*] Error: {e}
                    y[b[*]
                    y[b[*] Will proceed, generating a new source dir.
                    """))
        count = None
        returnValue = None
        
        try:
            count = self.scm().updateInternal(ipc)
        except Exception as e:
            traceback.print_exc()
            reason = IPC.MODULE_FAILURE
            
            if BuildException.had_an_exception(e):
                if e.exception_type == "ConflictPresent":
                    reason = IPC.MODULE_CONFLICT
                else:
                    ctx.markModulePhaseFailed("build", self)
                e = e.message
            
            Debug().error(f"Error updating r[{self}], removing from list of packages to build.")
            Debug().error(f" > y[{e}]")
            
            ipc.sendIPCMessage(reason, moduleName)
            self.phases.filterOutPhase("build")
            returnValue = False
        else:
            message = ""
            if count is None:
                message = Debug().colorize("b[y[Unknown changes].")
                ipc.notifyUpdateSuccess(moduleName, message)
            elif count:
                if count == 1:
                    message = "1 file affected."
                if count != 1:
                    message = f"{count} files affected."
                ipc.notifyUpdateSuccess(moduleName, message)
            else:
                message = "0 files affected."
                refreshReason = self.buildSystem().needsRefreshed()
                ipc.sendIPCMessage(IPC.MODULE_UPTODATE, f"{moduleName},{refreshReason}")
            
            # We doing e.g. --src-only, the build phase that normally outputs
            # number of files updated doesn't get run, so manually mention it
            # here.
            if not ipc.supportsConcurrency():
                Debug().info(f"\t{self} update complete, {message}")
            
            returnValue = True
        Debug().info("")  # Print empty line.
        return returnValue
    
    # @override
    def setOption(self, options: dict) -> None:
        """
        This calls OptionsBase::setOption and performs any Module-specific
        handling.
        """
        
        # Ensure we don't accidentally get fed module-set options
        for mso in ["use-modules", "ignore-modules"]:
            if mso in options:
                Debug().error(f" r[b[*] module b[{self}] should be declared as module-set to use b[{mso}]")
                raise BuildException_Config(mso, f"Option {mso} can only be used in module-set")
        
        # Special case handling.
        if "filter-out-phases" in options:
            for phase in options["filter-out-phases"].split(" "):
                self.phases.filterOutPhase(phase)
            del options["filter-out-phases"]
        
        # Phases changes handling
        #
        # The context phases were handled by cmdline. The module-sets will eventually be expanded to modules. For module, we will handle its phases.
        if "no-src" in options:
            self.phases.filterOutPhase("update")
            del options["no-src"]
        if "no-install" in options:
            self.phases.filterOutPhase("install")
            del options["no-install"]
        if "no-tests" in options:
            self.phases.filterOutPhase("test")  # May not work properly yet.
            del options["no-tests"]
        if "no-build" in options:
            self.phases.filterOutPhase("build")
            del options["no-build"]
        if "uninstall" in options:
            # Not useful yet. Currently only may be useful to disable uninstallation when uninstalling with cmdline ("uninstall" run_mode)
            if self.phases.has("uninstall"):
                self.phases.phases("uninstall")
            else:
                self.phases.clear()
            del options["uninstall"]
        if "build-only" in options:
            if self.phases.has("build"):
                self.phases.phases("build")
            else:
                self.phases.clear()
            del options["build-only"]
        if "install-only" in options:
            # Not useful yet, because install is invoked by run_mode or in the end of building function. See a todo with text "Likewise this should be a phase to run."
            if self.phases.has("install"):
                self.phases.phases("install")
            else:
                self.phases.clear()
            del options["install-only"]
        
        OptionsBase.setOption(self, options)
    
    # @override(check_signature=False)
    def getOption(self, key, levelLimit="allow-inherit") -> str | bool | dict | None:
        """
        This subroutine returns an option value for a given module.  Some globals
        can't be overridden by a module's choice (but see 2nd parameter below).
        If so, the module's choice will be ignored, and a warning will be issued.
        
        Option names are case-sensitive!
        
        Some options (e.g. cmake-options, configure-flags) have the global value
        and then the module's own value appended together. To get the actual
        module setting you must use the level limit parameter set to 'module'.
        
        Likewise, some qt module options do not obey the previous proviso since
        Qt options are not likely to agree nicely with generic KDE buildsystem
        options.
        
        1st parameter: Name of option
        2nd parameter: Level limit (optional). If not present, then the value
        'allow-inherit' is used. Options:
          - allow-inherit: Module value is used if present (with exceptions),
            otherwise global is used.
          - module: Only module value is used (if you want only global then use the
            buildContext) NOTE: This overrides global "sticky" options as well!
        
        Returned type - for example used in
          bool - "#guessed-kde-project"
          None - unexisting key in module-only level
          dict - "set-env"
          str - almost everything else
        """
        
        ctx = self.buildContext()
        
        # Some global options would probably make no sense applied to Qt.
        qtCopyOverrides = ["branch", "configure-flags", "tag", "cxxflags"]
        if key in qtCopyOverrides and self.buildSystemType() == "Qt":
            levelLimit = "module"
        
        Util.assert_in(levelLimit, ["allow-inherit", "module"])
        
        # If module-only, check that first.
        if levelLimit == "module":
            return self.options[key] if key in self.options else None
        
        ctxValue = ctx.getOption(key)  # we'll use this a lot from here
        
        # Some global options always override module options.
        if ctx.hasStickyOption(key):
            return ctxValue
        
        # Some options append to the global (e.g. conf flags)
        confFlags = ["cmake-options", "configure-flags", "cxxflags"]
        if key in confFlags and ctxValue:
            return (f"{ctxValue} " + self.options.get(key, "")).strip()
        
        # Everything else overrides the global option, unless it's simply not
        # set at all.
        return self.options.get(key, ctxValue)
    
    def getPersistentOption(self, key) -> str | int | None:
        """
        Gets persistent options set for this module. First parameter is the name
        of the option to lookup. Undef is returned if the option is not set,
        although even if the option is set, the value returned might be empty.
        Note that ksb::BuildContext also has this function, with a slightly
        different signature, which OVERRIDEs this function since Perl does not
        have parameter-based method overloading.
        
        Return types: the same as BuildContext::getPersistentOption()
        """
        return self.buildContext().getPersistentOption(self.name, key)
    
    def setPersistentOption(self, key, value) -> None:
        """
        Sets a persistent option (i.e. survives between processes) for this module.
        First parameter is the name of the persistent option.
        Second parameter is its actual value.
        See the warning for getPersistentOption above, it also applies for this
        method vs. ksb::BuildContext::setPersistentOption
        """
        return self.buildContext().setPersistentOption(self.name, key, value)
    
    def unsetPersistentOption(self, key) -> None:
        """
        Unsets a persistent option for this module.
        Only parameter is the name of the option to unset.
        """
        self.buildContext().unsetPersistentOption(self.name, key)
    
    def fullpath(self, dirtype) -> str:
        # Returns the path to the desired directory type (source or build),
        # including the module destination directory itself.
        Util.assert_in(dirtype, ["build", "source"])
        
        pathinfo = self.getInstallPathComponents(dirtype)
        return pathinfo["fullpath"]
    
    def fullProjectPath(self) -> str:
        """
        Returns the "full kde-projects path" for the module. As should be obvious by
        the description, this only works for modules with an scm type that is a
        Updater::KDEProject (or its subclasses), but modules that don't fall into this
        hierarchy will just return the module name (with no path components) anyways.
        """
        return self.getOption("#kde-project-path", "module") or self.name
    
    def isKDEProject(self) -> bool:
        """
        Returns true if this module is (or was derived from) a kde-projects module.
        """
        return self.scmType() == "proj"
    
    def destDir(self) -> str:
        """
        Subroutine to return the name of the destination directory for the
        checkout and build routines.  Based on the dest-dir option.  The return
        value will be relative to the src/build dir.  The user may use the
        '$MODULE' or '${MODULE}' sequences, which will be replaced by the name of
        the module in question.
        """
        destDir = self.getOption("dest-dir")
        basePath = None
        
        layout = self.getOption("directory-layout")
        if layout == "flat":
            basePath = self.name
        elif layout == "invent":  # invent layout is the modern layout for proper KDE projects
            basePath = self.getOption("#kde-repo-path", "module")
            basePath = basePath or self.name  # Default if not provided in repo-metadata
        elif layout == "metadata":
            basePath = self.getOption("#kde-project-path", "module")
            basePath = basePath or self.name  # Default if not provided in repo-metadata
        else:
            if not self.hasOption("#warned-invalid-directory-layout"):  # avoid spamming
                Debug().warning(f"y[ * Invalid b[directory-layout]y[ value: \"{layout}\". Will use b[flat]y[ instead for b[{self}]")
                self.setOption({"#warned-invalid-directory-layout": True})
            basePath = self.name
        
        # Note the default dest-dir option is '${MODULE}' so this normally is used
        destDir = re.sub(r"(\$\{MODULE})|(\$MODULE\b)", basePath, destDir)
        
        return destDir
    
    def installationPath(self) -> str:
        """
        Subroutine to return the installation path of a given module (the value
        that is passed to the CMAKE_INSTALL_PREFIX CMake option).
        It is based on the "install-dir" option.
        The user may use '$MODULE' or '${MODULE}' in the "install-dir" option to have
        them replaced by the name of the module in question.
        """
        Util.assert_isa(self, Module)
        path = self.getOption("install-dir")
        moduleName = self.name
        path = re.sub(r"(\$\{MODULE})|(\$MODULE\b)", moduleName, path)
        
        return path
    
    def getPostBuildMessages(self) -> list:
        """
        Returns a list of any 'post-build' messages that have been set for the module
        to show after the build has ended. These may be messages such as warning of a
        local source conflict that may have scrolled past or similar things the user
        needs to know about.
        
        Each entry in the list will be a text message that should be shown (perhaps
        with additional formatting).
        """
        Util.assert_isa(self, Module)
        return self.post_build_msgs
    
    def addPostBuildMessage(self, new_msg) -> None:
        """
        Adds the given message to the list of post-build messages to show to the user
        """
        self.post_build_msgs.append(new_msg)
