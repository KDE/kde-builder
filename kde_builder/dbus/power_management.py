# SPDX-FileCopyrightText: 2026 Benjamin Port <benjamin.port@kde.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from sdbus import DbusInterfaceCommon
from sdbus import DbusUnprivilegedFlag
from sdbus import dbus_method


class PowerManagementInhibitInterface(
    DbusInterfaceCommon,
    interface_name="org.freedesktop.PowerManagement.Inhibit",
):
    """
    DBus interface for inhibiting power management.
    """

    @dbus_method(
        input_signature="ss",
        result_signature="u",
        flags=DbusUnprivilegedFlag,
    )
    def inhibit(
        self,
        application: str,
        reason: str,
    ) -> int:
        raise NotImplementedError
