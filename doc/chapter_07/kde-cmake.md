(kde-cmake-intro)=
# Introduction to CMake

In March 2006, the CMake program beat out several competitors and was
selected to be the build system for KDE 4, replacing the autotools-based
system that KDE had used from the beginning.

A introduction to CMake page is available on the [KDE Community
Wiki](https://community.kde.org/Guidelines_HOWTOs/CMake). Basically,
instead of running `make -f Makefile.cvs`, then `configure`, then Make,
we simply run CMake and then Make.

kde-builder has support for CMake. A few features of kde-builder were
really features of the underlying buildsystem, including
[configure-flags](#conf-configure-flags) and
[do-not-compile](#conf-do-not-compile). When equivalent features are
available, they are provided. For instance, the equivalent to the
configure-flags option is [cmake-options](#conf-cmake-options), and the
[do-not-compile](#conf-do-not-compile) option is also supported for
CMake as of kde-builder version 1.6.3.
