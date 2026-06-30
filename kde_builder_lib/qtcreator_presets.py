# SPDX-FileCopyrightText: 2026 Bogdan Vatra <bogdan.vatra@kdab.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Shared helpers for generating Qt Creator ``CMakeUserPresets.json`` content.

Both the per-project generator (:class:`~kde_builder_lib.ide_project_config_generator.IdeProjectConfigGenerator`,
for projects kde-builder already manages) and the new-project wizard installer
(:class:`~kde_builder_lib.qtcreator_templates.QtCreatorTemplatesInstaller`) emit the same preset shape and
the same run environment, so that logic lives here once.
"""

from __future__ import annotations

import os


def cmake_run_environment(install_dir: str, libname: str) -> dict[str, str]:
    """
    Build the run environment for an application that runs against a kde-builder install prefix.

    Mirrors ``prefix.sh`` / ``kde-builder --run``.

    ``LD_LIBRARY_PATH`` is included even though kde-builder binaries carry an rpath to the install
    prefix: ``DT_RUNPATH`` does not propagate to transitively ``dlopen``ed libraries (for example a
    Kirigami QML plugin's dependency on ``libKirigamiPlatform.so``), so when a distro KF6 also exists
    under ``/usr/lib`` the older same-soname system copy can load first via the ldconfig cache and
    shadow the kde-builder one, causing undefined-symbol errors at run time. ``LD_LIBRARY_PATH``
    outranks the ldconfig cache and pins every lookup to the install prefix.

    Args:
        install_dir: The installation prefix (``install-dir``), e.g. ``~/kde/usr``.
        libname: The library subdirectory (``lib`` / ``lib64`` / ``lib/x86_64-linux-gnu``).

    Returns:
        A mapping of environment variable name to value.
    """
    return {
        "PATH": f"{install_dir}/bin:" + os.environ.get("PATH", ""),
        "LD_LIBRARY_PATH": f"{install_dir}/{libname}:" + os.environ.get("LD_LIBRARY_PATH", ""),
        "XDG_DATA_DIRS": f"{install_dir}/share:" + os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share"),
        "XDG_CONFIG_DIRS": f"{install_dir}/etc/xdg:" + os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg"),
        "QT_PLUGIN_PATH": f"{install_dir}/{libname}/plugins:" + os.environ.get("QT_PLUGIN_PATH", ""),
        "QML2_IMPORT_PATH": f"{install_dir}/{libname}/qml:" + os.environ.get("QML2_IMPORT_PATH", ""),
        "QT_QUICK_CONTROLS_STYLE_PATH": f"{install_dir}/{libname}/qml/QtQuick/Controls.2/:" + os.environ.get("QT_QUICK_CONTROLS_STYLE_PATH", ""),
        "MANPATH": f"{install_dir}/share/man:" + os.environ.get("MANPATH", "/usr/local/share/man:/usr/share/man"),
        "SASL_PATH": f"{install_dir}/{libname}/sasl2:" + os.environ.get("SASL_PATH", f"/usr/{libname}/sasl2"),
    }


def cmake_user_presets(*, generator: str, binary_dir: str, cache_vars: dict, environment: dict, run_environment: dict) -> dict:
    """
    Assemble a version-6 ``CMakeUserPresets.json`` document for the ``kde-builder`` preset.

    The ``qt.io/QtCreator/1.0`` vendor metadata carries the run environment and an ``install`` deploy
    step, which Qt Creator 20+ consumes directly (no kit registration required).

    Args:
        generator: CMake generator name, e.g. ``Ninja``.
        binary_dir: The configure preset ``binaryDir`` (an absolute path or a ``${sourceDir}/...`` macro).
        cache_vars: ``cacheVariables`` entries (values may be strings or ``{"type", "value"}`` objects).
        environment: The configure/build ``environment``.
        run_environment: The run environment (see :func:`cmake_run_environment`).

    Returns:
        A dict ready to be serialized with :func:`json.dumps`.
    """
    return {
        "version": 6,
        "configurePresets": [
            {
                "name": "kde-builder",
                "displayName": "KDE Builder",
                "generator": generator,
                "binaryDir": binary_dir,
                "vendor": {
                    "qt.io/QtCreator/1.0": {
                        "runEnvironment": run_environment,
                    },
                },
                "cacheVariables": cache_vars,
                "environment": environment,
            },
        ],
        "buildPresets": [
            {"name": "kde-builder", "configurePreset": "kde-builder"},
        ],
        "vendor": {
            "qt.io/QtCreator/1.0": {
                "deployPresets": [
                    {"type": "install", "name": "kde-builder"},
                ],
            },
        },
    }
