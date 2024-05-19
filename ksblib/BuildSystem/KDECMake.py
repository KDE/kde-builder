# SPDX-FileCopyrightText: 2012, 2013, 2016, 2018, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 Kristen McWilliam <kmcwilliampublic@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations
import os.path
import re
import sys
# from overrides import override

from .BuildSystem import BuildSystem
from ..BuildException import BuildException
from ..Util.Util import Util
from ..Util.LoggedSubprocess import Util_LoggedSubprocess
from ..Debug import Debug, kbLogger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..Module.Module import Module
    from ..BuildContext import BuildContext

logger_ide_proj = kbLogger.getLogger("ide_project_configs")
logger_buildsystem = kbLogger.getLogger("build-system")


class BuildSystem_KDECMake(BuildSystem):
    """
    Class responsible for building CMake-based modules, with special support for KDE modules.
    """

    BASE_GENERATOR_MAP = {
        "Ninja": {
            "optionsName": "ninja-options",
            "installTarget": "install",
            "requiredPrograms": ["ninja", "cmake", "qmake"],
            "buildCommands": ["ninja"]
        },
        "Unix Makefiles": {
            "optionsName": "make-options",
            "installTarget": "install/fast",
            "requiredPrograms": ["cmake", "qmake"],
            # Non Linux systems can sometimes fail to build when GNU Make would work,
            # so prefer GNU Make if present, otherwise try regular make.
            "buildCommands": ["gmake", "make"]
        }
    }

    # Extra generators that are compatible to the base generators above.
    # See: https://cmake.org/cmake/help/latest/manual/cmake-generators.7.html#extra-generators
    GENERATOR_MAP = {
        "Ninja": BASE_GENERATOR_MAP["Ninja"],
        "CodeBlocks - Ninja": BASE_GENERATOR_MAP["Ninja"],
        "CodeLite - Ninja": BASE_GENERATOR_MAP["Ninja"],
        "Sublime Text 2 - Ninja": BASE_GENERATOR_MAP["Ninja"],
        "Kate - Ninja": BASE_GENERATOR_MAP["Ninja"],
        "Eclipse CDT4 - Ninja": BASE_GENERATOR_MAP["Ninja"],

        "Unix Makefiles": BASE_GENERATOR_MAP["Unix Makefiles"],
        "CodeBlocks - Unix Makefiles": BASE_GENERATOR_MAP["Unix Makefiles"],
        "CodeLite - Unix Makefiles": BASE_GENERATOR_MAP["Unix Makefiles"],
        "Sublime Text 2 - Unix Makefiles": BASE_GENERATOR_MAP["Unix Makefiles"],
        "Kate - Unix Makefiles": BASE_GENERATOR_MAP["Unix Makefiles"],
        "Eclipse CDT4 - Unix Makefiles": BASE_GENERATOR_MAP["Unix Makefiles"]
    }

    def __init__(self, module):
        BuildSystem.__init__(self, module)
        self.cmake_generator = None
        self.cmake_toolchain = None

    @staticmethod
    def _checkGeneratorIsWhitelisted(generator: str) -> bool:
        return generator in BuildSystem_KDECMake.GENERATOR_MAP

    @staticmethod
    def _stripGeneratorFromCMakeOptions(args: list) -> list:
        nextShouldBeGenerator = 0
        filtered = []
        for i in args:
            accept = 1
            if nextShouldBeGenerator:
                nextShouldBeGenerator = 0
                accept = 0
            else:
                maybeGenerator = i
                match = re.match(r"^-G(\S*(\s*\S)*)\s*", maybeGenerator)
                if match:
                    generator = match.group(1) or ""
                    if generator == "":
                        nextShouldBeGenerator = 1
                    accept = 0
            if accept == 1:
                filtered.append(i)
        return filtered

    @staticmethod
    def _findGeneratorInCMakeOptions(args: list) -> str:
        nextShouldBeGenerator = 0
        filtered = []
        for i in args:
            accept = 0
            if nextShouldBeGenerator:
                nextShouldBeGenerator = 0
                accept = 1
            else:
                maybeGenerator = i
                match = re.match(r"^-G(\S*(\s*\S)*)\s*", maybeGenerator)
                if match:
                    generator = match.group(1) or ""
                    if generator != "":
                        accept = 1
                    else:
                        nextShouldBeGenerator = 1
            if accept == 1:
                filtered.append(i)

        for found in filtered:
            match = re.match(r"^-G(\S*(\s*\S)*)\s*", found)
            if match:
                found = match.group(1) or ""
            if not found == "":
                return found
        return ""

    @staticmethod
    def _checkToolchainOk(toolchain: str) -> bool:
        return toolchain != "" and os.path.isfile(toolchain) and os.access(toolchain, os.R_OK)

    @staticmethod
    def _stripToolchainFromCMakeOptions(args: list) -> list:
        filtered = []

        for maybeToolchain in args:
            accept = 1
            if re.match(r"^-DCMAKE_TOOLCHAIN_FILE=(\S*(\s*\S)*)\s*", maybeToolchain):
                accept = 0
            if accept == 1:
                filtered.append(maybeToolchain)
        return filtered

    @staticmethod
    def _findToolchainInCMakeOptions(args: list) -> str:
        found = None
        for maybeToolchain in args:
            match = re.match(r"^-DCMAKE_TOOLCHAIN_FILE=(\S*(\s*\S)*)\s*", maybeToolchain)
            if match:
                file = match.group(1) or ""
                if BuildSystem_KDECMake._checkToolchainOk(file):
                    accept = 1
                    found = maybeToolchain
                    break
            found = maybeToolchain
            break

        if found:
            match = re.match(r"^-DCMAKE_TOOLCHAIN_FILE=(\S*(\s*\S)*)\s*", found)
            if match:
                found = match.group(1) or ""
                if BuildSystem_KDECMake._checkToolchainOk(found):
                    return found
        return ""

    def _determineCmakeToolchain(self) -> str:
        module = self.module
        cmakeOptions = Util.split_quoted_on_whitespace(module.getOption("cmake-options"))

        toolchain = next((toolchain for toolchain in (self._findToolchainInCMakeOptions(cmakeOptions), module.getOption("cmake-toolchain")) if self._checkToolchainOk(toolchain)), None)
        return toolchain or ""

    def cmakeToolchain(self) -> str:
        if not self.cmake_toolchain:
            self.cmake_toolchain = self._determineCmakeToolchain()
        return self.cmake_toolchain

    # @override
    def hasToolchain(self) -> bool:
        return self.cmakeToolchain() != ""

    # @override(check_signature=False)
    def supportsAutoParallelism(self) -> bool:
        """
        Returns true if CMake is run with ninja, which supports setting -j
        automatically.
        """
        generator = self.cmakeGenerator()
        generatorOpts = BuildSystem_KDECMake.GENERATOR_MAP[generator]["optionsName"]

        if not generatorOpts:
            return False
        if generatorOpts == "ninja-options":
            return True
        return False

    def _determineCmakeGenerator(self) -> str:
        module = self.module
        cmakeOptions = Util.split_quoted_on_whitespace(module.getOption("cmake-options"))
        generator = next((gen for gen in (self._findGeneratorInCMakeOptions(cmakeOptions), module.getOption("cmake-generator"), "Unix Makefiles") if self._checkGeneratorIsWhitelisted(gen)), None)

        if not generator:
            BuildException.croak_internal(f"Unable to determine CMake generator for: {module}")
        return generator

    def cmakeGenerator(self) -> str:
        if self.cmake_generator is None:
            self.cmake_generator = self._determineCmakeGenerator()
        return self.cmake_generator

    @staticmethod
    # @override
    def needsInstalled() -> bool:
        return True

    @staticmethod
    # @override
    def name() -> str:
        return "KDE CMake"

    # @override
    def prepareModuleBuildEnvironment(self, ctx: BuildContext, module: Module, prefix: str) -> None:
        """
        Called by the module being built before it runs its build/install process. Should
        set up any needed environment variables, build context settings, etc., in preparation
        for the build and install phases.
        """

        # Suppress injecting qt-install-dir/install-dir related environment variables if a toolchain is also set
        # Let the toolchain files/definitions take care of themselves.
        if self.hasToolchain():
            return

        # Avoid moving /usr up in env vars
        if prefix != "/usr":
            # Find the normal CMake "config" mode files for find_package()
            ctx.prependEnvironmentValue("CMAKE_PREFIX_PATH", prefix)
            # Try to ensure that older "module" mode find_package() calls also point to right directory
            ctx.prependEnvironmentValue("CMAKE_MODULE_PATH", f"{prefix}/lib64/cmake:{prefix}/lib/cmake")
            # Set the plugin path correctly for configuration-time access e.g. by Extra CMake Modules
            ctx.prependEnvironmentValue("QT_PLUGIN_PATH", f"{prefix}/lib64/plugins:{prefix}/lib/plugins")
            ctx.prependEnvironmentValue("XDG_DATA_DIRS", f"{prefix}/share")

        qt_installdir = module.getOption("qt-install-dir")
        if qt_installdir and qt_installdir != prefix:
            # Ensure we can find Qt5's own CMake modules
            ctx.prependEnvironmentValue("CMAKE_PREFIX_PATH", qt_installdir)
            ctx.prependEnvironmentValue("CMAKE_MODULE_PATH", f"{qt_installdir}/lib/cmake")

    # @override(check_signature=False)
    def requiredPrograms(self) -> list[str]:
        """
        This should return a list of executable names that must be present to
        even bother attempting to use this build system. An empty list should be
        returned if there's no required programs.
        """
        generator = self.cmakeGenerator()
        required = BuildSystem_KDECMake.GENERATOR_MAP[generator]["requiredPrograms"]
        return required

    # @override(check_signature=False)
    def buildCommands(self) -> list[str]:
        """
        Returns a list of possible build commands to run, any one of which should
        be supported by the build system.
        """
        generator = self.cmakeGenerator()
        progs = BuildSystem_KDECMake.GENERATOR_MAP[generator]["buildCommands"]
        return progs

    @staticmethod
    # @override
    def configuredModuleFileName() -> str:
        return "cmake_install.cmake"

    # @override
    def runTestsuite(self) -> bool:
        Util.assert_isa(self, BuildSystem_KDECMake)
        module = self.module

        # Note that we do not run safe_make, which should really be called
        # safe_compile at this point.

        # Step 1: Ensure the tests are built, oh wait we already did that when we ran
        # CMake :)

        make_target = "test"
        if module.getOption("run-tests") == "upload":
            make_target = "Experimental"

        logger_buildsystem.info("\tRunning test suite...")

        # Step 2: Run the tests.
        buildCommand = self.defaultBuildCommand()
        numTests = "Some"  # overwritten by a specific number, hopefully

        cmd = Util_LoggedSubprocess().module(module).log_to("test-results").set_command([buildCommand, make_target])

        def on_child_output(line):
            match = re.match(r"([0-9]+) tests failed out of", line)
            if match:
                nonlocal numTests
                numTests = match.group(1)

        cmd.on({"child_output": on_child_output})  # pl2py: this is in testsuite

        result = Util.await_exitcode(cmd.start())

        if not result:
            logDir = module.getLogDir()
            logger_buildsystem.warning(f"\t{numTests} tests failed for y[{module}], consult {logDir}/test-results.log for info")
        else:
            logger_buildsystem.info("\tAll tests ran successfully.")
        return result

    # @override
    def installInternal(self, cmdPrefix: list[str]) -> bool:
        """
        Re-implementing the one in BuildSystem since in CMake we want to call
        make install/fast, so it only installs rather than building + installing
        """
        module = self.module
        generator = self.cmakeGenerator()
        target = BuildSystem_KDECMake.GENERATOR_MAP[generator]["installTarget"]

        if module.getOption("custom-build-command"):
            target = "install"

        return self.safe_make({
            "target": target,
            "message": f"Installing g[{module}]",
            "prefix-options": cmdPrefix,
            "logfile": "install",
        })["was_successful"]

    # @override
    def configureInternal(self) -> bool:

        Util.assert_isa(self, BuildSystem_KDECMake)
        module = self.module

        if module.getOption("generate-vscode-project-config"):
            self.generateVSCodeConfig(module)
        else:
            logger_ide_proj.debug("\tGenerating .vscode directory - disabled for this module")

        # Use cmake to create the build directory (sh script return value
        # semantics).
        if self._safe_run_cmake():
            return False

        # handle the linking of compile_commands.json back to source directory if wanted
        # allows stuff like clangd to function out of the box
        if module.getOption("compile-commands-linking"):
            # symlink itself will keep existing files untouched!
            builddir = module.fullpath("build")
            srcdir = module.fullpath("source")
            if os.path.exists(f"{builddir}/compile_commands.json"):
                Util.remake_symlink(f"{builddir}/compile_commands.json", f"{srcdir}/compile_commands.json")
        return True

    def generateVSCodeConfig(self, module: Module) -> bool:
        """
        Generate default config files for VSCode.

        This populates the settings VSCode needs to work with most KDE projects,
        such as C++ support, correct build directory, and LSP / IntelliSense.
        """
        if Debug().pretending():
            logger_ide_proj.pretend("\tWould have generated .vscode directory")
            return False

        projectName = module.name
        buildDir = module.fullpath("build")
        srcDir = module.fullpath("source")
        installDir = module.installationPath()
        libDir = module.getOption("libname")
        configDir = f"{srcDir}/.vscode"

        if os.path.exists(configDir):
            if os.path.isdir(configDir):
                logger_ide_proj.debug("\tGenerating .vscode directory - skipping as it already exists")
            elif os.path.isfile(configDir):
                logger_ide_proj.error("\tGenerating .vscode directory - cannot proceed, file .vscode exists")
            return False
        else:
            logger_ide_proj.debug(f"\tGenerating .vscode directory for {projectName}: {configDir}")

        os.mkdir(configDir)

        baseDir = os.path.dirname(os.path.realpath(sys.modules["__main__"].__file__))
        dataDir = f"{baseDir}/data/vscode"

        # c_cpp_properties.json configures C++, CMake & IntelliSense.
        cCppPropertiesJson = self._readFile(f"{dataDir}/c_cpp_properties.json.in")

        # settings.json configures the paths for CMake, QML, Qt, etc.
        settingsJson = self._readFile(f"{dataDir}/settings.json.in")
        settingsJson = settingsJson.replace("$buildDir", buildDir)
        settingsJson = settingsJson.replace("$installDir", installDir)
        settingsJson = settingsJson.replace("$libDir", libDir)

        # extensions.json recommends extensions to install/enable.
        extensionsJson = self._readFile(f"{dataDir}/extensions.json.in")

        # launch.json configures the run with debugger functionality.
        launchJson = self._readFile(f"{dataDir}/launch.json.in")

        self._writeToFile(f"{configDir}/c_cpp_properties.json", cCppPropertiesJson)
        self._writeToFile(f"{configDir}/settings.json", settingsJson)
        self._writeToFile(f"{configDir}/extensions.json", extensionsJson)
        self._writeToFile(f"{configDir}/launch.json", launchJson)

        return True

    @staticmethod
    def _readFile(file_path: str) -> str:
        """
        Reads the contents of a file.

        Parameters:
            file_path: The path to the file to read.

        Returns:
             The contents of the file as a string.
        """

        content = ""  # Avoid lefting content uninitialized. We still need to return empty string in case file could not be opened.
        try:
            with open(file_path, "r") as file:
                content = file.read()
        except IOError as e:
            logger_buildsystem.warning(f"\tCouldn't open {file_path}: {e}")
        return content

    @staticmethod
    def _writeToFile(file_path: str, content: str) -> None:
        """
        Writes content to a file.

        Parameters:
            file_path: The path to the file to write to.
            content: The content to write to the file.
        """
        try:
            with open(file_path, "w") as file:
                file.write(content)
        except IOError as e:
            logger_buildsystem.warning(f"\tCouldn't write to {file_path}: {e}")

    # @override
    def buildInternal(self, optionsName=None) -> dict:
        """
        Return value style: dict to build results object (see :meth:`BuildSystem.safe_make`)
        """
        generator = self.cmakeGenerator()
        defaultOptionsName = BuildSystem_KDECMake.GENERATOR_MAP[generator]["optionsName"]
        if optionsName is None:
            optionsName = f"{defaultOptionsName}"
        return super().buildInternal(optionsName)

    ### Internal package functions.

    def _safe_run_cmake(self) -> int:
        """
        Function to run CMake to create the build directory for a module.
        CMake is not actually run if pretend mode is enabled.

        Returns:
            The shell return value as returned by log_command().  i.e.
            0 for success, non-zero for failure.
        """
        module = self.module
        generator = self.cmakeGenerator()
        toolchain = self.cmakeToolchain()
        srcdir = module.fullpath("source")
        commands = Util.split_quoted_on_whitespace(module.getOption("cmake-options"))

        # grep out empty fields
        commands = [command for command in commands if not re.match(r"^\s*$", command)]
        commands = self._stripGeneratorFromCMakeOptions(commands)
        commands = self._stripToolchainFromCMakeOptions(commands)

        if toolchain != "":
            commands.insert(0, f"-DCMAKE_TOOLCHAIN_FILE={toolchain}")

        # generate a compile_commands.json if requested for e.g. clangd tooling
        if module.getOption("compile-commands-export"):
            commands.insert(0, "-DCMAKE_EXPORT_COMPILE_COMMANDS:BOOL=ON")

        # Add -DBUILD_foo=OFF options for the directories in do-not-compile.
        # This will only work if the CMakeLists.txt file uses macro_optional_add_subdirectory()
        masked_directories = module.getOption("do-not-compile").split(" ")
        masked_directories = [el for el in masked_directories if el != ""]  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it.
        for directory in masked_directories:
            commands.append(f"-DBUILD_{directory}=OFF")

        # Get the user's CXXFLAGS, use them if specified and not already given
        # on the command line.
        cxxflags = module.getOption("cxxflags")
        if cxxflags and not [command for command in commands if re.match(r"^-DCMAKE_CXX_FLAGS(:\w+)?=", command)]:
            commands.append(f"-DCMAKE_CXX_FLAGS:STRING={cxxflags}")

        installdir = module.installationPath()

        commands.append(f"-DCMAKE_INSTALL_PREFIX={installdir}")

        # Add custom Qt to the installdir (but don't overwrite a user-set install-dir)
        qt_installdir = module.getOption("qt-install-dir")
        if qt_installdir and qt_installdir != installdir and not [command for command in commands if re.match(r"^\s*-DCMAKE_PREFIX_PATH", command)]:
            commands.append(f"-DCMAKE_PREFIX_PATH={qt_installdir}")

        if module.getOption("run-tests") and [command for command in commands if not re.match(r"^\s*-DBUILD_TESTING(:BOOL)?=(ON|TRUE|1)\s*$", command)]:
            logger_buildsystem.debug("Enabling tests")
            commands.append("-DBUILD_TESTING:BOOL=ON")

        if module.getOption("run-tests") == "upload":
            logger_buildsystem.debug("Enabling upload of test results")
            commands.append("-DBUILD_experimental:BOOL=ON")

        for item in reversed(["cmake", "-B", ".", "-S", srcdir, "-G", generator]):
            commands.insert(0, item)  # Add to beginning of list.

        old_options = module.getPersistentOption("last-cmake-options") or ""
        builddir = module.fullpath("build")

        if old_options != Util.get_list_digest(commands) or module.getOption("reconfigure") or \
                not os.path.exists(f"{builddir}/CMakeCache.txt"):  # File should exist only on successful cmake run
            logger_buildsystem.info(f"\tRunning g[cmake] targeting b[{generator}]...")

            # Remove any stray CMakeCache.txt
            if os.path.exists(f"{srcdir}/CMakeCache.txt"):
                Util.safe_unlink(f"{srcdir}/CMakeCache.txt")
            if os.path.exists(f"{builddir}/CMakeCache.txt"):
                Util.safe_unlink(f"{builddir}/CMakeCache.txt")

            module.setPersistentOption("last-cmake-options", Util.get_list_digest(commands))

            cmd = Util_LoggedSubprocess().module(module).log_to("cmake").chdir_to(builddir).set_command(commands)

            reading_optional_packages_not_found = False
            optional_packages_not_found = []

            def on_child_output(line):
                nonlocal reading_optional_packages_not_found
                nonlocal optional_packages_not_found
                if line == "-- The following OPTIONAL packages have not been found:":
                    reading_optional_packages_not_found = True
                    return

                # Example output from cmake:
                #
                # -- The following OPTIONAL packages have not been found:
                #
                #  * packagekitqt6 (required version >= 1.0.1), Library that exposes PackageKit resources, <https://www.freedesktop.org/software/PackageKit/>
                #    Required to build the PackageKit backend
                #  * SeleniumWebDriverATSPI, Server component for selenium tests using Linux accessibility infrastructure, <https://invent.kde.org/sdk/selenium-webdriver-at-spi>
                #    Needed for GUI tests
                #  * Snapd, Library that exposes Snapd, <https://www.snapcraft.io>
                #    Required to build the Snap backend
                #
                # -- Found clang-format version 17

                # Another example (without comma at the end of name of package):
                # -- The following OPTIONAL packages have not been found:
                #
                #  * Qt6QmlCompilerPlusPrivate
                #
                # -- Found clang-format version 17

                if reading_optional_packages_not_found:
                    if not line.startswith("-- "):
                        if line.startswith(" * "):
                            match = re.search(r"^ \* (.*?),", line)
                            if match:
                                cmake_package = match.group(1)
                            else:
                                cmake_package = line.removeprefix(" * ")
                            optional_packages_not_found.append(cmake_package)
                    else:
                        reading_optional_packages_not_found = False

            cmd.on({"child_output": on_child_output})

            # await_result, not await_exitcode, to match return semantic
            result = Util.await_result(cmd.start())

            if optional_packages_not_found:
                logger_buildsystem.warning("\t  Some optional dependencies were not found:")
                for package in optional_packages_not_found:
                    logger_buildsystem.warning(f"\t    {package}")
                module.addPostBuildMessage("Some optional dependencies were not found: " + ", ".join(optional_packages_not_found))
            return result
        # Skip cmake run
        return 0
