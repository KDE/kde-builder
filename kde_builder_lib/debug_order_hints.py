# SPDX-FileCopyrightText: 2019 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from functools import cmp_to_key
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from module.module import Module


class DebugOrderHints:
    """
    Help the user debug a kde-builder failure more easily.

    It provides support code to rank build failures on a per
    module from "most" to "least" interesting, as well as to sort the list of
    (all) failures by their respective rankings. This ranking is determined by
    trying to evaluate whether a given build failure fits a number of
    assumptions/heuristics. E.g.: a module which fails to build is likely to
    trigger build failures in other modules that depend on it (because of a
    missing dependency).
    """

    @staticmethod
    def _get_phase_score(phase: str) -> int:
        """
        Get phase score.

        Assumption: build & install phases are interesting.
        Install is particularly interesting because that should "rarely" fail,
        and so if it does there are probably underlying system issues at work.

        Assumption: "test" is opt in and therefore the user has indicated a
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
    def _make_comparison_func(module_graph, extra_debug_info):
        def _compare_debug_order(a, b):
            # comparison results uses:
            # -1 if a < b
            # 0 if a == b
            # 1 if a > b

            name_a = a.name
            name_b = b.name

            # Enforce a strict dependency ordering.
            # The case where both are true should never happen, since that would
            # amount to a cycle, and cycle detection is supposed to have been
            # performed beforehand.
            #
            # Assumption: if A depends on B, and B is broken then a failure to build
            # A is probably due to lacking a working B.

            b_depends_on_a = module_graph[name_a]["votes"].get(name_b, 0)
            a_depends_on_b = module_graph[name_b]["votes"].get(name_a, 0)
            order = -1 if b_depends_on_a else (1 if a_depends_on_b else 0)

            if order:
                return order

            # TODO we could tag explicitly selected modules from command line?
            # If we do so, then the user is probably more interested in debugging
            # those first, rather than "unrelated" noise from modules pulled in due
            # to possibly overly broad dependency declarations. In that case we
            # should sort explicitly tagged modules next highest, after dependency
            # ordering.

            # Assuming no dependency resolution, next favour possible root causes as
            # may be inferred from the dependency tree.
            #
            # Assumption: there may be certain "popular" modules which rely on a
            # failed module. Those should probably not be considered as "interesting"
            # as root cause failures in less popuplar dependency trees. This is
            # essentially a mitigation against noise introduced from raw "popularity"
            # contests (see below).

            is_root_a = len(module_graph[name_a]["deps"]) == 0
            is_root_b = len(module_graph[name_b]["deps"]) == 0

            if is_root_a and not is_root_b:
                return -1
            if is_root_b and not is_root_a:
                return 1

            # Next sort by "popularity": the item with the most votes (back edges) is
            # depended on the most.
            #
            # Assumption: it is probably a good idea to debug that one earlier.
            # This would point the user to fixing the most heavily used dependencies
            # first before investing time in more "exotic" modules

            vote_a = len(module_graph[name_a]["votes"])
            vote_b = len(module_graph[name_b]["votes"])
            votes = vote_b - vote_a

            if votes:
                return votes

            # Try and see if there is something "interesting" that might e.g. indicate
            # issues with the system itself, preventing a successful build.

            phase_a = DebugOrderHints._get_phase_score(extra_debug_info["phases"].get(name_a, ""))
            phase_b = DebugOrderHints._get_phase_score(extra_debug_info["phases"].get(name_b, ""))
            phase = (phase_b > phase_a) - (phase_b < phase_a)

            if phase:
                return phase

            # Assumption: persistently failing modules do not prompt the user
            # to act and therefore these are likely not that interesting.
            # Conversely *new* failures are.
            #
            # If we get this wrong the user will likely be on the case anyway:
            # someone does not need prodding if they have been working on it
            # for the past X builds or so already.

            fail_count_a = a.get_persistent_option("failure-count")
            fail_count_b = b.get_persistent_option("failure-count")
            fail_count = (fail_count_a or 0) - (fail_count_b or 0)

            if fail_count:
                return fail_count

            # If there is no good reason to perfer one module over another,
            # simply sort by name to get a reproducible order.
            # That simplifies autotesting and/or reproducible builds.
            # (The items to sort are supplied as a dict so the order of keys is by
            # definition not guaranteed.)

            name = (name_a > name_b) - (name_a < name_b)

            return name

        return _compare_debug_order

    @staticmethod
    def sort_failures_in_debug_order(module_graph, extra_debug_info, failures: list[Module]) -> list[Module]:
        prioritised = sorted(failures, key=cmp_to_key(DebugOrderHints._make_comparison_func(module_graph, extra_debug_info)))
        return prioritised
