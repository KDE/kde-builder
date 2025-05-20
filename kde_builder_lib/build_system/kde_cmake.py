# SPDX-FileCopyrightText: 2012, 2013, 2016, 2018, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os.path
import re
import sys

from .build_system import BuildSystem
from ..kb_exception import ProgramError
from ..debug import KBLogger
from ..ide_project_config_generator import IdeProjectConfigGenerator
from ..util.logged_subprocess import UtilLoggedSubprocess
from ..util.util import Util

logger_buildsystem = KBLogger.getLogger("build-system")


class BuildSystemKDECMake(BuildSystem):
    """
    Class responsible for building CMake-based modules, with special support for KDE modules.
    """

    BASE_GENERATOR_MAP = {
        "Ninja": {
            "options_name": "ninja-options",
            "install_target": "install",
            "required_programs": ["ninja", "cmake"],
            "build_commands": ["ninja"]
        },
        "Unix Makefiles": {
            "options_name": "make-options",
            "install_target": "install/fast",
            "required_programs": ["cmake"],
            # Non Linux systems can sometimes fail to build when GNU Make would work,
            # so prefer GNU Make if present, otherwise try regular make.
            "build_commands": ["gmake", "make"]
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
        self.cmake_generator: str | None = None
        self.cmake_toolchain: str | None = None

    @staticmethod
    def _check_generator_is_whitelisted(generator: str) -> bool:
        return generator in BuildSystemKDECMake.GENERATOR_MAP

    @staticmethod
    def _strip_generator_from_cmake_options(args: list[str]) -> list[str]:
        next_should_be_generator = 0
        filtered = []
        for i in args:
            accept = 1
            if next_should_be_generator:
                next_should_be_generator = 0
                accept = 0
            else:
                maybe_generator = i
                match = re.match(r"^-G(\S*(\s*\S)*)\s*", maybe_generator)
                if match:
                    generator = match.group(1) or ""
                    if generator == "":
                        next_should_be_generator = 1
                    accept = 0
            if accept == 1:
                filtered.append(i)
        return filtered

    @staticmethod
    def _find_generator_in_c_make_options(args: list[str]) -> str:
        next_should_be_generator = 0
        filtered = []
        for i in args:
            accept = 0
            if next_should_be_generator:
                next_should_be_generator = 0
                accept = 1
            else:
                maybe_generator = i
                match = re.match(r"^-G(\S*(\s*\S)*)\s*", maybe_generator)
                if match:
                    generator = match.group(1) or ""
                    if generator != "":
                        accept = 1
                    else:
                        next_should_be_generator = 1
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
    def _check_toolchain_ok(toolchain: str) -> bool:
        return toolchain != "" and os.path.isfile(toolchain) and os.access(toolchain, os.R_OK)

    @staticmethod
    def _strip_toolchain_from_cmake_options(args: list[str]) -> list[str]:
        filtered = []

        for maybe_toolchain in args:
            accept = 1
            if re.match(r"^-DCMAKE_TOOLCHAIN_FILE=(\S*(\s*\S)*)\s*", maybe_toolchain):
                accept = 0
            if accept == 1:
                filtered.append(maybe_toolchain)
        return filtered

    @staticmethod
    def _find_toolchain_in_cmake_options(args: list[str]) -> str:
        found = None
        for maybe_toolchain in args:
            match = re.match(r"^-DCMAKE_TOOLCHAIN_FILE=(\S*(\s*\S)*)\s*", maybe_toolchain)
            if match:
                file = match.group(1) or ""
                if BuildSystemKDECMake._check_toolchain_ok(file):
                    found = maybe_toolchain
                    break
            found = maybe_toolchain
            break

        if found:
            match = re.match(r"^-DCMAKE_TOOLCHAIN_FILE=(\S*(\s*\S)*)\s*", found)
            if match:
                found = match.group(1) or ""
                if BuildSystemKDECMake._check_toolchain_ok(found):
                    return found
        return ""

    def _determine_cmake_toolchain(self) -> str:
        module = self.module
        cmake_options = Util.split_quoted_on_whitespace(module.get_option("cmake-options"))

        toolchain = next((toolchain for toolchain in (self._find_toolchain_in_cmake_options(cmake_options), module.get_option("cmake-toolchain")) if self._check_toolchain_ok(toolchain)), None)
        return toolchain or ""

    def get_cmake_toolchain(self) -> str:
        if not self.cmake_toolchain:
            self.cmake_toolchain = self._determine_cmake_toolchain()
        return self.cmake_toolchain

    # @override
    def has_toolchain(self) -> bool:
        return self.get_cmake_toolchain() != ""

    # @override(check_signature=False)
    def supports_auto_parallelism(self) -> bool:
        """
        Return true if CMake is run with ninja, which supports setting -j automatically.
        """
        generator = self.get_cmake_generator()
        generator_opts = BuildSystemKDECMake.GENERATOR_MAP[generator]["options_name"]

        if not generator_opts:
            return False
        if generator_opts == "ninja-options":
            return True
        return False

    def _determine_cmake_generator(self) -> str:
        module = self.module
        cmake_options = Util.split_quoted_on_whitespace(module.get_option("cmake-options"))
        generator = next((gen for gen in (self._find_generator_in_c_make_options(cmake_options), module.get_option("cmake-generator"), "Unix Makefiles") if self._check_generator_is_whitelisted(gen)), None)

        if not generator:
            raise ProgramError(f"Unable to determine CMake generator for: {module}")
        return generator

    def get_cmake_generator(self) -> str:
        if self.cmake_generator is None:
            self.cmake_generator = self._determine_cmake_generator()
        return self.cmake_generator

    @staticmethod
    # @override
    def needs_installed() -> bool:
        return True

    @staticmethod
    # @override
    def name() -> str:
        return "KDE CMake"

    # @override
    def prepare_module_build_environment(self) -> None:
        """
        Set up any needed environment variables, build context settings, etc., in preparation for the build and install phases.

        Called by the module being built before it runs its build/install process.
        """
        module = self.module
        prefix = self.module.installation_path()

        # Suppress injecting qt-install-dir/install-dir related environment variables if a toolchain is also set
        # Let the toolchain files/definitions take care of themselves.
        if self.has_toolchain():
            return

        # Avoid moving /usr up in env vars
        if prefix != "/usr":
            # Find the normal CMake "config" mode files for find_package()
            module.prepend_environment_value("CMAKE_PREFIX_PATH", prefix)
            # Try to ensure that older "module" mode find_package() calls also point to right directory
            module.prepend_environment_value("CMAKE_MODULE_PATH", f"{prefix}/lib64/cmake:{prefix}/lib/cmake")
            # Set the plugin path correctly for configuration-time access e.g. by Extra CMake Modules
            module.prepend_environment_value("QT_PLUGIN_PATH", f"{prefix}/lib64/plugins:{prefix}/lib/plugins")
            module.prepend_environment_value("XDG_DATA_DIRS", f"{prefix}/share")

        qt_installdir = module.get_option("qt-install-dir")
        if qt_installdir and qt_installdir != prefix:
            # Ensure we can find Qt5's own CMake modules
            module.prepend_environment_value("CMAKE_PREFIX_PATH", qt_installdir)
            module.prepend_environment_value("CMAKE_MODULE_PATH", f"{qt_installdir}/lib/cmake")

    # @override(check_signature=False)
    def required_programs(self) -> list[str]:
        """
        Return a list of executable names that must be present to even bother attempting to use this build system.

        An empty list should be returned if there's no required programs.
        """
        generator = self.get_cmake_generator()
        required = BuildSystemKDECMake.GENERATOR_MAP[generator]["required_programs"]
        return required

    # @override(check_signature=False)
    def build_commands(self) -> list[str]:
        """
        Return a list of possible build commands to run, any one of which should be supported by the build system.
        """
        generator = self.get_cmake_generator()
        progs = BuildSystemKDECMake.GENERATOR_MAP[generator]["build_commands"]
        return progs

    @staticmethod
    # @override
    def configured_module_file_name() -> str:
        return "cmake_install.cmake"

    # @override
    def run_testsuite(self) -> bool:
        module = self.module

        # Note that we do not run safe_make, which should really be called
        # safe_compile at this point.

        # Step 1: Ensure the tests are built, oh wait we already did that when we ran
        # CMake :)

        logger_buildsystem.info("\tRunning test suite...")

        # Step 2: Run the tests.
        build_command = self.default_build_command()
        num_tests = "Some"  # overwritten by a specific number, hopefully

        cmd = UtilLoggedSubprocess().module(module).log_to("test-results").set_command([build_command, "test"])

        def on_child_output(line):
            match = re.match(r"([0-9]+) tests failed out of", line)
            if match:
                nonlocal num_tests
                num_tests = match.group(1)

        cmd.on({"child_output": on_child_output})  # pl2py: this is in testsuite

        result = Util.good_exitcode(cmd.start())

        if not result:
            log_dir = module.get_log_dir()
            logger_buildsystem.warning(f"\t{num_tests} tests failed for y[{module}], consult {log_dir}/test-results.log for info")
        else:
            logger_buildsystem.info("\tAll tests ran successfully.")
        return result

    # @override
    def install_internal(self, cmd_prefix: list[str]) -> bool:
        """
        Re-implementing the one in BuildSystem since in CMake we want to call make install/fast, so it only installs rather than building + installing.
        """
        module = self.module
        generator = self.get_cmake_generator()
        target = BuildSystemKDECMake.GENERATOR_MAP[generator]["install_target"]

        if module.get_option("custom-build-command"):
            target = "install"

        return self.safe_make({
            "target": target,
            "message": f"Installing g[{module}]",
            "prefix-options": cmd_prefix,
            "logfile": "install",
        })["was_successful"]

    # @override
    def configure_internal(self) -> bool:
        module = self.module

        # Use cmake to create the build directory
        if self._safe_run_cmake():
            return False

        # handle the linking of compile_commands.json back to source directory if wanted
        # allows stuff like clangd to function out of the box
        if module.get_option("compile-commands-linking"):
            # symlink itself will keep existing files untouched!
            builddir = module.fullpath("build")
            srcdir = module.fullpath("source")
            if os.path.exists(f"{builddir}/compile_commands.json"):
                Util.remake_symlink(f"{builddir}/compile_commands.json", f"{srcdir}/compile_commands.json")
        return True

    # @override
    def build_options_name(self) -> str:
        generator = self.get_cmake_generator()
        options_name = BuildSystemKDECMake.GENERATOR_MAP[generator]["options_name"]
        return options_name

    def get_final_cmake_options(self) -> list[str]:
        """
        Return the cmake options that will finally be used when running cmake.

        "Final" means that it will contain all extra options that kde-builder inserts automatically, in addition to those options that are
        read from user's config.
        """
        module = self.module
        toolchain = self.get_cmake_toolchain()

        commands = Util.split_quoted_on_whitespace(module.get_option("cmake-options"))

        # grep out empty fields
        commands = [command for command in commands if not re.match(r"^\s*$", command)]
        commands = self._strip_generator_from_cmake_options(commands)
        commands = self._strip_toolchain_from_cmake_options(commands)

        if toolchain != "":
            commands.insert(0, f"-DCMAKE_TOOLCHAIN_FILE={toolchain}")

        # generate a compile_commands.json if requested for e.g. clangd tooling
        if module.get_option("compile-commands-export"):
            commands.insert(0, "-DCMAKE_EXPORT_COMPILE_COMMANDS:BOOL=ON")

        # Add -DBUILD_foo=OFF options for the directories in do-not-compile.
        # This will only work if the CMakeLists.txt file uses macro_optional_add_subdirectory()
        masked_directories = module.get_option("do-not-compile").split(" ")
        masked_directories = [el for el in masked_directories if el != ""]  # pl2py: split in perl makes 0 elements for empty string. In python split leaves one empty element. Remove it.
        for directory in masked_directories:
            commands.append(f"-DBUILD_{directory}=OFF")

        # Get the user's CXXFLAGS, use them if specified and not already given
        # on the command line.
        cxxflags = module.get_option("cxxflags")
        if cxxflags and not [command for command in commands if re.match(r"^-DCMAKE_CXX_FLAGS(:\w+)?=", command)]:
            commands.append(f"-DCMAKE_CXX_FLAGS:STRING={cxxflags}")

        installdir = module.installation_path()

        commands.append(f"-DCMAKE_INSTALL_PREFIX={installdir}")

        # Add custom Qt to the installdir (but don't overwrite a user-set install-dir)
        qt_installdir = module.get_option("qt-install-dir")
        if qt_installdir and qt_installdir != installdir and not [command for command in commands if re.match(r"^\s*-DCMAKE_PREFIX_PATH", command)]:
            commands.append(f"-DCMAKE_PREFIX_PATH={qt_installdir}")

        if module.get_option("run-tests"):
            found_build_testing_index = -1
            for index, command in enumerate(commands):
                if not re.match(r"^\s*-DBUILD_TESTING(:BOOL)?=", command):
                    continue
                found_build_testing_index = index
                # The last occurrence of variable takes precedence. So continue iterations over the rest of the list.

            if found_build_testing_index == -1:
                logger_buildsystem.debug("\tAdding BUILD_TESTING variable with ON value.")
                commands.append("-DBUILD_TESTING:BOOL=ON")
            else:
                logger_buildsystem.debug("\tOverriding BUILD_TESTING variable with ON value.")
                commands[found_build_testing_index] = "-DBUILD_TESTING:BOOL=ON"

        if sys.prefix != sys.base_prefix:
            # We are in virtual environment.
            # Some projects require python modules (for example, breeze-gtk requires python-cairo).
            # We will append (if missing) cmake options so that those python modules are searched in system environment rather than in virtual environment.
            # See https://cmake.org/cmake/help/latest/module/FindPython3.html for options description.
            # The path of virtual environment was removed in prepend_environment_value().
            if not [command for command in commands if re.match(r"^-DPython3_FIND_VIRTUALENV(:\w+)?=", command)]:
                logger_buildsystem.debug("\tAdding -DPython3_FIND_VIRTUALENV cmake option, because we are in virtual environment.")
                commands.append(f"-DPython3_FIND_VIRTUALENV=STANDARD")
            if not [command for command in commands if re.match(r"^-DPython3_FIND_UNVERSIONED_NAMES(:\w+)?=", command)]:
                logger_buildsystem.debug("\tAdding -DPython3_FIND_UNVERSIONED_NAMES cmake option, because we are in virtual environment.")
                commands.append(f"-DPython3_FIND_UNVERSIONED_NAMES=FIRST")

        return commands

    def _safe_run_cmake(self) -> int:
        """
        Run CMake to create the build directory for a module.

        CMake is not actually run if pretend mode is enabled.

        Returns:
            The shell return value as returned by log_command(). i.e.
            0 for success, non-zero for failure.
        """
        module = self.module
        generator = self.get_cmake_generator()
        srcdir = module.fullpath("source")
        commands = self.get_final_cmake_options()

        commands = ["cmake", "-B", ".", "-S", srcdir, "-G", generator] + commands  # Add to beginning of list.

        # Generate IDE configs now, so if cmake configure fails, user already have them, and could then debug cmake script in their IDE.
        IdeProjectConfigGenerator(module, commands).generate_ide_project_configs()

        old_options = module.get_persistent_option("last-cmake-options") or ""
        builddir = module.fullpath("build")

        if old_options != Util.get_list_digest(commands) or module.get_option("reconfigure") or \
                not os.path.exists(f"{builddir}/CMakeCache.txt"):  # File should exist only on successful cmake run
            logger_buildsystem.info(f"\tRunning g[cmake] targeting b[{generator}]...")

            # Remove any stray CMakeCache.txt
            if os.path.exists(f"{srcdir}/CMakeCache.txt"):
                Util.safe_unlink(f"{srcdir}/CMakeCache.txt")
            if os.path.exists(f"{builddir}/CMakeCache.txt"):
                Util.safe_unlink(f"{builddir}/CMakeCache.txt")

            module.set_persistent_option("last-cmake-options", Util.get_list_digest(commands))

            cmd = UtilLoggedSubprocess().module(module).log_to("cmake").chdir_to(builddir).set_command(commands)

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

            # just a result, not good_exitcode, to match return semantic
            result = cmd.start()

            if optional_packages_not_found:
                logger_buildsystem.warning("\t  Some optional dependencies were not found:")
                for package in optional_packages_not_found:
                    logger_buildsystem.warning(f"\t    {package}")
                module.add_post_build_message("Some optional dependencies were not found: " + ", ".join(optional_packages_not_found))
            return result
        # Skip cmake run
        return 0
