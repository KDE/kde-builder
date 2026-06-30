/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#include "%{ProjectNameLC}window.h"

#include <QLabel>
#include <QTest>

class %{ProjectName}WindowTest : public QObject
{
    Q_OBJECT

private Q_SLOTS:
    void testConstruction()
    {
        %{ProjectName}Window window;

        // The form is loaded into a central widget.
        QVERIFY(window.centralWidget() != nullptr);

        // The "label" widget from the .ui form shows the greeting.
        QLabel *label = window.findChild<QLabel *>(QStringLiteral("label"));
        QVERIFY(label != nullptr);
        QCOMPARE(label->text(), QStringLiteral("Hello world!"));
    }
};

QTEST_MAIN(%{ProjectName}WindowTest)

#include "%{ProjectNameLC}windowtest.moc"
