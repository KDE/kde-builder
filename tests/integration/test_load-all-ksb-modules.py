# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

def test_import_all():
    """
    Loads every single ksb module to make sure they all compile.
    """
    import kde_builder_lib.application
    import kde_builder_lib.build_context
    import kde_builder_lib.build_exception
    import kde_builder_lib.build_system
    import kde_builder_lib.build_system.autotools
    import kde_builder_lib.build_system.cmake_bootstrap
    import kde_builder_lib.build_system.kde_cmake
    import kde_builder_lib.build_system.meson
    import kde_builder_lib.build_system.qmake5
    import kde_builder_lib.build_system.qmake6
    import kde_builder_lib.build_system.qt4
    import kde_builder_lib.build_system.qt5
    import kde_builder_lib.build_system.qt6
    import kde_builder_lib.cmd_line
    import kde_builder_lib.debug
    import kde_builder_lib.debug_order_hints
    import kde_builder_lib.dependency_resolver
    import kde_builder_lib.first_run
    import kde_builder_lib.ipc
    import kde_builder_lib.ipc.null
    import kde_builder_lib.ipc.pipe
    import kde_builder_lib.kde_projects_reader
    import kde_builder_lib.module
    import kde_builder_lib.module.branch_group_resolver
    import kde_builder_lib.module_resolver
    import kde_builder_lib.module_set
    import kde_builder_lib.module_set.kde_projects
    import kde_builder_lib.module_set.null
    import kde_builder_lib.module_set.qt5
    import kde_builder_lib.options_base
    import kde_builder_lib.os_support
    import kde_builder_lib.phase_list
    import kde_builder_lib.recursive_fh
    import kde_builder_lib.status_view
    import kde_builder_lib.task_manager
    import kde_builder_lib.updater
    import kde_builder_lib.updater.updater
    import kde_builder_lib.updater.kde_project
    import kde_builder_lib.updater.kde_project_metadata
    import kde_builder_lib.updater.qt5
    import kde_builder_lib.util
    import kde_builder_lib.util.logged_subprocess
    import kde_builder_lib.version

    assert True, "Able to compile and load all kde-builder modules."
