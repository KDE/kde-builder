# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

def test_import_all():
    """
    Loads every single ksb module to make sure they all compile.
    """
    import ksblib.Application
    import ksblib.BuildContext
    import ksblib.BuildException
    import ksblib.BuildSystem
    import ksblib.BuildSystem.Autotools
    import ksblib.BuildSystem.CMakeBootstrap
    import ksblib.BuildSystem.KDECMake
    import ksblib.BuildSystem.Meson
    import ksblib.BuildSystem.QMake
    import ksblib.BuildSystem.QMake6
    import ksblib.BuildSystem.Qt4
    import ksblib.BuildSystem.Qt5
    import ksblib.BuildSystem.Qt6
    import ksblib.Cmdline
    import ksblib.Debug
    import ksblib.DebugOrderHints
    import ksblib.DependencyResolver
    import ksblib.FirstRun
    import ksblib.IPC
    import ksblib.IPC.Null
    import ksblib.IPC.Pipe
    import ksblib.KDEProjectsReader
    import ksblib.Module
    import ksblib.Module.BranchGroupResolver
    import ksblib.ModuleResolver
    import ksblib.ModuleSet
    import ksblib.ModuleSet.KDEProjects
    import ksblib.ModuleSet.Null
    import ksblib.ModuleSet.Qt5
    import ksblib.OptionsBase
    import ksblib.OSSupport
    import ksblib.PhaseList
    import ksblib.RecursiveFH
    import ksblib.StatusView
    import ksblib.TaskManager
    import ksblib.Updater
    import ksblib.Updater.Git
    import ksblib.Updater.KDEProject
    import ksblib.Updater.KDEProjectMetadata
    import ksblib.Updater.Qt5
    import ksblib.Util
    import ksblib.Util.LoggedSubprocess
    import ksblib.Version

    assert True, "Able to compile and load all kde-builder modules."
