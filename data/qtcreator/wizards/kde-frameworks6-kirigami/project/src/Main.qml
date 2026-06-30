// SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
// SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>

import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    title: i18nc("@title:window", "%{ProjectName}")

    width: Kirigami.Units.gridUnit * 30
    height: Kirigami.Units.gridUnit * 25
    minimumWidth: Kirigami.Units.gridUnit * 20
    minimumHeight: Kirigami.Units.gridUnit * 15

    // Greeter is registered by this application's QML module (org.kde.%{ProjectNameLC}).
    Greeter {
        id: greeter
    }

    pageStack.initialPage: Kirigami.Page {
        title: i18nc("@title", "%{ProjectName}")

        Controls.Label {
            anchors.centerIn: parent
            text: greeter.greeting
        }
    }
}
