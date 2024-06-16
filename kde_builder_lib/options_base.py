# SPDX-FileCopyrightText: 2015, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
A class that encapsulates generic option-handling tasks for kde-builder, used
to implement common functions within :class:`BuildContext`, :class:`Module`, and
:class:`ModuleSet`.

There is some internal trickery to ensure that program code can override
user-selected options in certain situations, which is why we don't simply
use a dict table directly. These are the so-called "sticky" options, seen
internally as options with a name starting with #.

This class is mostly used to encapsulate common code for handling module and
module-set options, for use by major subclasses.

The code in this class simply gets/sets options. To parse options and determine
what options to set, see :class:`Application` and its friends.
"""

from __future__ import annotations

import copy
import re

from .build_exception import BuildException_Config
from .util.util import Util


class OptionsBase:
    def __init__(self):
        # We don't directly bless the options hash so that subclasses can
        # use this base hash table directly (as long as they don't overwrite
        # 'options', of course.
        self.options = {"set-env": {}}

    def has_sticky_option(self, key: str) -> bool:
        """
        Returns true if the given option has been overridden by a "sticky" option.
        Use `get_option` to return the actual value in this case.
        """
        key = key.removeprefix("#")  # Remove sticky marker.

        if key in ["pretend", "disable-agent-check"]:
            return True
        return True if f"#{key}" in self.options.keys() else False

    def has_option(self, key: str) -> bool:
        """
        Returns true if the given option has been set for this module.
        Use `get_option` to return the actual value in this case.
        """
        return key in self.options.keys()

    def get_option(self, key: str) -> str | dict | list | bool:
        """
        Returns the value of the given option. "Sticky" options are returned in
        preference to this object's own option (this allows you to temporarily
        override an option with a sticky option without overwriting the option
        value). If no such option is present, returns an empty string.

        Note that :class:`Module` has its own, much more involved override of this
        method. Note further that although `None` is not returned directly by
        this method, that it's possible for sticky options to be set to `None` (if
        you're setting sticky option values, it's probably best not to do that).

        May return type - example which uses this type:
         list - "#defined-at"
         dict - "git-repository-base"
         bool - "include-dependencies"
         str - almost everything else
        """

        for el in [f"#{key}", key]:
            if self.has_option(el):
                return self.options[el]
        return ""

    def set_option(self, options: dict) -> None:
        """        
        Sets the given option(s) to the given values.
            self.set_option(options)
        Normally seen as simply:
            self.set_option(option, value)

        For the vast majority of possible options, setting the same option again
        overwrites any previous value. However, for `set-env` options, additional
        option sets instead will **append** to previously-set values.

        If you need to perform special handling based on option values, subclass
        this function, but be sure to call **this** set_option() with the resulting
        set of options (if any are left to set).
        """

        # Special case handling.
        if "set-env" in options.keys():
            self._process_set_env_option(options["set-env"])
            del options["set-env"]

        # Special-case handling
        repoOption = "git-repository-base"
        if repoOption in options:
            value = options[repoOption]

            if isinstance(value, dict):
                # The case when we merge the constructed OptionBase module (from the config) into the BuildContext. The type of $value is a hash (dict).
                for key in value.keys():
                    self.options[repoOption][key] = value[key]
                del options[repoOption]
            else:
                match = re.match(r"^([a-zA-Z0-9_-]+)\s+(.+)$", value)
                repo, url = match.group(1), match.group(2)

                if not repo or not url:
                    raise BuildException_Config(repoOption, f"Invalid git-repository-base setting: {value}")

                dictref = self.get_option(repoOption)
                if dictref == "":  # pl2py: in perl they checked if _reference_ was defined (i.e. its id, but not that the hash is empty itself).
                    dictref = {}
                dictref[repo] = url
                self.options[repoOption] = dictref
                return

        # Everything else can be dumped straight into our hash.
        for option in options:
            self.options[option] = options[option]

    def delete_option(self, key: str) -> None:
        """
        Removes the given option (and its value), if present.
        """
        if key in self.options.keys():
            del self.options[key]

    def merge_options_from(self, other) -> None:
        """
        Merges options from the given :class:`OptionsBase`, replacing any options already
        present (but keeping other existing options). Nice to quickly set up an options
        baseline to make small changes afterwards without having to worry about
        aliasing the other module's option set.
        """
        Util.assert_isa(other, OptionsBase)
        newOpts = copy.deepcopy(other.options)
        self.set_option(newOpts)

    def _process_set_env_option(self, value) -> None:
        """
        Handles setting set-env options.

        Parameters:
            value: Either a dict (in which case it is simply merged into our
                existing options) or a string value of the option as read from the
                rc-file (which will have the env-var to set as the first item, the
                value for the env-var to take as the rest of the value).
        """

        if type(value) is dict:
            for key in value:
                self.options["set-env"][key] = value[key]
        else:
            var, envValue = value.split(" ", maxsplit=1)
            self.options["set-env"][var] = envValue
