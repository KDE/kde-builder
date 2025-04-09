# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING
import yaml

from .kb_exception import ConfigError
from .debug import KBLogger

if TYPE_CHECKING:
    from .build_context import BuildContext


logger_var_subst = KBLogger.getLogger("variables_substitution")
logger_app = KBLogger.getLogger("application")


class RecursiveConfigNodesIterator:
    """
    Iterate over main config nodes, but in place of "include" lines, return nodes from corresponding file.
    """

    def __init__(self, initial_dictionary: dict, rcfile: str, ctx: BuildContext):
        self.context = ctx
        assert os.path.isabs(rcfile)

        self.stack_dictionaries: list[dict] = []
        self.stack_filenames: list[str] = []
        self.stack_indexes: list[int] = []
        self.stack_keys_lists: list[list[str]] = []
        self.stack_base_path: list[str] = [os.path.dirname(rcfile)]  # Base directory path for relative includes.

        self.current_dictionary: dict = initial_dictionary
        self.current_filename: str = rcfile
        self.current_index = 0
        self.current_keys_list: list[str] = list(self.current_dictionary.keys())

    def __iter__(self):
        return self

    def __next__(self):
        from .application import Application

        while True:
            if self.current_index < len(self.current_keys_list):
                node_name = self.current_keys_list[self.current_index]
                node = self.current_dictionary[node_name]
                self.current_index += 1

                if node_name.startswith("include "):
                    # Include found, extract file name and open file.
                    match = re.match(r"^\s*include\s+(.+?)\s*$", node_name)
                    filename = None
                    if match:
                        filename = match.group(1)

                    if not filename:
                        raise ConfigError(f"Unable to handle file include \"{node_name}\" from {self.current_filename}")

                    option_re = re.compile(r"\$\{([a-zA-Z0-9-_]+)}")  # Example of matched string is "${option-name}" or "${_option-name}".
                    ctx = self.context

                    # Replace reference to global option with their value.
                    sub_var_name = found_vars[0] if (found_vars := re.findall(option_re, filename)) else None

                    while sub_var_name:
                        sub_var_value = ctx.get_option(sub_var_name) or ""
                        if not ctx.has_option(sub_var_name):
                            logger_var_subst.warning(f" *\n * WARNING: {sub_var_name} used in {self.current_filename} is not set in global context.\n *")

                        logger_var_subst.debug(f"Substituting ${sub_var_name} with {sub_var_value}")

                        filename = re.sub(r"\$\{" + sub_var_name + r"}", sub_var_value, filename)

                        # Replace other references as well. Keep this RE up to date with the other one.
                        sub_var_name = found_vars[0] if (found_vars := re.findall(option_re, filename)) else None

                    prefix = self.stack_base_path[-1]

                    if filename.startswith("~/"):
                        filename = re.sub(r"^~", os.getenv("HOME"), filename)  # Tilde-expand
                    if not filename.startswith("/"):
                        filename = f"{prefix}/{filename}"

                    try:
                        if not os.path.exists(filename):  # so we throw exception manually
                            raise FileNotFoundError
                        with open(filename, "r") as f:
                            new_config_content = yaml.safe_load(f)
                    except IOError:
                        raise ConfigError(f"Unable to open file \"{filename}\" which was included from {self.current_filename}")

                    self.add_file_to_stack(new_config_content, filename, os.path.dirname(filename))
                    continue
                else:
                    return node_name, node, self.current_filename
            else:
                self.pop_file_from_stack()
                if self.current_dictionary is None:
                    raise StopIteration
                continue

    def add_file_to_stack(self, nodes_dict: dict, filename: str, new_basepath: str) -> None:
        self.stack_dictionaries.append(self.current_dictionary)
        self.stack_filenames.append(self.current_filename)
        self.stack_indexes.append(self.current_index)
        self.stack_keys_lists.append(self.current_keys_list)
        self.stack_base_path.append(self.stack_base_path[-1])

        self.current_dictionary: dict = nodes_dict
        self.current_filename: str = filename
        self.current_index = 0
        self.current_keys_list = list(self.current_dictionary.keys())
        self.stack_base_path.append(new_basepath)

    def pop_file_from_stack(self) -> None:
        self.current_dictionary = self.stack_dictionaries.pop() if len(self.stack_dictionaries) else None
        self.current_filename = self.stack_filenames.pop() if len(self.stack_filenames) else None
        self.current_index = self.stack_indexes.pop() if len(self.stack_indexes) else None
        self.current_keys_list = self.stack_keys_lists.pop() if len(self.stack_keys_lists) else None
        self.stack_base_path.pop()
