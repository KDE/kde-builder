# SPDX-FileCopyrightText: 2026 Méven Car <meven@kde.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder.build_context import BuildContext
from kde_builder.build_system.kde_cmake import BuildSystemKDECMake
from kde_builder.module.module import Module


def test_kde_install_libdir():
    """
    kde-builder should tell CMake to install into the same libdir it assumes itself (libname),
    unless the user set a libdir explicitly. Otherwise KDEInstallDirs may pick a different one and
    split the install prefix (e.g. lib64 while kde-builder uses lib).
    """
    ctx = BuildContext()
    ctx.set_option("override-build-system", "KDE")  # use CMake without probing a source dir
    ctx.set_option("install-dir", "/tmp/kde-test")

    # 1. By default, we pass our detected libname as KDE_INSTALL_LIBDIR.
    ctx.set_option("cmake-options", "")
    mod = Module(ctx, "test")
    mod.set_build_system()
    assert isinstance(mod.build_system, BuildSystemKDECMake)
    libname = mod.get_option("libname")
    assert f"-DKDE_INSTALL_LIBDIR={libname}" in mod.build_system.get_final_cmake_options()

    # 2. A user-set KDE_INSTALL_LIBDIR is kept and not duplicated.
    ctx.set_option("cmake-options", "-DKDE_INSTALL_LIBDIR=customlib")
    mod = Module(ctx, "test2")
    mod.set_build_system()
    libdir_options = [opt for opt in mod.build_system.get_final_cmake_options() if "KDE_INSTALL_LIBDIR" in opt]
    assert libdir_options == ["-DKDE_INSTALL_LIBDIR=customlib"]

    # 3. A user-set CMAKE_INSTALL_LIBDIR also suppresses our KDE_INSTALL_LIBDIR.
    ctx.set_option("cmake-options", "-DCMAKE_INSTALL_LIBDIR=customlib")
    mod = Module(ctx, "test3")
    mod.set_build_system()
    assert not [opt for opt in mod.build_system.get_final_cmake_options() if "KDE_INSTALL_LIBDIR" in opt]
