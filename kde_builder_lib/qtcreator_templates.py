# SPDX-FileCopyrightText: 2026 Bogdan Vatra <bogdan.vatra@kdab.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import json
import os
import shutil
import sys

import yaml

from .debug import KBLogger
from .qtcreator_presets import cmake_run_environment
from .qtcreator_presets import cmake_user_presets

logger_qtc_tmpl = KBLogger.getLogger("qtcreator_templates")


class QtCreatorTemplatesInstaller:
    """
    Install the Qt Creator project wizard templates bundled with kde-builder.

    The templates are copied from ``data/qtcreator/wizards/`` into the user's Qt Creator
    configuration directory, under ``templates/wizards/``. Qt Creator's "New Project" dialog
    discovers any ``wizard.json`` placed there on its next start, offering KDE project templates
    (for example, a KDE Frameworks 6 C++/Qt Widgets application) right in the wizard.

    For each template that ships a CMake ``project/`` directory, a ``CMakeUserPresets.json`` is
    generated alongside it so that projects created from the wizard configure, build, install and
    run against the KDE that kde-builder installed (rather than the system KDE). Without this file,
    Qt Creator would configure with a plain kit whose ``CMAKE_PREFIX_PATH`` does not point at the
    kde-builder install prefix, and ``find_package(KF6 ...)`` would fail. The preset mirrors what
    kde-builder generates for already-managed projects (:class:`IdeProjectConfigGenerator`).

    The environment baked into the preset reflects the kde-builder configuration *at install time*,
    so re-run this command after changing ``install-dir`` (or moving the install prefix).

    The templates are installed into ``$XDG_CONFIG_HOME/QtProject/qtcreator`` (i.e.
    ``~/.config/QtProject/qtcreator``), which is where Qt Creator looks for them.
    """

    def __init__(self):
        base_dir = os.path.dirname(os.path.realpath(sys.modules["__main__"].__file__))
        self.source_dir = os.path.join(base_dir, "data", "qtcreator", "wizards")

        xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        settings_path = os.path.join(xdg_config_home, "QtProject", "qtcreator")
        self.dest_dir = os.path.join(settings_path, "templates", "wizards")

        self.libname = self._detect_libname()
        global_opts = self._read_global_config_options()
        self.install_prefix = os.path.expanduser(global_opts.get("install-dir") or "~/kde/usr")
        qt_install_dir = global_opts.get("qt-install-dir")
        self.qt_install_dir = os.path.expanduser(qt_install_dir) if qt_install_dir else ""

    def install(self) -> int:
        """
        Copy every bundled wizard template into the Qt Creator templates directory.

        Returns:
            0 on success, 1 on failure (suitable as a process exit code).
        """
        if not os.path.isdir(self.source_dir):
            logger_qtc_tmpl.error(f"Could not find bundled templates directory: {self.source_dir}")
            return 1

        template_names = sorted(
            entry for entry in os.listdir(self.source_dir)
            if os.path.isdir(os.path.join(self.source_dir, entry))
        )
        if not template_names:
            logger_qtc_tmpl.warning(f"No Qt Creator templates found in {self.source_dir}")
            return 1

        os.makedirs(self.dest_dir, exist_ok=True)

        for name in template_names:
            source = os.path.join(self.source_dir, name)
            destination = os.path.join(self.dest_dir, name)
            # Refresh on each run so the installed copy always matches the bundled one.
            if os.path.exists(destination):
                shutil.rmtree(destination)
            shutil.copytree(source, destination)

            project_dir = os.path.join(destination, "project")
            if os.path.isdir(project_dir):
                self._write_cmake_user_presets(project_dir)

            logger_qtc_tmpl.warning(f" * Installed Qt Creator template {name}")

        logger_qtc_tmpl.warning(f"Installed {len(template_names)} Qt Creator template(s) into {self.dest_dir}")
        logger_qtc_tmpl.warning(f"Projects created from them will build against the KDE in {self.install_prefix}.")
        logger_qtc_tmpl.warning("Restart Qt Creator and find them under \"New Project\" in the KDE category.")
        return 0

    @staticmethod
    def _detect_libname() -> str:
        """Mirror BuildContext's library directory detection (lib / lib64 / multiarch)."""
        libname = "lib"
        if os.path.isdir("/usr/lib64") and not os.path.islink("/usr/lib64"):
            libname = "lib64"
        if os.path.isdir("/usr/lib/x86_64-linux-gnu"):
            libname = "lib/x86_64-linux-gnu"
        return libname

    @staticmethod
    def _read_global_config_options() -> dict:
        """
        Read the ``global`` section of the kde-builder rc-file, if one can be found.

        Looks at ``./kde-builder.yaml`` first, then the per-user rc-file, matching the lookup that
        the rest of kde-builder uses. Returns an empty dict (callers fall back to defaults) when no
        readable config exists.
        """
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        candidates = [
            os.path.join(os.getcwd(), "kde-builder.yaml"),
            os.path.join(xdg_config_home, "kde-builder.yaml"),
        ]
        for path in candidates:
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f)
            except (OSError, yaml.YAMLError) as e:
                logger_qtc_tmpl.warning(f"\tCouldn't read kde-builder config {path}: {e}")
                return {}
            if isinstance(data, dict) and isinstance(data.get("global"), dict):
                return data["global"]
            return {}
        return {}

    def _write_cmake_user_presets(self, project_dir: str) -> None:
        """
        Write a ``CMakeUserPresets.json`` into the template's project directory.

        The preset carries the kde-builder install prefix and the build / run environment, plus the
        ``qt.io/QtCreator/1.0`` vendor metadata (run environment and install deploy step) that
        Qt Creator 20+ consumes directly. ``binaryDir`` uses CMake's ``${sourceDir}`` so each
        generated project builds into its own ``build/`` subdirectory.
        """
        prefix = self.install_prefix
        lib = self.libname

        cmake_prefix_path = prefix
        if self.qt_install_dir:
            cmake_prefix_path = f"{prefix}:{self.qt_install_dir}"

        # Run environment, shared with IdeProjectConfigGenerator (see qtcreator_presets).
        run_env = cmake_run_environment(prefix, lib)

        # Build environment (configure + build steps).
        build_env = {
            "PATH": run_env["PATH"],
            "LD_LIBRARY_PATH": run_env["LD_LIBRARY_PATH"],
            "PKG_CONFIG_PATH": f"{prefix}/{lib}/pkgconfig:" + os.environ.get("PKG_CONFIG_PATH", ""),
            "QT_PLUGIN_PATH": run_env["QT_PLUGIN_PATH"],
            "XDG_DATA_DIRS": run_env["XDG_DATA_DIRS"],
        }

        # CMake presets carry a cache variable's type in a {type, value} object, not as a ":TYPE"
        # suffix on the key (that suffix is only valid on the `-D` command line).
        cache_vars = {
            "CMAKE_PREFIX_PATH": cmake_prefix_path,
            "CMAKE_INSTALL_PREFIX": prefix,
            "CMAKE_BUILD_TYPE": "Debug",
            "CMAKE_EXPORT_COMPILE_COMMANDS": {"type": "BOOL", "value": "ON"},
        }

        qmake_path = self._find_qmake()
        if qmake_path:
            cache_vars["QT_QMAKE_EXECUTABLE"] = qmake_path

        # Unlike kde-builder-managed projects (which build into ~/kde/build/<project>), a freshly
        # created project builds into its own ${sourceDir}/build.
        presets = cmake_user_presets(
            generator="Ninja",
            binary_dir="${sourceDir}/build",
            cache_vars=cache_vars,
            environment=build_env,
            run_environment=run_env,
        )

        preset_path = os.path.join(project_dir, "CMakeUserPresets.json")
        with open(preset_path, "w") as f:
            f.write(json.dumps(presets, indent=4) + "\n")

    def _find_qmake(self) -> str | None:
        """Locate a qmake executable, preferring qt-install-dir then PATH."""
        if self.qt_install_dir:
            for name in ("qmake6", "qmake"):
                candidate = os.path.join(self.qt_install_dir, "bin", name)
                if os.path.isfile(candidate):
                    return candidate
        return shutil.which("qmake6") or shutil.which("qmake")
