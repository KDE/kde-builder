from .Util.Conditional_Type_Enforced import conditional_type_enforced
from functools import cmp_to_key
from typing import Callable


@conditional_type_enforced
class DebugOrderHints:
    """
    This module is motivated by the desire to help the user debug a kde-builder
    failure more easily. It provides support code to rank build failures on a per
    module from 'most' to 'least' interesting, as well as to sort the list of
    (all) failures by their respective rankings. This ranking is determined by
    trying to evaluate whether or not a given build failure fits a number of
    assumptions/heuristics. E.g.: a module which fails to build is likely to
    trigger build failures in other modules that depend on it (because of a
    missing dependency).
    """
    
    @staticmethod
    def _getPhaseScore(phase) -> int:
        """
        Assumption: build & install phases are interesting.
        Install is particularly interesting because that should 'rarely' fail,
        and so if it does there are probably underlying system issues at work.
        
        Assumption: 'test' is opt in and therefore the user has indicated a
        special interest in that particular module?
        
        Assumption: source updates are likely not that interesting due to
        e.g. transient network failure. But it might also indicate something
        more serious such as an unclean git repository, causing scm commands
        to bail.
        """
        
        if phase == "install":
            return 4
        if phase == "test":
            return 3
        if phase == "build":
            return 2
        if phase == "update":
            return 1
        return 0
    
    @staticmethod
    def _make_comparison_func(moduleGraph, extraDebugInfo):
        def _compareDebugOrder(a, b):
            # comparison results uses:
            # -1 if a < b
            # 0 if a == b
            # 1 if a > b
            
            nameA = a.name
            nameB = b.name
            
            # Enforce a strict dependency ordering.
            # The case where both are true should never happen, since that would
            # amount to a cycle, and cycle detection is supposed to have been
            # performed beforehand.
            #
            # Assumption: if A depends on B, and B is broken then a failure to build
            # A is probably due to lacking a working B.
            
            bDependsOnA = moduleGraph[nameA]["votes"].get(nameB, 0)
            aDependsOnB = moduleGraph[nameB]["votes"].get(nameA, 0)
            order = -1 if bDependsOnA else (1 if aDependsOnB else 0)
            
            if order:
                return order
            
            # TODO we could tag explicitly selected modules from command line?
            # If we do so, then the user is probably more interested in debugging
            # those first, rather than 'unrelated' noise from modules pulled in due
            # to possibly overly broad dependency declarations. In that case we
            # should sort explicitly tagged modules next highest, after dependency
            # ordering.
            
            # Assuming no dependency resolution, next favour possible root causes as
            # may be inferred from the dependency tree.
            #
            # Assumption: there may be certain 'popular' modules which rely on a
            # failed module. Those should probably not be considered as 'interesting'
            # as root cause failures in less popuplar dependency trees. This is
            # essentially a mitigation against noise introduced from raw 'popularity'
            # contests (see below).
            
            isRootA = len(moduleGraph[nameA]["deps"]) == 0
            isRootB = len(moduleGraph[nameB]["deps"]) == 0
            
            if isRootA and not isRootB:
                return -1
            if isRootB and not isRootA:
                return 1
            
            # Next sort by 'popularity': the item with the most votes (back edges) is
            # depended on the most.
            #
            # Assumption: it is probably a good idea to debug that one earlier.
            # This would point the user to fixing the most heavily used dependencies
            # first before investing time in more 'exotic' modules
            
            voteA = len(moduleGraph[nameA]["votes"])
            voteB = len(moduleGraph[nameB]["votes"])
            votes = voteB - voteA
            
            if votes:
                return votes
            
            # Try and see if there is something 'interesting' that might e.g. indicate
            # issues with the system itself, preventing a successful build.
            
            phaseA = DebugOrderHints._getPhaseScore(extraDebugInfo["phases"].get(nameA, ""))
            phaseB = DebugOrderHints._getPhaseScore(extraDebugInfo["phases"].get(nameB, ""))
            phase = (phaseB > phaseA) - (phaseB < phaseA)
            
            if phase:
                return phase
            
            # Assumption: persistently failing modules do not prompt the user
            # to act and therefore these are likely not that interesting.
            # Conversely *new* failures are.
            #
            # If we get this wrong the user will likely be on the case anyway:
            # someone does not need prodding if they have been working on it
            # for the past X builds or so already.
            
            failCountA = a.getPersistentOption("failure-count")
            failCountB = b.getPersistentOption("failure-count")
            failCount = (failCountA or 0) - (failCountB or 0)
            
            if failCount:
                return failCount
            
            # If there is no good reason to perfer one module over another,
            # simply sort by name to get a reproducible order.
            # That simplifies autotesting and/or reproducible builds.
            # (The items to sort are supplied as a hash so the order of keys is by
            # definition not guaranteed.)
            
            name = (nameA > nameB) - (nameA < nameB)
            
            return name
        
        return _compareDebugOrder
    
    @staticmethod
    def sortFailuresInDebugOrder(moduleGraph, extraDebugInfo, failuresRef: list) -> list:
        failures = failuresRef
        prioritised = sorted(failures, key=cmp_to_key(DebugOrderHints._make_comparison_func(moduleGraph, extraDebugInfo)))
        return prioritised
