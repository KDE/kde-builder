from __future__ import annotations
import os
import textwrap
from typing import NoReturn
from .Debug import Debug
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .BuildContext import BuildContext


class StartProgram:
    @staticmethod
    def executeCommandLineProgram(ctx: BuildContext, args: list) -> NoReturn:
        """
        kde-builder --run [options] <module-name> [arguments]
        
        OPTIONS
        "-e", "--exec" <program> Specify program of the module. Default to module name.
        "-f", "--fork" Launch the program in a new session.
        
        EXAMPLES
        
        Launch kate in a new session with '-l 5 file1.txt' arguments.
            kde-builder --run -f kate -l 5 file1.txt
        
        Launch kate-syntax-highlighter of module kate with '--list-themes' argument.
            kde-builder-launch -e kate-syntax-highlighter kate --list-themes
        """
        
        optExec = None
        optFork = 0
        
        # We cannot use GetOptionsFromArray here, because -e or -f could be meant to be arguments of module executable. But that would steal them.
        # We manually care of them, they can only appear in front of module/executable name.
        arg = None
        while arg := args.pop(0):
            if arg == "-f" or arg == "--fork":
                optFork = 1
                continue
            elif arg == "-e" or arg == "--exec":
                optExec = args.pop(0)
                if optExec is None:
                    Debug().error("-e option requires a name of executable")
                    exit(1)
                continue
            break
        
        module = arg
        if module is None:  # the case when user specified -e executable_name and/or -f, but then did not specified the module name
            Debug().error("The module name is missing")
            exit(1)
        
        executable = optExec or module
        buildData = ctx.persistent_options
        extraRunEnv = ctx.getOption("source-when-start-program")
        
        if module not in buildData:
            print(f"Module {module} has not been built yet.")
            exit(1)
        
        buildDir = buildData[module]["build-dir"]
        installDir = buildData[module]["install-dir"]
        revision = buildData[module]["last-build-rev"]
        execPath = f"{installDir}/bin/{executable}"
        
        if not os.path.exists(execPath):
            print(f"Program \"{executable}\" does not exist.")
            print("Try to set executable name with -e option.")
            exit(127)  # Command not found
        
        script = textwrap.dedent(f"""\
        #!/bin/sh
        
        # Set up environment variables (dot command)
        . "{buildDir}/prefix.sh";
        . "{extraRunEnv}"
        
        # Launch the program with optional arguments.
        if [ "{int(optFork)}" = 1 ]; then
            setsid -f "{execPath}" $@
        else
            "{execPath}" $@
        fi
        """)
        
        # Print run information
        Debug().note(
            "#" * 80, "\n",
            f"Module:             {module}\n",
            f"Executable          {executable}\n",
            f"Revision:           {revision}\n",
            f"""Arguments:          {" ".join(args)}\n""",
            "#" * 80, "\n",
            "\n"
        )
        
        if Debug().pretending():
            exit(0)
        
        try:
            # Instead of embedding module_args in shell script with string interpolation, pass
            # them as arguments of the script. Let the shell handle the list through "$@",
            # so it will do the quoting on each one of them.
            #
            # Run the script with sh options specification:
            #                               sh     -c command_string    command_name       $1 $2 $3...
            os.execv("/bin/sh", ["/bin/sh", "-c", script, "kde-builder run script"] + args)
        except Exception as e:
            # If we get to here, that sucks, but don't continue.
            Debug().error(f"Error executing {executable}: {e}")
            exit(1)
