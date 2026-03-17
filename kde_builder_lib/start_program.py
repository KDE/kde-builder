# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
from typing import NoReturn
from typing import TYPE_CHECKING

from .debug import Debug
from .debug import KBLogger
from .util.textwrap_mod import dedent

if TYPE_CHECKING:
    from .build_context import BuildContext

logger_app = KBLogger.getLogger("application")


class StartProgram:
    """
    Run the installed binary of some project.
    """

    def __init__(self, ctx: BuildContext) -> None:
        self.ctx = ctx
        self.pers_opts = self.ctx.persistent_options

        self.bin_to_proj_map: dict[str, list[str]] = {}
        for proj_name, proj_data in self.pers_opts.items():
            binaries = proj_data.get("installed-binaries", [])
            for binary in binaries:
                self.bin_to_proj_map[binary] = proj_name

    def execute_built_binary(self, args: list[str]) -> NoReturn:
        """
        Execute the binary from install-dir/bin, and sources the environment file before that.
        """
        opt_fork = 0

        # We manually care of options. They can only appear in front of executable name.
        arg = None
        while True:
            try:
                arg = args.pop(0)
                if arg == "-f" or arg == "--fork":
                    opt_fork = 1
                    continue
                break
            except IndexError:
                arg = None
                break

        executable = arg
        if executable is None:  # the case when user specified -f, but then did not specified the executable name
            logger_app.error("Executable name is missing")
            exit(1)

        extra_run_env = self.ctx.get_option("source-when-start-program")

        install_dir = self.ctx.get_option("install-dir")
        bin_dir = f"{install_dir}/bin/"
        exec_path = f"{install_dir}/bin/{executable}"

        if not os.path.exists(exec_path):
            logger_app.error(f" r[*] Program r[{executable}] does not exist in {bin_dir} directory.")
            if executable in self.pers_opts:  # Hint possible variants in case we got a name of some already built project
                bins_of_project = self.pers_opts[executable].get("installed-binaries", [])
                if bins_of_project:
                    logger_app.error("   You probably mean one from this list:")
                    for binary in bins_of_project:
                        logger_app.error("\ty[" + binary)
            exit(127)  # Command not found

        prefix_sh_path = self._determine_prefix_sh_path(executable)

        script = dedent(f"""
        #!/bin/sh
        . "{prefix_sh_path}"
        . "{extra_run_env}"

        if [ "{opt_fork}" = "1" ]; then
            nohup "{exec_path}" "$@" >/dev/null 2>&1 &
            disown
            echo "PID:                $!"
            printf "%.0s#" {{1..80}}
            printf "\\n\\n"
        else
            echo "PID:                $$"
            printf "%.0s#" {{1..80}}
            printf "\\n\\n"
            exec "{exec_path}" "$@"
        fi

        """)

        # Print run information
        logger_app.warning(
            "#" * 80 + "\n" +
            f"Executable:         {executable}\n" +
            f"""Arguments:          {" ".join(args)}"""
        )

        if Debug().pretending():
            exit(0)

        try:
            #                               sh     -c command_string    command_name       $1 $2 $3...
            os.execv("/bin/sh", ["/bin/sh", "-c", script, "kde-builder run script"] + args)
        except Exception as e:
            logger_app.error(f"Error executing {executable}: {e}")
            exit(1)

    def _determine_prefix_sh_path(self, executable) -> str:
        build_dir = ""

        # Try to use prefix.sh from build dir if we can determine project name,
        # and persistent option lists the executable.
        if executable in self.bin_to_proj_map:
            proj_name = self.bin_to_proj_map[executable]
            build_dir = self.pers_opts[proj_name].get("build-dir", "")

            if build_dir:
                build_dir_prefix_sh_path = build_dir + "/prefix.sh"
                if os.path.exists(build_dir_prefix_sh_path):
                    logger_app.debug("Using prefix.sh from build directory")
                    return build_dir_prefix_sh_path

        # Try to fall back to common prefix.sh
        install_dir = self.ctx.get_option("install-dir")
        common_prefix_sh_path = f"{install_dir}/prefix.sh"
        if os.path.exists(common_prefix_sh_path):
            logger_app.debug("Using prefix.sh from install directory")
            return common_prefix_sh_path

        logger_app.error(dedent(f"""
             r[*] Not found y[prefix.sh] file neither in build-dir, nor in install-dir.
                 build-dir: {build_dir or "<undefined>"}
                 install-dir: {install_dir}
             r[*] Please copy prefix.sh manually from build directory of any kde project or add the \"-DKDE_INSTALL_PREFIX_SCRIPT=ON\" to cmake-options of any kde project and (re)build it.
            """, preserve_len=1))
        exit(1)
