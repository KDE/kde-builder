#!/bin/bash

# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

# This script is used to bulk update the years values in spdx license headers.

# To get the lists of files for arrays, I used:
# find . -name "*.py" -not -path "./venv/*" -not -name "__init__.py" | sort

normal_py_files=(
  ./ksblib/Application.py
  ./ksblib/BuildContext.py
  ./ksblib/BuildException.py
  ./ksblib/BuildSystem/Autotools.py
  ./ksblib/BuildSystem/BuildSystem.py
  ./ksblib/BuildSystem/CMakeBootstrap.py
  ./ksblib/BuildSystem/KDECMake.py
  ./ksblib/BuildSystem/Meson.py
  ./ksblib/BuildSystem/QMake6.py
  ./ksblib/BuildSystem/QMake.py
  ./ksblib/BuildSystem/Qt4.py
  ./ksblib/BuildSystem/Qt5.py
  ./ksblib/BuildSystem/Qt6.py
  ./ksblib/Cmdline.py
  ./ksblib/DebugOrderHints.py
  ./ksblib/Debug.py
  ./ksblib/DependencyResolver.py
  ./ksblib/FirstRun.py
  ./ksblib/IPC/IPC.py
  ./ksblib/IPC/Null.py
  ./ksblib/IPC/Pipe.py
  ./ksblib/KDEProjectsReader.py
  ./ksblib/Module/BranchGroupResolver.py
  ./ksblib/Module/Module.py
  ./ksblib/ModuleResolver.py
  ./ksblib/ModuleSet/KDEProjects.py
  ./ksblib/ModuleSet/ModuleSet.py
  ./ksblib/ModuleSet/Null.py
  ./ksblib/ModuleSet/Qt5.py
  ./ksblib/OptionsBase.py
  ./ksblib/OSSupport.py
  ./ksblib/PhaseList.py
  ./ksblib/RecursiveFH.py
  ./ksblib/StartProgram.py
  ./ksblib/StatusView.py
  ./ksblib/TaskManager.py
  ./ksblib/Updater/Git.py
  ./ksblib/Updater/KDEProjectMetadata.py
  ./ksblib/Updater/KDEProject.py
  ./ksblib/Updater/Qt5.py
  ./ksblib/Updater/Updater.py
  ./ksblib/Util/LoggedSubprocess.py
  ./ksblib/Util/Util.py
  ./ksblib/Version.py
)

tests_py_files=(
  ./tests/integration/test_branch-time-based.py
  ./tests/integration/test_bug-394497-ignore-dep-module.py
  ./tests/integration/test_bug-395627-keep-cmake-prefix.py
  ./tests/integration/test_bug-402509-masked-cmdline-opts.py
  ./tests/integration/test_cmdline-no-include-dependencies.py
  ./tests/integration/test_custom-build-command-work.py
  ./tests/integration/test_install-and-run.py
  ./tests/integration/test_issue-64-cmdline-opt-override.py
  ./tests/integration/test_kde-projects-basics.py
  ./tests/integration/test_load-all-ksb-modules.py
  ./tests/integration/test_os-release-basics.py
  ./tests/integration/test_read-module-options.py
  ./tests/integration/test_set-module-option-value.py
  ./tests/integration/test_submodule-functions.py
  ./tests/unit/build-environment/test_platform-env-prepend.py
  ./tests/unit/build-system/test_empty-num-cores.py
  ./tests/unit/build-system/test_logged-subprocess.py
  ./tests/unit/debug-hints/test_compare-debug-order.py
  ./tests/unit/dependency-resolver/test_compare-build-order.py
  ./tests/unit/dependency-resolver/test_copy-up-dependencies.py
  ./tests/unit/dependency-resolver/test_detect-cycles.py
  ./tests/unit/dependency-resolver/test_get-dependency-path.py
  ./tests/unit/dependency-resolver/test_run-dependency-vote.py
  ./tests/unit/dependency-resolver/test_sort-build-order.py
  ./tests/unit/util/test_lndir.py
  ./tests/unit/util/test_prune_under_directory.py
)

merged_array=("${normal_py_files[@]}" "${tests_py_files[@]}")

reuse annotate --copyright "Andrew Shark <ashark@linuxcomp.ru>" --year "2023 - 2024" --merge-copyrights "${merged_array[@]}"
reuse annotate --copyright "Michael Pyne <mpyne@kde.org>" --year "2003 - 2023" --merge-copyrights "${merged_array[@]}"
reuse annotate --copyright "KDE Contributors (see git history) <community@kde.org>" --year "2004 - 2024" --merge-copyrights "${normal_py_files[@]}"
