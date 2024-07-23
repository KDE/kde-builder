# SPDX-FileCopyrightText: 2012, 2013, 2016, 2018, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 Kristen McWilliam <kmcwilliampublic@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os.path
import re
import sys
import textwrap
from typing import TYPE_CHECKING

from .build_system import BuildSystem
from ..build_exception import BuildException
from ..debug import Debug
from ..debug import KBLogger
from ..util.logged_subprocess import UtilLoggedSubprocess
from ..util.util import Util

if TYPE_CHECKING:
    from ..module.module import Module

logger_ide_proj = KBLogger.getLogger("ide_project_configs")
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
        self.cmake_generator = None
        self.cmake_toolchain = None

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

        for maybeToolchain in args:
            accept = 1
            if re.match(r"^-DCMAKE_TOOLCHAIN_FILE=(\S*(\s*\S)*)\s*", maybeToolchain):
                accept = 0
            if accept == 1:
                filtered.append(maybeToolchain)
        return filtered

    @staticmethod
    def _find_toolchain_in_cmake_options(args: list[str]) -> str:
        found = None
        for maybeToolchain in args:
            match = re.match(r"^-DCMAKE_TOOLCHAIN_FILE=(\S*(\s*\S)*)\s*", maybeToolchain)
            if match:
                file = match.group(1) or ""
                if BuildSystemKDECMake._check_toolchain_ok(file):
                    found = maybeToolchain
                    break
            found = maybeToolchain
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
        Returns true if CMake is run with ninja, which supports setting -j
        automatically.
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
            BuildException.croak_internal(f"Unable to determine CMake generator for: {module}")
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
        Called by the module being built before it runs its build/install process. Should
        set up any needed environment variables, build context settings, etc., in preparation
        for the build and install phases.
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
        This should return a list of executable names that must be present to
        even bother attempting to use this build system. An empty list should be
        returned if there's no required programs.
        """
        generator = self.get_cmake_generator()
        required = BuildSystemKDECMake.GENERATOR_MAP[generator]["required_programs"]
        return required

    # @override(check_signature=False)
    def build_commands(self) -> list[str]:
        """
        Returns a list of possible build commands to run, any one of which should
        be supported by the build system.
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
        Re-implementing the one in BuildSystem since in CMake we want to call
        make install/fast, so it only installs rather than building + installing
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

        # Note, that this must be after _safe_run_cmake(), because we need the list of cmake generate options that were used there.
        if module.get_option("generate-vscode-project-config"):
            self.generate_vs_code_config()
        else:
            logger_ide_proj.debug("\tGenerating .vscode directory - disabled for this module")

        # Note, that this must be after _safe_run_cmake(), because we need the list of cmake generate options that were used there.
        if module.get_option("generate-clion-project-config"):
            self.generate_clion_config()
        else:
            logger_ide_proj.debug("\tGenerating .idea directory - disabled for this module")

        if module.get_option("generate-vscode-project-config"):
            self.convert_prefixsh_to_env()

        # handle the linking of compile_commands.json back to source directory if wanted
        # allows stuff like clangd to function out of the box
        if module.get_option("compile-commands-linking"):
            # symlink itself will keep existing files untouched!
            builddir = module.fullpath("build")
            srcdir = module.fullpath("source")
            if os.path.exists(f"{builddir}/compile_commands.json"):
                Util.remake_symlink(f"{builddir}/compile_commands.json", f"{srcdir}/compile_commands.json")
        return True

    def generate_vs_code_config(self) -> bool:
        """
        Generate default config files for VSCode.

        This populates the settings VSCode needs to work with most KDE projects,
        such as C++ support, correct build directory, and LSP / IntelliSense.
        """
        if Debug().pretending():
            logger_ide_proj.pretend("\tWould have generated .vscode directory")
            return False

        module: Module = self.module
        project_name = module.name
        build_dir = module.fullpath("build")
        src_dir = module.fullpath("source")
        install_dir = module.installation_path()
        config_dir = f"{src_dir}/.vscode"

        if os.path.exists(config_dir):
            if os.path.isdir(config_dir):
                logger_ide_proj.debug("\tGenerating .vscode directory - skipping as it already exists")
            elif os.path.isfile(config_dir):
                logger_ide_proj.error("\tGenerating .vscode directory - cannot proceed, file .vscode exists")
            return False
        else:
            logger_ide_proj.debug(f"\tGenerating .vscode directory for {project_name}: {config_dir}")

        os.mkdir(config_dir)

        base_dir = os.path.dirname(os.path.realpath(sys.modules["__main__"].__file__))
        data_dir = f"{base_dir}/data/vscode"

        # c_cpp_properties.json configures C++, CMake & IntelliSense.
        c_cpp_properties_json = self._read_file(f"{data_dir}/c_cpp_properties.json.in")

        # settings.json configures the paths for CMake, QML, Qt, etc.
        settings_json = self._read_file(f"{data_dir}/settings.json.in")

        settings_json = settings_json.replace("%{build_dir}", build_dir)

        cmake_opts = module.cmake_opts[5:]  # The first 5 elements are ["cmake", "-B", ".", "-S", srcdir], we are not interested in them
        settings_json = settings_json.replace("%{generator}", cmake_opts[1])

        configureSettings_str = ""
        for cmake_opt in cmake_opts[2:]:  # The first 2 elements are ["-G", generator]
            opt, val = cmake_opt.split("=", maxsplit=1)
            opt = opt.removeprefix("-D")
            configureSettings_str += f"        \"{opt}\": \"{val}\",\n"
        configureSettings_str = configureSettings_str.removesuffix(",\n")
        settings_json = settings_json.replace("%{configureSettings}", configureSettings_str)

        cmake_environment_str = ""
        for key, val in module.env.items():
            cmake_environment_str += " " * 8 + f""""{key}": "{val}",\n"""
        cmake_environment_str = cmake_environment_str.removesuffix(",\n")
        settings_json = settings_json.replace("%{environment}", cmake_environment_str)

        build_opts = self.get_build_options()
        buildArgs_str = ""
        for build_opt in build_opts:
            buildArgs_str += f"\"{build_opt}\", "
        buildArgs_str = buildArgs_str.removesuffix(", ")
        settings_json = settings_json.replace("%{buildArgs}", buildArgs_str)

        settings_json = settings_json.replace("%{install_dir}", install_dir)

        # extensions.json recommends extensions to install/enable.
        extensions_json = self._read_file(f"{data_dir}/extensions.json.in")

        # launch.json configures the run with debugger functionality.
        launch_json = self._read_file(f"{data_dir}/launch.json.in")
        program = install_dir + "/bin/" + module.name
        launch_json = launch_json.replace("%{program}", program)
        launch_json = launch_json.replace("%{install_dir}", install_dir)

        prefix_content = self._read_file(build_dir + "/prefix.sh")
        prefix_content = prefix_content.replace("$PATH", "${env:PATH}")
        prefix_content = prefix_content.replace("${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}", "${env:XDG_DATA_DIRS}:/usr/local/share/:/usr/share/")
        prefix_content = prefix_content.replace("${XDG_CONFIG_DIRS:-/etc/xdg}", "${env:XDG_CONFIG_DIRS}:/etc/xdg")
        prefix_content = prefix_content.replace("$QT_PLUGIN_PATH", "${env:QT_PLUGIN_PATH}")
        prefix_content = prefix_content.replace("$QML2_IMPORT_PATH", "${env:QML2_IMPORT_PATH}")
        prefix_content = prefix_content.replace("$QT_QUICK_CONTROLS_STYLE_PATH", "${env:QT_QUICK_CONTROLS_STYLE_PATH}")

        launch_env_entries_str = ""
        for line in prefix_content.split("\n"):
            if line.startswith("#") or line == "":
                continue
            line = line.removeprefix("export ")
            var, val = line.split("=", maxsplit=1)
            launch_env_entries_str += " " * 16 + "{\n" + " " * 20 + f""""name": "{var}",\n""" + " " * 20 + f""""value": "{val}"\n""" + " " * 16 + "},\n"
        launch_env_entries_str = launch_env_entries_str.removesuffix(",\n")

        launch_json = launch_json.replace("%{launch_env_entries}", launch_env_entries_str)

        extra_run_env = module.get_option("source-when-start-program")
        # Currently, sourcing a _script_ is not possible, see https://github.com/microsoft/vscode-cpptools/issues/9329 feature request.
        # For now, will just use an envFile, hoping user is aware of this behavior in vs code, and used the env file in the value of source-when-start-program option.
        launch_json = launch_json.replace("%{envFile}", extra_run_env)

        # tasks.json contains tasks to be easily / automatically run.
        tasks_json = self._read_file(f"{data_dir}/tasks.json.in")

        self._write_to_file(f"{config_dir}/c_cpp_properties.json", c_cpp_properties_json)
        self._write_to_file(f"{config_dir}/settings.json", settings_json)
        self._write_to_file(f"{config_dir}/extensions.json", extensions_json)
        self._write_to_file(f"{config_dir}/launch.json", launch_json)
        self._write_to_file(f"{config_dir}/tasks.json", tasks_json)

        return True

    def generate_clion_config(self) -> bool:
        if Debug().pretending():
            logger_ide_proj.pretend("\tWould have generated .idea directory")
            return False

        branch_group = self.module.context.get_option("branch-group")
        project_name = self.module.name
        if branch_group != "kf6-qt6":
            project_name += f" ({branch_group})"
        src_dir = self.module.fullpath("source")
        config_dir = f"{src_dir}/.idea"

        if os.path.exists(config_dir):
            if os.path.isdir(config_dir):
                logger_ide_proj.debug("\tGenerating .idea directory - skipping as it already exists")
            elif os.path.isfile(config_dir):
                logger_ide_proj.error("\tGenerating .idea directory - cannot proceed, file .idea exists")
            return False
        else:
            logger_ide_proj.debug(f"\tGenerating .idea directory for {project_name}: {config_dir}")

        os.mkdir(config_dir)
        os.mkdir(config_dir + "/runConfigurations")

        self._write_to_file(f"{config_dir}/.name", project_name + "\n")

        module: Module = self.module
        build_dir = module.fullpath("build")
        cmake_opts = module.cmake_opts[5:]  # The first 5 elements are ["cmake", "-B", ".", "-S", srcdir], we are not interested in them
        cmake_opts = " ".join(cmake_opts)
        build_opts = self.get_build_options()
        build_opts = " ".join(build_opts)

        base_dir = os.path.dirname(os.path.realpath(sys.modules["__main__"].__file__))
        data_dir = f"{base_dir}/data/clion"

        cmake_xml = self._read_file(f"{data_dir}/cmake.xml.in")
        cmake_xml = cmake_xml.replace("%{GENERATION_DIR}", build_dir)
        cmake_xml = cmake_xml.replace("%{GENERATION_OPTIONS}", cmake_opts)
        cmake_xml = cmake_xml.replace("%{BUILD_OPTIONS}", build_opts)
        env_entries_str = ""
        for key, val in module.env.items():
            env_entries_str += " " * 12 + f"""<env name="{key}" value="{val}" />\n"""
        env_entries_str = env_entries_str.removesuffix("\n")
        cmake_xml = cmake_xml.replace("%{env_entries}", env_entries_str)

        self._write_to_file(f"{config_dir}/cmake.xml", cmake_xml)

        run_conf_xml = self._read_file(f"{data_dir}/KDE_Builder_run_debug_configuration.xml.in")
        extra_run_env = module.get_option("source-when-start-program")
        run_conf_xml = run_conf_xml.replace("%{ENVFILE}", extra_run_env)
        install_dir = module.installation_path()
        executable = install_dir + "/bin/" + module.name
        run_conf_xml = run_conf_xml.replace("%{RUN_PATH}", executable)

        # Currently, unlike in PyCharm run configurations, it CLion run configurations it is not possible to specify several env files.
        # And because we need to keep user's env from source-when-start-program file in a file (so user can easily edit it),
        # we will convert the prefix.sh into the individual variables.

        prefix_content = self._read_file(build_dir + "/prefix.sh")
        # Their format is very weird: it needs to use trailing "$" in variable names, and does not support expansions.
        # So, instead of expansion, will just use variables as is.
        prefix_content = prefix_content.replace("$PATH", "$PATH$")
        prefix_content = prefix_content.replace("${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}", "$XDG_DATA_DIRS$:/usr/local/share/:/usr/share/")
        prefix_content = prefix_content.replace("${XDG_CONFIG_DIRS:-/etc/xdg}", "$XDG_CONFIG_DIRS$:/etc/xdg")
        prefix_content = prefix_content.replace("$QT_PLUGIN_PATH", "$QT_PLUGIN_PATH$")
        prefix_content = prefix_content.replace("$QML2_IMPORT_PATH", "$QML2_IMPORT_PATH$")
        prefix_content = prefix_content.replace("$QT_QUICK_CONTROLS_STYLE_PATH", "$QT_QUICK_CONTROLS_STYLE_PATH$")

        env_entries_str = ""
        for line in prefix_content.split("\n"):
            if line.startswith("#") or line == "":
                continue
            line = line.removeprefix("export ")
            var, val = line.split("=", maxsplit=1)
            env_entries_str += " " * 6 + f"""<env name="{var}" value="{val}" />\n"""
        env_entries_str = env_entries_str.removesuffix("\n")

        run_conf_xml = run_conf_xml.replace("%{env_entries}", env_entries_str)
        self._write_to_file(f"{config_dir}/runConfigurations/KDE_Builder_run_debug_configuration.xml", run_conf_xml)

        misc_xml = self._read_file(f"{data_dir}/misc.xml")
        self._write_to_file(f"{config_dir}/misc.xml", misc_xml)

        return True

    @staticmethod
    def _read_file(file_path: str) -> str:
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
    def _write_to_file(file_path: str, content: str) -> None:
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

    def convert_prefixsh_to_env(self):
        """
        Export a standard environment variables key/value file, for tools that can't make use of the prefix.sh.
        They are essentially the same, but without the "export" keywords.

        This is needed for things like the VS Code CMake extension.
        """
        build_dir = self.module.fullpath("build")
        if os.path.exists(build_dir + "/prefix.sh"):
            env_content = textwrap.dedent("""\
            # This file is .env type, for tools that can't make use of the prefix.sh
            # kate: syntax bash;
            """)
            with open(build_dir + "/prefix.sh", "r") as f:
                for line in f:
                    if line.startswith("#") or line == "\n":
                        continue
                    line = line.removeprefix("export ")
                    env_content += line
            with open(build_dir + "/prefix.env", "w") as f:
                f.write(env_content)

    # @override
    def build_options_name(self) -> str:
        generator = self.get_cmake_generator()
        options_name = BuildSystemKDECMake.GENERATOR_MAP[generator]["options_name"]
        return options_name

    def _safe_run_cmake(self) -> int:
        """
        Function to run CMake to create the build directory for a module.
        CMake is not actually run if pretend mode is enabled.

        Returns:
            The shell return value as returned by log_command(). i.e.
            0 for success, non-zero for failure.
        """
        module = self.module
        generator = self.get_cmake_generator()
        toolchain = self.get_cmake_toolchain()
        srcdir = module.fullpath("source")
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

        if module.get_option("run-tests") and [command for command in commands if not re.match(r"^\s*-DBUILD_TESTING(:BOOL)?=(ON|TRUE|1)\s*$", command)]:
            logger_buildsystem.debug("Enabling tests")
            commands.append("-DBUILD_TESTING:BOOL=ON")

        commands = ["cmake", "-B", ".", "-S", srcdir, "-G", generator] + commands  # Add to beginning of list.
        self.module.cmake_opts = commands  # Remember them for later, if user wants to generate clion project configs

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
