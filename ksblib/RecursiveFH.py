import textwrap
import os
import re
import fileinput
from .Util.Conditional_Type_Enforced import conditional_type_enforced

from .BuildException import BuildException
# from .Util import Util
from .Debug import Debug


@conditional_type_enforced
class RecursiveFH:
    # TODO: Replace make_exception with appropriate croak_* function.
    def __init__(self, rcfile, ctx):
        self.filehandles = []  # Stack of filehandles to read
        self.filenames = []  # Corresponding tack of filenames (full paths)
        self.base_path = []  # Base directory path for relative includes
        self.current = None  # Current filehandle to read
        self.current_fn = None  # Current filename
        self.ctx = ctx
        
        self.pushBasePath(os.path.dirname(rcfile))  # rcfile should already be absolute
    
    def addFile(self, fh, fn) -> None:
        """
        Adds a new filehandle to read config data from.
        
        This should be called in conjunction with pushBasePath to allow for recursive
        includes from different folders to maintain the correct notion of the current
        cwd at each recursion level.
        """
        self.filehandles.append(fh)
        self.filenames.append(fn)
        self.setCurrentFile(fh, fn)
    
    def popFilehandle(self) -> None:
        self.filehandles.pop()
        self.filenames.pop()
        newFh = self.filehandles[-1] if self.filehandles else None
        newFilename = self.filenames[-1] if self.filenames else None
        self.setCurrentFile(newFh, newFilename)
    
    def currentFilehandle(self):
        return self.current
    
    def currentFilename(self):
        return self.current_fn
    
    def setCurrentFile(self, fh, fn) -> None:
        self.current = fh
        self.current_fn = fn
    
    def pushBasePath(self, base_path) -> None:
        """
        Sets the base directory to use for any future encountered include entries
        that use relative notation, and saves the existing base path (as on a stack).
        Use in conjunction with addFile, and use popFilehandle and popBasePath
        when done with the filehandle.
        """
        self.base_path.append(base_path)
    
    def popBasePath(self):
        """
        See above
        """
        return self.base_path.pop()
    
    def currentBasePath(self):
        """
        Returns the current base path to use for relative include declarations.
        """
        curBase = self.popBasePath()
        self.pushBasePath(curBase)
        return curBase
    
    def readLine(self) -> str | None:
        """
        Reads the next line of input and returns it.
        If a line of the form "include foo" is read, this function automatically
        opens the given file and starts reading from it instead. The original
        file is not read again until the entire included file has been read. This
        works recursively as necessary.
        
        No further modification is performed to returned lines.
        
        None is returned on end-of-file (but only of the initial filehandle, not
        included files from there)
        """
        
        while True:  # READLINE
            line = None
            fh = self.currentFilehandle()
            
            # Sanity check since different methods might try to read same file reader
            if fh is None:
                return None
            
            if not (line := fh.readline()):
                self.popFilehandle()
                self.popBasePath()
                
                fh = self.currentFilehandle()
                if not fh:
                    return None
                
                continue
            elif re.match(r"^\s*include\s+\S", line):
                # Include found, extract file name and open file.
                line = line.rstrip("\n")
                match = re.match(r"^\s*include\s+(.+?)\s*$", line)
                filename = None
                if match:
                    filename = match.group(1)
                
                if not filename:
                    raise BuildException.make_exception("Config", f"Unable to handle file include '{line}' from {self.current_fn}:{fh.filelineno()}")
                
                # Existing configurations (before 2023 December) may have pointed to the build-include files located in root of project
                # Warn those users to update the path, and automatically map to new location
                # TODO remove this check after May 2024
                if filename.endswith("-build-include"):
                    filename = re.sub(r"-build-include$", ".ksb", filename)  # replace the ending "-build-include" with ".ksb"
                    filename = re.sub(r".*/([^/]+)$", r"${module-definitions-dir}/\1", filename)  # extract the file name (after the last /), and append it to "${module-definitions-dir}/" string
                    Debug().warning(textwrap.dedent(f"""\
                    y[Warning:] The include line defined in {self.current_fn}:{fh.filelineno()} uses an old path to build-include file.
                    The module-definitions files are now located in repo-metadata.
                    The configuration file is intended to only have this include line (please manually edit your config):
                        include ${{module-definitions-dir}}/kf6-qt6.ksb
                    Alternatively, you can regenerate the config with --generate-config option.
                    Mapping this line to "include {filename}"
                    """))
                if "data/build-include" in filename:
                    filename = re.sub(r".*/data/build-include/([^/]+)$", r"${module-definitions-dir}/\1", filename)  # extract the file name (after the last /), and append it to "${module-definitions-dir}/" string
                    Debug().warning(textwrap.dedent(f"""\
                    y[Warning:] The include line defined in {self.current_fn}:{fh.filelineno()} uses an old path with data/build-include.
                    The module-definitions files are now located in repo-metadata.
                    The configuration file is intended to only have this include line (please manually edit your config):
                        include ${{module-definitions-dir}}/kf6-qt6.ksb
                    Alternatively, you can regenerate the config with --generate-config option.
                    Mapping this line to "include {filename}"
                    """))
                
                optionRE = re.compile(r"\$\{([a-zA-Z0-9-_]+)}")  # Example of matched string is "${option-name}" or "${_option-name}".
                ctx = self.ctx
                
                # Replace reference to global option with their value.
                if re.findall(optionRE, filename):
                    sub_var_name = re.findall(optionRE, filename)[0]
                else:
                    sub_var_name = None
                
                while sub_var_name:
                    sub_var_value = ctx.getOption(sub_var_name) or ""
                    if not ctx.hasOption(sub_var_name):
                        Debug().warning(f" *\n * WARNING: {sub_var_name} used in {self.current_fn}:{fh.filelineno()} is not set in global context.\n *")
                    
                    Debug().debug(f"Substituting ${sub_var_name} with {sub_var_value}")
                    
                    filename = re.sub(r"\$\{" + sub_var_name + r"}", sub_var_value, filename)
                    
                    # Replace other references as well.  Keep this RE up to date with
                    # the other one.
                    sub_var_name = re.findall(optionRE, filename)[0] if re.findall(optionRE, filename) else None
                
                newFh = None
                prefix = self.currentBasePath()
                
                if filename.startswith("~/"):
                    filename = re.sub(r"^~", os.getenv("HOME"), filename)  # Tilde-expand
                if not filename.startswith("/"):
                    filename = f"{prefix}/{filename}"
                
                try:
                    # newFh = open(filename, "r")  # cannot count line numbers
                    # newFh = fileinput.input(files=filename, mode="r")  # can count line numbers, but cannot open multiple instances. Supports throwing exceptions.
                    newFh = fileinput.FileInput(files=filename, mode="r")  # can count line numbers, can open multiple instances. Does not support throwing exceptions.
                    if not os.path.exists(filename):  # so we throw exception manually
                        raise FileNotFoundError
                except IOError:
                    raise BuildException.make_exception("Config", f"Unable to open file '{filename}' which was included from {self.current_fn}:{fh.filelineno()}")
                
                prefix = os.path.dirname(filename)  # Recalculate base path
                self.addFile(newFh, filename)
                self.pushBasePath(prefix)
                
                continue
            else:
                return line
