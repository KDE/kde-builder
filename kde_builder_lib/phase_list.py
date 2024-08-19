# SPDX-FileCopyrightText: 2012, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations


class PhaseList:
    """
    Handles the "phases" for kde-builder, e.g. a simple list of phases, and methods to add, clear, or filter out phases.

    Meant to be assigned to a :class:`Module`.

    Example:
    ::

        phases = PhaseList()
        if phases.has("build_system"):
            mod.create_build_system()
        if ctx.get_option("build-only"):
            phases.filter_out_phase("update")
    """

    def __init__(self, phases: list[str] | None = None):
        """
        Construct a new phase list, with the provided list of phases or a default set if none are provided.

        ::

            phases1 = PhaseList() # default phases
            print("phases are " + ", ".join(phases1.phaselist))

            phases2 = PhaseList(["update", "test", "install"])
        """
        if not phases:
            phases = ["update", "build", "install"]
        self.phaselist = phases

    def filter_out_phase(self, phase: str) -> None:
        """
        Remove the given phase from the list, if present.
        """
        self.phaselist = [item for item in self.phaselist if item != phase]

    def add_phase(self, phase: str) -> None:
        """
        Add the given phase to the phase list at the end.

        This is probably a misfeature; use insert at index to add the phase
        in the right spot if it's not at the end.
        """
        if not self.has(phase):
            self.phaselist.append(phase)

    def has(self, phase: str) -> bool:
        """
        Return true if the given phase is in the phase list.
        """
        return any(element == phase for element in self.phaselist)

    def reset_to(self, args: list[str]) -> None:
        """
        Clear the existing list of phases and resets it to the provided list.

        Basically, it is same as __init__, but with mandatory list argument
        """
        self.phaselist = args

    def clear(self) -> None:
        """
        Empty the phase list.
        """
        self.phaselist = []
