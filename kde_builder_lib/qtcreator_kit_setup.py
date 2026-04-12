# SPDX-FileCopyrightText: 2026 BogDan Vatra <bogdan@kde.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import platform
import re
import shlex
import shutil
import subprocess

from .build_context import BuildContext
from .debug import KBLogger

logger = KBLogger.getLogger("qtcreator-kit-setup")


class QtCreatorKitSetup:
    """
    Uses Qt Creator's sdktool to register a KDE development kit.

    The kit includes:
    - CMake configuration variables (prefix paths, module paths, flags)
    - Build environment variables (PATH, LD_LIBRARY_PATH, PKG_CONFIG_PATH, etc.)
    - Run environment variables (from prefix.sh pattern)
    - CMake generator set to Ninja
    """

    KIT_ID = "org.kde.builder"
    KIT_NAME = "KDE Builder"

    QT_ID = "org.kde.builder.qt"
    QT_NAME = "Qt (KDE Builder)"

    SDKTOOL_SEARCH_PATHS = [
        os.path.expanduser("~/Qt/Tools/sdktool/libexec/qtcreator/sdktool"),
        "/usr/libexec/qtcreator/sdktool",
        "/usr/lib/qtcreator/sdktool",
    ]

    def __init__(self, context: BuildContext):
        self.context = context
        self.install_dir = context.get_option("install-dir")
        self.build_dir = context.get_option("build-dir")
        self.source_dir = context.get_option("source-dir")
        self.qt_install_dir = context.get_option("qt-install-dir")
        self.libname = context.libname

    def setup_kit(self) -> bool:
        sdktool = self._find_sdktool()
        if not sdktool:
            logger.error("Could not find sdktool. Please set b[qtcreator-sdktool-path] in your kde-builder config.")
            logger.error("or install Qt Creator SDK tools.")
            return False

        sdkpath = self._get_sdkpath()

        print(f"Using sdktool: {sdktool}")
        print(f"Using settings path: {sdkpath}")
        print(f"Install prefix: {self.install_dir}")

        # Check if kit already exists
        if self._kit_exists(sdktool, sdkpath):
            print(f"Kit {self.KIT_ID} already exists.")
            response = input("Remove existing kit and recreate? [y/N] ").strip().lower()
            if response != "y":
                print("Kit setup cancelled.")
                return True
            self._remove_kit(sdktool, sdkpath)

        # Find or register Qt version (mandatory for kit)
        qt_id = self._resolve_qt_version(sdktool, sdkpath)
        if not qt_id:
            print("ERROR: No compatible Qt 6+ version found. Cannot create kit.")
            print("Register a Qt version in Qt Creator or pass --qt-install-dir to kde-builder.")
            return False

        # Find best registered CMake tool
        cmake_id = self._find_best_cmake(sdktool, sdkpath)

        # Determine target ABI and find matching toolchains/debugger
        target_abi = self._get_target_abi()
        toolchains: dict[str, str] = {}
        debugger_id = None
        if target_abi:
            print(f"Target ABI: {target_abi}")
            toolchains = self._find_best_toolchains(sdktool, sdkpath, target_abi)
            debugger_id = self._find_best_debugger(sdktool, sdkpath, target_abi)
        else:
            print("WARNING: Could not determine target ABI. Toolchains and debugger will not be set.")

        # Create the kit
        success = self._create_kit(sdktool, sdkpath, qt_id=qt_id, cmake_id=cmake_id,
                                   toolchains=toolchains, debugger_id=debugger_id)

        if success:
            # addKit hardcodes SDK=true and AutoDetected=true which causes
            # Qt Creator to discard the kit. Patch them to false.
            self._patch_kit_flags(sdktool, sdkpath)
            print(f"\nKit '{self.KIT_NAME}' (id: {self.KIT_ID}) created successfully!")
            print("Restart Qt Creator to pick up the new kit.")
        return success

    def _find_sdktool(self) -> str | None:
        configured = self.context.get_option("qtcreator-sdktool-path")
        if configured:
            expanded = os.path.expanduser(configured)
            if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
                return expanded
            logger.warning(f"Configured sdktool path not found or not executable: {configured}")
            return None

        for path in self.SDKTOOL_SEARCH_PATHS:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        found = shutil.which("sdktool")
        if found:
            return found

        return None

    def _get_sdkpath(self) -> str:
        configured = self.context.get_option("qtcreator-settings-path")
        if configured:
            return os.path.expanduser(configured)
        return os.path.expanduser("~/.config/QtProject/qtcreator")

    def _run_sdktool(self, sdktool: str, sdkpath: str, args: list[str], check: bool = True, silent: bool = False) -> subprocess.CompletedProcess:
        cmd = [sdktool, f"--sdkpath={sdkpath}"] + args
        if not silent:
            print(f"  > {shlex.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            logger.debug(f"sdktool stderr: {result.stderr.strip()}")
        return result

    # ── Generic sdktool enumeration ──────────────────────────────────

    def _enumerate_entries(self, sdktool: str, sdkpath: str, file: str, key: str) -> list[str]:
        """Use findKey to enumerate all entry prefixes in a settings file.

        Returns list of prefixes, e.g. ["QtVersion.0", "QtVersion.1"].
        """
        result = self._run_sdktool(sdktool, sdkpath, ["findKey", file, key], check=False, silent=True)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        prefixes = []
        for line in result.stdout.strip().splitlines():
            # line looks like "QtVersion.0/Id" or "CMakeTools.1/Id"
            prefix = line.rsplit("/", 1)[0]
            prefixes.append(prefix)
        return prefixes

    def _get_entry_value(self, sdktool: str, sdkpath: str, file: str, key_path: str) -> str | None:
        """Get a single value from sdktool settings. Returns None on failure."""
        result = self._run_sdktool(sdktool, sdkpath, ["get", file, key_path], check=False, silent=True)
        if result.returncode == 0:
            val = result.stdout.strip()
            if val and val != "<invalid>":
                return val
        return None

    # ── Kit existence / removal ──────────────────────────────────────

    def _kit_exists(self, sdktool: str, sdkpath: str) -> bool:
        for prefix in self._enumerate_entries(sdktool, sdkpath, "profiles", "PE.Profile.Id"):
            val = self._get_entry_value(sdktool, sdkpath, "profiles", f"{prefix}/PE.Profile.Id")
            if val == self.KIT_ID:
                return True
        return False

    def _remove_kit(self, sdktool: str, sdkpath: str) -> None:
        print(f"Removing existing kit {self.KIT_ID}...")
        self._run_sdktool(sdktool, sdkpath, ["rmKit", "--id", self.KIT_ID], check=False)

    def _patch_kit_flags(self, sdktool: str, sdkpath: str) -> None:
        """Set PE.Profile.SDK=false and PE.Profile.AutoDetected=false.

        addKit hardcodes both to true, which causes Qt Creator to treat the
        kit as auto-detected/SDK-provided and discard it on startup.
        """
        prefix = None
        for p in self._enumerate_entries(sdktool, sdkpath, "profiles", "PE.Profile.Id"):
            val = self._get_entry_value(sdktool, sdkpath, "profiles", f"{p}/PE.Profile.Id")
            if val == self.KIT_ID:
                prefix = p
                break

        if not prefix:
            print("WARNING: Could not find kit to patch flags.")
            return

        for key in ("PE.Profile.SDK", "PE.Profile.AutoDetected"):
            self._run_sdktool(sdktool, sdkpath, ["rmKeys", "profiles", f"{prefix}/{key}"], check=False)
            self._run_sdktool(sdktool, sdkpath, ["addKeys", "profiles", f"{prefix}/{key}", "bool:false"])

    # ── Version parsing helpers ──────────────────────────────────────

    @staticmethod
    def _parse_version(version_str: str) -> tuple[int, ...] | None:
        m = re.match(r"(\d+)\.(\d+)\.(\d+)", version_str)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return None

    @staticmethod
    def _get_qt_version_from_qmake(qmake_path: str) -> tuple[int, ...] | None:
        """Run qmake -query QT_VERSION and parse the result."""
        try:
            result = subprocess.run([qmake_path, "-query", "QT_VERSION"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return QtCreatorKitSetup._parse_version(result.stdout.strip())
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None

    @staticmethod
    def _get_cmake_version(cmake_path: str) -> tuple[int, ...] | None:
        """Run cmake --version and parse the result."""
        try:
            result = subprocess.run([cmake_path, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                m = re.search(r"cmake version (\d+\.\d+\.\d+)", result.stdout)
                if m:
                    return QtCreatorKitSetup._parse_version(m.group(1))
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None

    # ── Qt version handling ──────────────────────────────────────────

    def _enumerate_qt_versions(self, sdktool: str, sdkpath: str) -> list[dict]:
        """List all registered Qt versions with metadata."""
        entries = []
        for prefix in self._enumerate_entries(sdktool, sdkpath, "qtversion", "Id"):
            qt_id = self._get_entry_value(sdktool, sdkpath, "qtversion", f"{prefix}/Id")
            qmake = self._get_entry_value(sdktool, sdkpath, "qtversion", f"{prefix}/QMakePath")
            auto_src = self._get_entry_value(sdktool, sdkpath, "qtversion", f"{prefix}/autodetectionSource")

            if not qmake:
                continue

            version = self._get_qt_version_from_qmake(qmake) if os.path.isfile(qmake) else None

            # addKit --qt matches against autodetectionSource. Entries with
            # autodetectionSource="PATH" (system auto-detected) cannot be
            # referenced — only those with a proper detection source id work.
            detection_source = auto_src if auto_src and auto_src != "PATH" else None

            entries.append({
                "raw_id": qt_id,
                "detection_source": detection_source,  # full autodetectionSource for addKit --qt, or None
                "qmake": qmake,
                "version": version,
                "is_system": qmake.startswith("/usr/"),
            })
        return entries

    def _find_qmake(self) -> str | None:
        if self.qt_install_dir:
            for name in ["qmake6", "qmake"]:
                path = os.path.join(self.qt_install_dir, "bin", name)
                if os.path.isfile(path):
                    return path
        return shutil.which("qmake6") or shutil.which("qmake")

    def _register_qt(self, sdktool: str, sdkpath: str, qmake: str) -> str | None:
        """Register a Qt version via sdktool. Returns the autodetectionSource or None."""
        # Remove stale entry if present
        self._run_sdktool(sdktool, sdkpath, ["rmQt", "--id", self.QT_ID], check=False)

        print(f"Registering Qt version from {qmake}...")
        result = self._run_sdktool(sdktool, sdkpath, [
            "addQt",
            "--id", self.QT_ID,
            "--name", self.QT_NAME,
            "--qmake", qmake,
            "--type", "Qt4ProjectManager.QtVersion.Desktop",
        ])
        if result.returncode != 0:
            print(f"WARNING: Failed to register Qt version: {result.stderr.strip()}")
            return None
        # addQt creates autodetectionSource as "SDK.<id>"
        return f"SDK.{self.QT_ID}"

    def _resolve_qt_version(self, sdktool: str, sdkpath: str) -> str | None:
        """Find or register a Qt 6+ version for the kit.

        Returns the full autodetectionSource value for use with addKit --qt,
        or None if no compatible Qt is found.

        Strategy:
        1. If --qt-install-dir is set, look for a matching registered version
           or register a new one.
        2. Otherwise, scan registered versions and pick the best compatible
           one (Qt 6+). Prefer system Qt, else highest version.
        3. If a compatible Qt exists but has autodetectionSource=PATH (not
           usable by sdktool), re-register it.
        """
        registered = self._enumerate_qt_versions(sdktool, sdkpath)

        if self.qt_install_dir:
            qmake = self._find_qmake()
            if not qmake:
                print("WARNING: Could not find qmake in qt-install-dir.")
                return None
            # Check if already registered with a usable detection source
            for entry in registered:
                if entry["qmake"] == qmake and entry["detection_source"]:
                    print(f"Found existing Qt version ({entry['detection_source']}) matching qt-install-dir, reusing.")
                    return entry["detection_source"]
            # Not usable — register it
            return self._register_qt(sdktool, sdkpath, qmake)

        # No --qt-install-dir: pick best from registered Qt 6+ versions
        compatible = [e for e in registered if e["version"] and e["version"][0] >= 6]
        if not compatible:
            # Nothing registered at all — try to register system qmake
            qmake = shutil.which("qmake6") or shutil.which("qmake")
            if qmake:
                version = self._get_qt_version_from_qmake(qmake)
                if version and version[0] >= 6:
                    return self._register_qt(sdktool, sdkpath, qmake)
            return None

        # Prefer entries with a usable detection source
        referenceable = [e for e in compatible if e["detection_source"]]

        if referenceable:
            # Prefer system Qt among referenceable
            system_qts = [e for e in referenceable if e["is_system"]]
            if system_qts:
                best = max(system_qts, key=lambda e: e["version"])
            else:
                best = max(referenceable, key=lambda e: e["version"])
            print(f"Using Qt {'.'.join(map(str, best['version']))} ({best['detection_source']}).")
            return best["detection_source"]

        # Compatible Qt exists but detection_source is PATH — re-register best one
        system_qts = [e for e in compatible if e["is_system"]]
        if system_qts:
            best = max(system_qts, key=lambda e: e["version"])
        else:
            best = max(compatible, key=lambda e: e["version"])
        print(f"Qt {'.'.join(map(str, best['version']))} at {best['qmake']} has no usable detection source, re-registering...")
        return self._register_qt(sdktool, sdkpath, best["qmake"])

    # ── CMake tool handling ──────────────────────────────────────────

    def _find_best_cmake(self, sdktool: str, sdkpath: str) -> str | None:
        """Find the best registered CMake tool by version.

        Only registers a new one if no cmake tools exist at all.
        """
        entries = []
        for prefix in self._enumerate_entries(sdktool, sdkpath, "cmaketools", "Id"):
            cmake_id = self._get_entry_value(sdktool, sdkpath, "cmaketools", f"{prefix}/Id")
            binary = self._get_entry_value(sdktool, sdkpath, "cmaketools", f"{prefix}/Binary")

            if not cmake_id or not binary:
                continue

            version = self._get_cmake_version(binary) if os.path.isfile(binary) else None
            entries.append({"id": cmake_id, "binary": binary, "version": version})

        # Filter to those with a valid, accessible binary
        valid = [e for e in entries if e["version"] is not None]
        if not valid:
            return self._register_fallback_cmake(sdktool, sdkpath)

        best = max(valid, key=lambda e: e["version"])
        print(f"Using CMake {'.'.join(map(str, best['version']))} (id={best['id']}) at {best['binary']}.")
        return best["id"]

    def _register_fallback_cmake(self, sdktool: str, sdkpath: str) -> str | None:
        """Register system cmake as a last resort when none are registered."""
        cmake_path = shutil.which("cmake")
        if not cmake_path:
            print("WARNING: Could not find cmake in PATH. CMake tool will not be set in the kit.")
            return None

        cmake_id = "org.kde.builder.cmake"
        print(f"No usable CMake tools registered. Registering {cmake_path}...")
        result = self._run_sdktool(sdktool, sdkpath, [
            "addCMake",
            "--id", cmake_id,
            "--name", "CMake (KDE Builder)",
            "--path", cmake_path,
        ])
        if result.returncode != 0:
            print(f"WARNING: Failed to register CMake: {result.stderr.strip()}")
            return None
        return cmake_id

    # ── ABI detection ───────────────────────────────────────────────

    @staticmethod
    def _gnu_triplet_to_abi(triplet: str) -> str | None:
        """Convert GNU triplet (e.g. x86_64-linux-gnu) to Qt Creator ABI string."""
        arch_part = triplet.split("-")[0]
        arch_map = {
            "x86_64": ("x86", "64bit"),
            "i686": ("x86", "32bit"),
            "i386": ("x86", "32bit"),
            "aarch64": ("arm", "64bit"),
            "arm": ("arm", "32bit"),
            "riscv64": ("riscv", "64bit"),
            "riscv32": ("riscv", "32bit"),
        }
        match = arch_map.get(arch_part)
        if match:
            qtc_arch, width = match
            return f"{qtc_arch}-linux-generic-elf-{width}"
        return None

    def _get_target_abi(self) -> str | None:
        """Determine the target ABI string for toolchain/debugger matching.

        Uses gcc -dumpmachine as primary source, falls back to platform.machine().
        """
        for compiler in ("gcc", "cc"):
            path = shutil.which(compiler)
            if not path:
                continue
            try:
                result = subprocess.run([path, "-dumpmachine"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    abi = self._gnu_triplet_to_abi(result.stdout.strip())
                    if abi:
                        return abi
            except (OSError, subprocess.TimeoutExpired):
                pass

        machine = platform.machine()
        fallback_map = {
            "x86_64": "x86-linux-generic-elf-64bit",
            "i686": "x86-linux-generic-elf-32bit",
            "aarch64": "arm-linux-generic-elf-64bit",
            "riscv64": "riscv-linux-generic-elf-64bit",
        }
        return fallback_map.get(machine)

    # ── Toolchain handling ───────────────────────────────────────────

    def _find_best_toolchains(self, sdktool: str, sdkpath: str, target_abi: str) -> dict[str, str]:
        """Find best C and Cxx toolchains matching the target ABI.

        Returns dict with keys 'C' and/or 'Cxx' mapping to toolchain IDs.
        Prefers non-ccache GCC toolchains over Clang.
        """
        entries = []
        for prefix in self._enumerate_entries(sdktool, sdkpath, "toolchains", "ProjectExplorer.ToolChain.Id"):
            tc_id = self._get_entry_value(sdktool, sdkpath, "toolchains", f"{prefix}/ProjectExplorer.ToolChain.Id")
            lang = self._get_entry_value(sdktool, sdkpath, "toolchains", f"{prefix}/ProjectExplorer.ToolChain.LanguageV2")
            abi = self._get_entry_value(sdktool, sdkpath, "toolchains", f"{prefix}/ProjectExplorer.GccToolChain.TargetAbi")
            path = self._get_entry_value(sdktool, sdkpath, "toolchains", f"{prefix}/ProjectExplorer.GccToolChain.Path")

            if not all([tc_id, lang, abi, path]):
                continue
            if abi != target_abi:
                continue

            entries.append({
                "id": tc_id,
                "lang": lang,
                "path": path,
                "is_gcc": ".Gcc:" in tc_id,
                "is_ccache": "/ccache/" in path,
            })

        result = {}
        for lang in ("C", "Cxx"):
            candidates = [e for e in entries if e["lang"] == lang]
            if not candidates:
                continue
            # Prefer: non-ccache, then GCC over Clang, then stable sort by path
            candidates.sort(key=lambda e: (e["is_ccache"], not e["is_gcc"], e["path"]))
            best = candidates[0]
            result[lang] = best["id"]
            print(f"Using {lang} toolchain: {best['path']} ({best['id']})")

        return result

    # ── Debugger handling ────────────────────────────────────────────

    def _find_best_debugger(self, sdktool: str, sdkpath: str, target_abi: str) -> str | None:
        """Find best debugger matching the target ABI.

        Prefers GDB (EngineType 1) over LLDB (EngineType 256).
        """
        entries = []
        for prefix in self._enumerate_entries(sdktool, sdkpath, "debuggers", "Id"):
            dbg_id = self._get_entry_value(sdktool, sdkpath, "debuggers", f"{prefix}/Id")
            binary = self._get_entry_value(sdktool, sdkpath, "debuggers", f"{prefix}/Binary")
            engine = self._get_entry_value(sdktool, sdkpath, "debuggers", f"{prefix}/EngineType")

            if not dbg_id or not binary:
                continue

            # Abis is a list; sdktool prints with index prefixes. Check substring match.
            abis_result = self._run_sdktool(sdktool, sdkpath, ["get", "debuggers", f"{prefix}/Abis"], check=False, silent=True)
            abis_str = abis_result.stdout if abis_result.returncode == 0 else ""
            if target_abi not in abis_str:
                continue

            entries.append({
                "id": dbg_id,
                "binary": binary,
                "is_gdb": engine == "1",
            })

        if not entries:
            return None

        # Prefer GDB, then by binary path for stable ordering
        entries.sort(key=lambda e: (not e["is_gdb"], e["binary"]))
        best = entries[0]
        print(f"Using debugger: {best['binary']} (id={best['id']})")
        return best["id"]

    # ── Environment variables ────────────────────────────────────────

    def _get_build_env_vars(self) -> list[str]:
        """Get build environment variables in KEY=VALUE format for --env."""
        install = self.install_dir
        libname = self.libname
        env_vars = []

        env_vars.append(f"PKG_CONFIG_PATH={install}/{libname}/pkgconfig")
        env_vars.append(f"LD_LIBRARY_PATH={install}/{libname}")
        env_vars.append(f"PATH={install}/bin:" + os.environ.get("PATH", ""))
        env_vars.append(f"QT_PLUGIN_PATH={install}/lib64/plugins:{install}/lib/plugins")
        env_vars.append(f"XDG_DATA_DIRS={install}/share:" + os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share"))

        return env_vars

    def _get_run_env_vars(self) -> list[str]:
        """Get run environment variables in KEY=VALUE format for --run-env.

        These mirror what prefix.sh exports — the runtime environment needed
        to run KDE applications built from source.
        """
        install = self.install_dir
        libname = self.libname
        env_vars = []

        env_vars.append(f"PATH={install}/bin:" + os.environ.get("PATH", ""))
        env_vars.append(f"XDG_DATA_DIRS={install}/share:" + os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share"))
        env_vars.append(f"XDG_CONFIG_DIRS={install}/etc/xdg:" + os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg"))
        env_vars.append(f"QT_PLUGIN_PATH={install}/{libname}/plugins:" + os.environ.get("QT_PLUGIN_PATH", ""))
        env_vars.append(f"QML2_IMPORT_PATH={install}/{libname}/qml:" + os.environ.get("QML2_IMPORT_PATH", ""))
        env_vars.append(f"QT_QUICK_CONTROLS_STYLE_PATH={install}/{libname}/qml/QtQuick/Controls.2/:" + os.environ.get("QT_QUICK_CONTROLS_STYLE_PATH", ""))
        env_vars.append(f"MANPATH={install}/share/man:" + os.environ.get("MANPATH", "/usr/local/share/man:/usr/share/man"))
        env_vars.append(f"SASL_PATH={install}/{libname}/sasl2:" + os.environ.get("SASL_PATH", f"/usr/{libname}/sasl2"))

        return env_vars

    # ── CMake configuration variables ────────────────────────────────

    def _get_cmake_config_vars(self) -> list[str]:
        """Get CMake configuration variables for --cmake-config."""
        install = self.install_dir
        config = []

        config.append(f"CMAKE_INSTALL_PREFIX:PATH={install}")
        config.append(f"CMAKE_PREFIX_PATH:PATH={install};%{{Qt:QT_INSTALL_PREFIX}}")
        config.append(f"CMAKE_MODULE_PATH:PATH={install}/lib64/cmake;{install}/lib/cmake")
        config.append("CMAKE_CXX_COMPILER:FILEPATH=%{Compiler:Executable:Cxx}")
        config.append("CMAKE_C_COMPILER:FILEPATH=%{Compiler:Executable:C}")
        config.append("QT_QMAKE_EXECUTABLE:FILEPATH=%{Qt:qmakeExecutable}")

        cxxflags = self.context.get_option("cxxflags")
        if cxxflags:
            config.append(f"CMAKE_CXX_FLAGS:STRING={cxxflags}")

        cmake_options = self.context.get_option("cmake-options")
        if cmake_options:
            existing_vars = {v.split("=")[0].split(":")[0] for v in config}
            for opt in cmake_options.split():
                if opt.startswith("-D"):
                    var_name = opt[2:].split("=")[0].split(":")[0]
                    if var_name not in existing_vars and var_name != "CMAKE_BUILD_TYPE":
                        config.append(opt[2:])

        return config

    # ── Kit creation ─────────────────────────────────────────────────

    def _create_kit(self, sdktool: str, sdkpath: str, qt_id: str | None = None, cmake_id: str | None = None,
                    toolchains: dict[str, str] | None = None, debugger_id: str | None = None) -> bool:
        print(f"Creating kit '{self.KIT_NAME}'...")

        args = [
            "addKit",
            "--id", self.KIT_ID,
            "--name", self.KIT_NAME,
            "--devicetype", "Desktop",
            "--cmake-generator", "Ninja:::",
        ]

        if qt_id:
            args.extend(["--qt", qt_id])

        if cmake_id:
            args.extend(["--cmake", cmake_id])

        if toolchains:
            if "C" in toolchains:
                args.extend(["--Ctoolchain", toolchains["C"]])
            if "Cxx" in toolchains:
                args.extend(["--Cxxtoolchain", toolchains["Cxx"]])

        if debugger_id:
            args.extend(["--debuggerid", debugger_id])

        for config_var in self._get_cmake_config_vars():
            args.extend(["--cmake-config", config_var])

        for env_var in self._get_build_env_vars():
            args.extend(["--env", env_var])

        for env_var in self._get_run_env_vars():
            args.extend(["--run-env", env_var])

        result = self._run_sdktool(sdktool, sdkpath, args)
        if result.returncode != 0:
            print(f"ERROR: Failed to create kit: {result.stderr.strip()}")
            return False
        return True
