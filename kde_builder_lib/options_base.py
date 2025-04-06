# SPDX-FileCopyrightText: 2015, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING

from .kb_exception import SetOptionError
from .util.util import Util

if TYPE_CHECKING:
    from .build_context import BuildContext


class OptionsBase:
    """
    Encapsulates generic option-handling tasks for kde-builder.

    Used to implement common functions within :class:`BuildContext`, :class:`Module`, and
    :class:`ModuleSet`.

    This class is mostly used to encapsulate common code for handling module and
    module-set options, for use by major subclasses.

    The code in this class simply gets/sets options. To parse options and determine
    what options to set, see :class:`Application` and its friends.
    """

    def __init__(self, ctx: BuildContext | None = None):
        # We don't directly bless the options dict so that subclasses can
        # use this base dict directly (as long as they don't overwrite
        # "options", of course).
        self.options = {"set-env": {}}
        self.ctx = ctx

    def has_option(self, key: str) -> bool:
        """
        Return true if the given option has been set for this module.

        Use `get_option` to return the actual value in this case.
        """
        return key in self.options.keys()

    def get_option(self, key: str, level_limit="") -> str | dict | list | bool:
        """
        Return the value of the given option. If no such option is present, returns an empty string.

        Note that :class:`Module` has its own, much more involved override of this
        method.

        May return type - example which uses this type:
         list - "#defined-at"
         dict - "git-repository-base"
         bool - "include-dependencies"
         str - almost everything else
        """
        if self.has_option(key):
            return self.options[key]
        return ""

    def set_option(self, opt_name: str, opt_val) -> None:
        """
        Set the given option(s) to the given values.

        For the vast majority of possible options, setting the same option again
        overwrites any previous value. However, for `set-env` options, additional
        option sets instead will **append** to previously-set values.

        If you need to perform special handling based on option values, subclass
        this function, but be sure to call **this** set_option() with the resulting
        set of options (if any are left to set).
        """
        # Special case handling.
        if opt_name == "set-env":
            self._process_set_env_option(opt_val)
            return

        # Special-case handling
        repo_option = "git-repository-base"
        if opt_name == repo_option:
            value = opt_val

            if isinstance(value, dict):
                # The case when we merge the constructed OptionBase module (from the config) into the BuildContext. The type of value is a dict.
                for key in value.keys():
                    self.options[repo_option][key] = value[key]
                return
            else:
                match = re.match(r"^([a-zA-Z0-9_-]+)\s+(.+)$", value)
                repo, url = None, None
                if match:
                    repo, url = match.group(1), match.group(2)

                if not repo or not url:
                    raise SetOptionError(repo_option, f"Invalid git-repository-base setting: {value}")

                dictionary = self.get_option(repo_option)
                if dictionary == "":  # pl2py: in perl they checked if _reference_ was defined (i.e. its id, but not that the hash (dict) is empty itself).
                    dictionary = {}
                dictionary[repo] = url
                self.options[repo_option] = dictionary
                return

        if opt_name == "num-cores-low-mem":
            try:
                int(opt_val)  # any value that can be cast to int.
            except ValueError:  # some string like "auto" is set.
                from .os_support import CoresAndMemorySupport
                opt_val = str(CoresAndMemorySupport.get_num_cores_for_low_memory())

        # Everything else can be dumped straight into our dict.
        self.verify_option_value_type(opt_name, opt_val)
        self.options[opt_name] = opt_val

    def delete_option(self, key: str) -> None:
        """
        Remove the given option (and its value), if present.
        """
        if key in self.options.keys():
            del self.options[key]

    def merge_options_from(self, other) -> None:
        """
        Merge options from the given :class:`OptionsBase`, replacing any options already present (but keeping other existing options).

        Nice to quickly set up an options
        baseline to make small changes afterwards without having to worry about
        aliasing the other module's option set.
        """
        Util.assert_isa(other, OptionsBase)
        new_opts = copy.deepcopy(other.options)
        for opt_name, opt_val in new_opts.items():
            self.set_option(opt_name, opt_val)

    def _process_set_env_option(self, value) -> None:
        """
        Handle setting set-env options.

        Args:
            value: Either a dict (in which case it is simply merged into our
                existing options) or a string value of the option as read from the
                rc-file (which will have the env-var to set as the first item, the
                value for the env-var to take as the rest of the value).
        """
        if isinstance(value, dict):
            for key in value:
                self.options["set-env"][key] = value[key]
        else:
            var, env_value = value.split(" ", maxsplit=1)
            self.options["set-env"][var] = env_value

    def verify_option_value_type(self, option_name, option_value) -> None:
        """
        Ensure we are setting the correct type for value of option.
        """
        if option_name == "ignore-projects":  # when reading the ignore-projects from global node from the config
            if not isinstance(option_value, list):
                raise SetOptionError(option_name, f"Option \"{option_name}\" has invalid value type \"{option_value.__class__.__name__}\", but \"list\" is expected.")
        if self.ctx:
            self.ctx.verify_option_value_type(option_name, option_value)
        else:
            return
