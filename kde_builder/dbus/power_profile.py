# SPDX-FileCopyrightText: 2026 Benjamin Port <benjamin.port@kde.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from sdbus import DbusInterfaceCommon
from sdbus import DbusUnprivilegedFlag
from sdbus import dbus_method


class PowerProfilesInterface(
    DbusInterfaceCommon,
    interface_name="org.freedesktop.UPower.PowerProfiles",
):
    """
    Interface for holding power profiles.
    """

    @dbus_method(
        input_signature="sss",
        result_signature="u",
        flags=DbusUnprivilegedFlag,
    )
    def hold_profile(
        self,
        profile: str,
        reason: str,
        application_id: str,
    ) -> int:
        raise NotImplementedError
