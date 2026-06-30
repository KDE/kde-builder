// SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
// SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>

import QtQuick
import QtTest

TestCase {
    name: "GreetingTests"

    // A plain sanity check, in the spirit of a Qt Quick Test starting point.
    function test_math() {
        compare(2 + 2, 4, "2 + 2 = 4");
    }

    // Build the greeting in QML the same way the C++ backend does, and verify it.
    function test_greeting() {
        const appName = "%{ProjectName}";
        compare("Hello from %1!".arg(appName), "Hello from %{ProjectName}!");
    }
}
