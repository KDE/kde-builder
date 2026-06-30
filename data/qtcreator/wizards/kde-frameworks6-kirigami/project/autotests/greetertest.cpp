/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#include "greeter.h"

#include <QTest>

class GreeterTest : public QObject
{
    Q_OBJECT

private Q_SLOTS:
    void testGreeting()
    {
        Greeter greeter;

        // Without a loaded translation catalog, i18n() returns the source string
        // with the placeholder substituted.
        QCOMPARE(greeter.greeting(), QStringLiteral("Hello from %{ProjectName}!"));
    }
};

QTEST_GUILESS_MAIN(GreeterTest)

#include "%{ProjectNameLC}greetertest.moc"
