# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
from typing import NoReturn
from typing import TYPE_CHECKING

from .debug import Debug
from .debug import KBLogger
from .util.textwrap_mod import textwrap

if TYPE_CHECKING:
    from .build_context import BuildContext

logger_app = KBLogger.getLogger("application")


class StartProgram:
    """
    Run the installed binary of some module.
    """

    @staticmethod
    def execute_built_binary(ctx: BuildContext, args: list[str]) -> NoReturn:
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

        pers_opts = ctx.persistent_options
        extra_run_env = ctx.get_option("source-when-start-program")

        install_dir = ctx.get_option("install-dir")
        bin_dir = f"{install_dir}/bin/"
        exec_path = f"{install_dir}/bin/{executable}"
        prefix_sh_path = f"{install_dir}/prefix.sh"

        if not os.path.exists(exec_path):
            logger_app.error(f" r[*] Program r[{executable}] does not exist in {bin_dir} directory.")
            if executable in pers_opts:  # Hint possible variants in case we got executable named as some already built module
                install_manifest = ctx.get_option("build-dir") + f"/{executable}/install_manifest.txt"
                bins_of_module = []
                if os.path.exists(install_manifest):
                    with open(install_manifest, "r") as f:
                        for line in f:
                            if line.startswith(bin_dir):
                                line = line.removeprefix(bin_dir).rstrip("\n")
                                bins_of_module.append(line)
                if bins_of_module:
                    logger_app.error("   You probably mean one from this list:")
                    for binary in bins_of_module:
                        logger_app.error("\ty[" + binary)
            exit(127)  # Command not found

        if not os.path.exists(prefix_sh_path):
            # Try to use prefix.sh from build dir if we can guess module (the case when executable is identical to module name, which is not always)
            msg = (f" r[*] Not found y[{install_dir}/prefix.sh] file. Please copy prefix.sh manually from build directory of any kde project or "
                   "add the \"-DKDE_INSTALL_PREFIX_SCRIPT=ON\" to cmake-options of any kde project and (re)build it.")
            if executable in pers_opts:
                prefix_sh_path = pers_opts[executable].get("build-dir", "/dev/null") + "/prefix.sh"
                if os.path.exists(prefix_sh_path):
                    logger_app.debug("Using prefix.sh from build directory")
                else:
                    logger_app.warning(msg)
                    exit(1)
            else:
                logger_app.warning(msg)
                exit(1)

        script = textwrap.dedent(f"""\
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
