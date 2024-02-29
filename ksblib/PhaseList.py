# SPDX-FileCopyrightText: 2003 - 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2004 - 2024 KDE Contributors (see git history) <community@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

"""
DESCRIPTION

Handles the "phases" for kde-builder, e.g. a simple list of phases, and
methods to add, clear, or filter out phases. Meant to be assigned to a
:class:`Module`.

SYNOPSIS
::

    phases = PhaseList()
    mod.createBuildSystem() if phases.has('buildsystem')
    phases.filterOutPhase('update') if ctx.getOption('build-only')
"""
from __future__ import annotations


class PhaseList:
    def __init__(self, phases: list | None = None):
        """
        Constructs a new phase list, with the provided list of phases or
        a default set if none are provided.
        ::
        
            phases1 = PhaseList() # default phases
            print("phases are " + phases1.phaselist.join(', '))
        
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

    def phases(self, args: list | None = None) -> list:
        """
        If provided a list, clears the existing list of phases and
        resets them to the provided list.
        If not provided a list, returns the list of
        phases without modifying the instance.
        """
        assert args is None or isinstance(args, list)
        if args:
            self.phaselist = args
        return self.phaselist

    def clear(self) -> None:
        """
        Empties the phase list.
        """
        self.phaselist = []
