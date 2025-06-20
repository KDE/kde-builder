# SPDX-FileCopyrightText: 2023 Kristen McWilliam <kmcwilliampublic@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from .debug import Debug
from .debug import KBLogger
from .util.textwrap_mod import textwrap

if TYPE_CHECKING:
    from module.module import Module

logger_ide_proj = KBLogger.getLogger("ide_project_configs")


class IdeProjectConfigGenerator:
    """
    Class responsible for creating IDE-specific files in source directories of modules.
    """

    def __init__(self, module: Module, cmake_opts: list[str]):
        self.module = module
        self.build_opts = module.build_system().get_build_options()
        self.cmake_opts = cmake_opts

    def _generate_vs_code_config(self) -> bool:
        """
        Generate default config files for VSCode.

        This populates the settings VSCode needs to work with most KDE projects,
        such as C++ support, correct build directory, and LSP / IntelliSense.
        """
        if Debug().pretending():
            logger_ide_proj.debug("\tWould have generated .vscode directory")
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

        cmake_opts = self.cmake_opts[5:]  # The first 5 elements are ["cmake", "-B", ".", "-S", srcdir], we are not interested in them
        settings_json = settings_json.replace("%{generator}", cmake_opts[1])

        configure_settings_str = ""
        for cmake_opt in cmake_opts[2:]:  # The first 2 elements are ["-G", generator]
            opt, val = cmake_opt.split("=", maxsplit=1)
            opt = opt.removeprefix("-D")
            configure_settings_str += f"        \"{opt}\": \"{val}\",\n"
        configure_settings_str = configure_settings_str.removesuffix(",\n")
        settings_json = settings_json.replace("%{configureSettings}", configure_settings_str)

        cmake_environment_str = ""
        for key, val in module.env.items():
            cmake_environment_str += " " * 8 + f""""{key}": "{val}",\n"""
        cmake_environment_str = cmake_environment_str.removesuffix(",\n")
        settings_json = settings_json.replace("%{environment}", cmake_environment_str)

        build_opts = self.build_opts
        build_args_str = ""
        for build_opt in build_opts:
            build_args_str += f"\"{build_opt}\", "
        build_args_str = build_args_str.removesuffix(", ")
        settings_json = settings_json.replace("%{buildArgs}", build_args_str)

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

    def _generate_clion_config(self) -> bool:
        if Debug().pretending():
            logger_ide_proj.debug("\tWould have generated .idea directory")
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
        cmake_opts = self.cmake_opts[5:]  # The first 5 elements are ["cmake", "-B", ".", "-S", srcdir], we are not interested in them
        cmake_opts = " ".join(cmake_opts)
        build_opts = self.build_opts
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

    def _generate_qtcreator_config(self) -> bool:
        """
        Generate config-helping files for Qt Creator.

        Generates the snippets in ${source-dir}/.qtcreator for manually recreating build/run configuration.
        Currently, CMakeLists.txt.shared configurations import are not supported by Qt Creator.
        See developers documentation for more info.
        """
        if Debug().pretending():
            logger_ide_proj.debug("\tWould have generated .qtcreator directory")
            return False

        module: Module = self.module
        project_name = module.name
        build_dir = module.fullpath("build")
        src_dir = module.fullpath("source")
        config_dir = f"{src_dir}/.qtcreator"

        logger_ide_proj.debug(f"\tGenerating .qtcreator directory for {project_name}: {config_dir}")
        os.makedirs(config_dir, exist_ok=True)

        cmake_opts = self.cmake_opts[7:]  # The first 7 elements are ["cmake", "-B", ".", "-S", srcdir, "-G", generator], we are not interested in them
        cmake_opts = "\n".join(cmake_opts) + "\n"
        self._write_to_file(f"{config_dir}/cmake_Initial_Configuration.txt", cmake_opts)

        configure_and_build_env_str = ""
        for key, val in module.env.items():
            configure_and_build_env_str += f"{key}={val}\n"
        self._write_to_file(f"{config_dir}/cmake_Configure_and_Build_Environment.txt", configure_and_build_env_str)

        prefix_content = self._read_file(build_dir + "/prefix.sh")
        prefix_content = prefix_content.replace("export ", "")
        prefix_content = prefix_content.replace(":$PATH", "")
        prefix_content = prefix_content.replace(":${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}", "")
        prefix_content = prefix_content.replace(":${XDG_CONFIG_DIRS:-/etc/xdg}", "")
        prefix_content = prefix_content.replace(":$QT_PLUGIN_PATH", "")
        prefix_content = prefix_content.replace(":$QML2_IMPORT_PATH", "")
        prefix_content = prefix_content.replace(":$QT_QUICK_CONTROLS_STYLE_PATH", "")
        prefix_content = prefix_content.replace("=", "=+")  # "=+" means prepend, "+=" means append. We prepend.

        run_env_str = ""
        for line in prefix_content.split("\n"):
            if line.startswith("#") or line == "":
                continue
            run_env_str += f"""{line}\n"""
        self._write_to_file(f"{config_dir}/Run_Environment.txt", run_env_str)

        return True

    @staticmethod
    def _read_file(file_path: str) -> str:
        """
        Read the contents of a file.

        Args:
            file_path: The path to the file to read.

        Returns:
             The contents of the file as a string.
        """
        content = ""  # Avoid lefting content uninitialized. We still need to return empty string in case file could not be opened.
        try:
            with open(file_path, "r") as file:
                content = file.read()
        except IOError as e:
            logger_ide_proj.warning(f"\tCouldn't open {file_path}: {e}")
        return content

    @staticmethod
    def _write_to_file(file_path: str, content: str) -> None:
        """
        Write content to a file.

        Args:
            file_path: The path to the file to write to.
            content: The content to write to the file.
        """
        try:
            with open(file_path, "w") as file:
                file.write(content)
        except IOError as e:
            logger_ide_proj.warning(f"\tCouldn't write to {file_path}: {e}")

    def _convert_prefixsh_to_env(self):
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

    def generate_ide_project_configs(self) -> None:
        """
        Trigger generation IDE project configs for all enabled IDEs.
        """
        module = self.module
        if module.get_option("generate-vscode-project-config"):
            self._generate_vs_code_config()
        else:
            logger_ide_proj.debug("\tGenerating .vscode directory - disabled for this project")

        if module.get_option("generate-clion-project-config"):
            self._generate_clion_config()
        else:
            logger_ide_proj.debug("\tGenerating .idea directory - disabled for this project")

        if module.get_option("generate-qtcreator-project-config"):
            self._generate_qtcreator_config()
        else:
            logger_ide_proj.debug("\tGenerating qtcreator configs - disabled for this project")

        if module.get_option("generate-vscode-project-config"):
            self._convert_prefixsh_to_env()
