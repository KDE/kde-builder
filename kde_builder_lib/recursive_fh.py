# SPDX-FileCopyrightText: 2012, 2014 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2016 David Faure <faure@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import fileinput
import os
import re
import textwrap
from typing import TYPE_CHECKING

from .kb_exception import ConfigError
from .debug import KBLogger

if TYPE_CHECKING:
    from .build_context import BuildContext

logger_var_subst = KBLogger.getLogger("variables_substitution")
logger_app = KBLogger.getLogger("application")


class RecursiveFH:
    """
    Handles the recursive (using "include" lines) reading of config file.
    """

    # TODO: Replace make_exception with appropriate croak_* function.
    def __init__(self, rcfile: str, ctx: BuildContext):
        self.filehandles: list[fileinput.FileInput] = []  # Stack of filehandles to read
        self.filenames: list[str] = []  # Corresponding stack of filenames (full paths)
        self.base_path: list[str] = []  # Base directory path for relative includes
        self.current: fileinput.FileInput | None = None  # Current filehandle to read
        self.current_fn: str | None = None  # Current filename
        self.ctx = ctx

        self.push_base_path(os.path.dirname(rcfile))  # rcfile should already be absolute

    def add_file(self, fh: fileinput.FileInput, fn: str) -> None:
        """
        Add a new filehandle to read config data from.

        This should be called in conjunction with push_base_path to allow for recursive
        includes from different folders to maintain the correct notion of the current
        cwd at each recursion level.
        """
        self.filehandles.append(fh)
        self.filenames.append(fn)
        self.set_current_file(fh, fn)

    def pop_filehandle(self) -> None:
        self.filehandles.pop()
        self.filenames.pop()
        new_fh = self.filehandles[-1] if self.filehandles else None
        new_filename = self.filenames[-1] if self.filenames else None
        self.set_current_file(new_fh, new_filename)

    def current_filehandle(self) -> fileinput.FileInput | None:
        return self.current

    def current_filename(self) -> str | None:
        return self.current_fn

    def set_current_file(self, fh: fileinput.FileInput, fn: str) -> None:
        self.current = fh
        self.current_fn = fn

    def push_base_path(self, base_path: str) -> None:
        """
        Set the base directory to use for any future encountered include entries that use relative notation, and saves the existing base path (as on a stack).

        Use in conjunction with add_file, and use pop_filehandle and pop_base_path
        when done with the filehandle.
        """
        self.base_path.append(base_path)

    def pop_base_path(self) -> str:
        """
        See above.
        """
        return self.base_path.pop()

    def current_base_path(self) -> str:
        """
        Return the current base path to use for relative include declarations.
        """
        cur_base = self.pop_base_path()
        self.push_base_path(cur_base)
        return cur_base

    def read_line(self) -> str | None:
        """
        Read the next line of input and return it.

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
            fh = self.current_filehandle()

            # Sanity check since different methods might try to read same file reader
            if fh is None:
                return None

            if not (line := fh.readline()):
                self.pop_filehandle()
                self.pop_base_path()

                fh = self.current_filehandle()
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
                    raise ConfigError(f"Unable to handle file include \"{line}\" from {self.current_fn}:{fh.filelineno()}")

                # Existing configurations (before 2023 December) may have pointed to the build-include files located in root of project
                # Warn those users to update the path, and automatically map to new location
                # TODO remove this check after May 2024
                if filename.endswith("-build-include"):
                    filename = re.sub(r"-build-include$", ".ksb", filename)  # replace the ending "-build-include" with ".ksb"
                    filename = re.sub(r".*/([^/]+)$", r"${module-definitions-dir}/\1", filename)  # extract the file name (after the last /), and append it to "${module-definitions-dir}/" string
                    logger_app.warning(textwrap.dedent(f"""\
                    y[Warning:] The include line defined in {self.current_fn}:{fh.filelineno()} uses an old path to build-include file.
                    The module-definitions files are now located in repo-metadata.
                    The configuration file is intended to only have this include line (please manually edit your config):
                        include ${{module-definitions-dir}}/kf6-qt6.ksb
                    Alternatively, you can regenerate the config with --generate-config option.
                    Mapping this line to "include {filename}"
                    """))
                if "data/build-include" in filename:
                    filename = re.sub(r".*/data/build-include/([^/]+)$", r"${module-definitions-dir}/\1", filename)  # extract the file name (after the last /), and append it to "${module-definitions-dir}/" string
                    logger_app.warning(textwrap.dedent(f"""\
                    y[Warning:] The include line defined in {self.current_fn}:{fh.filelineno()} uses an old path with data/build-include.
                    The module-definitions files are now located in repo-metadata.
                    The configuration file is intended to only have this include line (please manually edit your config):
                        include ${{module-definitions-dir}}/kf6-qt6.ksb
                    Alternatively, you can regenerate the config with --generate-config option.
                    Mapping this line to "include {filename}"
                    """))

                option_re = re.compile(r"\$\{([a-zA-Z0-9-_]+)}")  # Example of matched string is "${option-name}" or "${_option-name}".
                ctx = self.ctx

                # Replace reference to global option with their value.
                if re.findall(option_re, filename):
                    sub_var_name = re.findall(option_re, filename)[0]
                else:
                    sub_var_name = None

                while sub_var_name:
                    sub_var_value = ctx.get_option(sub_var_name) or ""
                    if not ctx.has_option(sub_var_name):
                        logger_var_subst.warning(f" *\n * WARNING: {sub_var_name} used in {self.current_fn}:{fh.filelineno()} is not set in global context.\n *")

                    logger_var_subst.debug(f"Substituting ${sub_var_name} with {sub_var_value}")

                    filename = re.sub(r"\$\{" + sub_var_name + r"}", sub_var_value, filename)

                    # Replace other references as well.  Keep this RE up to date with
                    # the other one.
                    sub_var_name = re.findall(option_re, filename)[0] if re.findall(option_re, filename) else None

                new_fh = None
                prefix = self.current_base_path()

                if filename.startswith("~/"):
                    filename = re.sub(r"^~", os.getenv("HOME"), filename)  # Tilde-expand
                if not filename.startswith("/"):
                    filename = f"{prefix}/{filename}"

                try:
                    # new_fh = open(filename, "r")  # cannot count line numbers
                    # new_fh = fileinput.input(files=filename, mode="r")  # can count line numbers, but cannot open multiple instances. Supports throwing exceptions.
                    new_fh = fileinput.FileInput(files=filename, mode="r")  # can count line numbers, can open multiple instances. Does not support throwing exceptions.
                    if not os.path.exists(filename):  # so we throw exception manually
                        raise FileNotFoundError
                except IOError:
                    raise ConfigError(f"Unable to open file \"{filename}\" which was included from {self.current_fn}:{fh.filelineno()}")

                prefix = os.path.dirname(filename)  # Recalculate base path
                self.add_file(new_fh, filename)
                self.push_base_path(prefix)

                continue
            else:
                return line
