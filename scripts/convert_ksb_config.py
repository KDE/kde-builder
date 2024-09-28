#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Convert the config from ksb format to the yaml format.
"""

import sys
from typing import TextIO
import re
import yaml


class KSBParser:
    """
    Read the config in legacy ksb format.
    """

    @staticmethod
    def read_ksb_file(config_path: str) -> dict:
        """
        Read in the settings from the configuration.

        Args:
            config_path: Full path of the config file to read from.
        """
        ret_dict = {}
        rcfile = config_path
        fh = open(config_path, "r")

        while line := fh.readline():
            line = re.sub(r"#.*$", "", line)  # Remove comments
            line = re.sub(r"^\s+", "", line)  # Remove leading whitespace
            if not line.strip():
                continue  # Skip blank lines

            if re.match(r"^global\s*$", line):
                key = "global"
            elif match := re.match(r"^(options|module)\s+([-/.\w]+)\s*$", line):  # Get modulename (has dash, dots, slashes, or letters/numbers)
                key = match.group(1) + " " + match.group(2)
            elif match := re.match(r"^module-set\s*([-/.\w]+)?\s*$", line):
                if match.group(1):
                    key = "module-set " + match.group(1)
                else:
                    key = "module-set " + f"Unnamed module-set at {rcfile}"  # module_set_name may be blank (because the capture group is optional)
            elif re.match(r"^\s*include\s+\S", line):
                line = line.rstrip("\n")
                match = re.match(r"^\s*include\s+(.+?)\s*$", line)
                filename = ""
                if match:
                    filename = match.group(1)
                filename = filename.replace("${module-definitions-dir}", "${build-configs-dir}")\
                    .replace("kf5-qt5.ksb", "kde5.yaml")\
                    .replace("kf6-qt6.ksb", "kde6.yaml")\
                    .replace("kf${_ver}-qt${_ver}.ksb", "kde${_ver}.yaml")\
                    .replace(".ksb", ".yaml")
                key = "include " + filename
                ret_dict[key] = ""  # use empty line as a value
                continue  # do not expect "end" marker after include line.
            else:
                print(f"Invalid configuration file {rcfile}!")
                print(f"Expecting a start of module section.")
                raise ValueError("Ungrouped/Unknown option")

            node = KSBParser._read_ksb_node(fh, rcfile)
            if key in ret_dict:
                msg = f"Duplicate entry \"{key}\" found in {rcfile}."
                if key.startswith("options "):
                    msg += " Note that \"options\" can be duplicated only in _different_ files."
                raise ValueError(msg)
            ret_dict[key] = node

        fh.close()
        return ret_dict

    @staticmethod
    def _read_ksb_node(file_handler: TextIO, file_name: str) -> dict:
        """
        Read in the options of the node (a section that is terminated with "end" word) from ksb file and construct dict.

        Args:
            file_handler: A file handle to read from.
            file_name: A full path for file name that is read.
        """
        end_re = re.compile(r"^\s*end")

        ret_dict = {}
        # Read in each option
        line = KSBParser._read_next_logical_line(file_handler)
        while line and not re.search(end_re, line):

            # Sanity check, make sure the section is correctly terminated
            if re.match(r"^(module\b|options\b)", line):
                print(f"Invalid configuration file {file_name}\nAdd an \"end\" before starting a new module.\n")
                raise ConfigError(f"Invalid file {file_name}")

            option, value = KSBParser._split_option_and_value(line)
            ret_dict[option] = value
            line = KSBParser._read_next_logical_line(file_handler)

        return ret_dict

    @staticmethod
    def _read_next_logical_line(file_reader: TextIO) -> str | None:
        """
        Read a "line" from a file.

        This line is stripped of comments and extraneous whitespace. Also, backslash-continued multiple lines are merged into a single line.

        Args:
            file_reader: The reference to the filehandle to read from.

        Returns:
             The text of the line.
        """
        line = file_reader.readline()
        while line:
            # Remove trailing newline
            line = line.rstrip("\n")

            # Replace \ followed by optional space at EOL and try again.
            if re.search(r"\\\s*$", line):
                line = re.sub(r"\\\s*$", "", line)
                line += file_reader.readline()
                continue

            if re.search(r"#.*$", line):
                line = re.sub(r"#.*$", "", line)  # Remove comments
            if re.match(r"^\s*$", line):
                line = file_reader.readline()
                continue  # Skip blank lines

            return line
        return None

    @staticmethod
    def _split_option_and_value(input_line: str) -> tuple:
        """
        Take an input line, and extract it into an option name and value.

        Args:
            input_line: The line to split.

        Returns:
             Tuple (option-name, option-value)
        """
        # The option is the first word, followed by the
        # flags on the rest of the line.  The interpretation
        # of the flags is dependent on the option.
        pattern = re.compile(
            r"^\s*"  # Find all spaces
            r"([-\w]+)"  # First match, alphanumeric, -, and _
            # (?: ) means non-capturing group, so (.*) is $value
            # So, skip spaces and pick up the rest of the line.
            r"(?:\s+(.*))?$"
        )

        match = re.match(pattern, input_line)
        option = match.group(1)
        value = match.group(2) or ""

        value = value.strip()

        return option, value


if __name__ == "__main__":
    ksb_file = sys.argv[1]
    yaml_file = sys.argv[2]
    print(f"Converting {ksb_file} to {yaml_file}")

    config_content = KSBParser.read_ksb_file(ksb_file)

    # # Create a new dictionary with the new key-value pair at the beginning
    # config_content = {"config-version": 2, **config_content}

    # Replace "true" and "false" strings to real boolean values
    for node in config_content:
        if not isinstance(config_content[node], dict):
            continue  # "include" lines are not dicts
        for option, value in config_content[node].items():
            if value == "true":
                config_content[node][option] = True
            if value == "false":
                config_content[node][option] = False

    # Rename entries: "module" -> "project"; "module-set" -> "group", "options" -> "override".
    old_keys = list(config_content.keys())
    for node in old_keys:
        new_name = None
        if node.startswith("module "):
            new_name = "project " + node.removeprefix("module ")
        if node.startswith("module-set "):
            new_name = "group " + node.removeprefix("module-set ")
        if node.startswith("options "):
            new_name = "override " + node.removeprefix("options ")

        # store the recognized node under new name, and remove old name
        if new_name:
            config_content[new_name] = config_content[node]
            del config_content[node]

    # Rename "use-modules" -> "use-projects"; "ignore-modules" -> "ignore-projects". Listify/dictify some options value.
    old_keys = list(config_content.keys())
    for node in old_keys:
        if not isinstance(config_content[node], dict):
            continue  # "include" lines are not dicts
        old_item_keys = list(config_content[node].keys())
        for option in old_item_keys:
            if option == "use-modules":
                config_content[node]["use-projects"] = config_content[node]["use-modules"].split(" ")
                del config_content[node]["use-modules"]
            if option == "ignore-modules":
                config_content[node]["ignore-projects"] = config_content[node]["ignore-modules"].split(" ")
                del config_content[node]["ignore-modules"]
            if option == "set-env":
                value = config_content[node]["set-env"]
                name, val = value.split(" ", maxsplit=1)
                config_content[node]["set-env"] = {name: val}


    class MyDumper(yaml.SafeDumper):  # noqa: D101
        # https://github.com/yaml/pyyaml/issues/127#issuecomment-525800484
        # HACK: insert blank lines between top-level objects
        # inspired by https://stackoverflow.com/a/44284819/3786245
        def write_line_break(self, data=None):
            super().write_line_break(data)

            if len(self.indents) == 1:
                super().write_line_break()

        # https://stackoverflow.com/a/39681672/7869636
        def increase_indent(self, flow=False, indentless=False):
            return super(MyDumper, self).increase_indent(flow, False)

    # Finally, export the resulting yaml file
    with open(yaml_file, "w") as file:
        yaml.dump(config_content, file, Dumper=MyDumper, sort_keys=False)
    pass
