# SPDX-FileCopyrightText: 2012, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Handles the "phases" for kde-builder, e.g. a simple list of phases, and
methods to add, clear, or filter out phases. Meant to be assigned to a
:class:`Module`.

Example:
::

    phases = PhaseList()
    if phases.has("buildsystem"):
        mod.createBuildSystem()
    if ctx.getOption("build-only"):
        phases.filterOutPhase("update")
"""

from __future__ import annotations


class PhaseList:
    def __init__(self, phases: list[str] | None = None):
        """
        Constructs a new phase list, with the provided list of phases or
        a default set if none are provided.
        ::

            phases1 = PhaseList() # default phases
            print("phases are " + ", ".join(phases1.phaselist))

            phases2 = PhaseList(["update", "test", "install"])
        """
        if not phases:
            phases = ["update", "build", "install"]
        self.phaselist = phases

    def filterOutPhase(self, phase: str) -> None:
        """
        Removes the given phase from the list, if present.
        """
        self.phaselist = [item for item in self.phaselist if item != phase]

    def addPhase(self, phase: str) -> None:
        """
        Adds the given phase to the phase list at the end.

        This is probably a misfeature; use insert at index to add the phase
        in the right spot if it's not at the end.
        """
        if not self.has(phase):
            self.phaselist.append(phase)

    def has(self, phase: str) -> bool:
        """
        Returns true if the given phase is in the phase list.
        """
        return any(element == phase for element in self.phaselist)

    def reset_to(self, args: list[str]) -> None:
        """
        Clears the existing list of phases and resets it to the provided list.
        Basically, it is same as __init__, but with mandatory list argument
        """
        self.phaselist = args

    def clear(self) -> None:
        """
        Empties the phase list.
        """
        self.phaselist = []
