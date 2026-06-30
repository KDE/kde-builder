/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#include "%{ProjectName}Settings.h"

#include <QStandardPaths>
#include <QTest>

class %{ProjectName}SettingsTest : public QObject
{
    Q_OBJECT

private Q_SLOTS:
    void initTestCase()
    {
        // Keep the test from touching the real user configuration.
        QStandardPaths::setTestModeEnabled(true);
    }

    void testDefaults()
    {
        %{ProjectName}Settings *settings = %{ProjectName}Settings::self();

        // These values come from the defaults declared in %{ProjectName}Settings.kcfg.
        QCOMPARE(settings->ageInDays(), 2);
        QCOMPARE(settings->colorBackground(), QColor(Qt::black));
        QCOMPARE(settings->colorForeground(), QColor(Qt::yellow));
    }

    void testColorSwitch()
    {
        %{ProjectName}Settings *settings = %{ProjectName}Settings::self();

        const QColor background = settings->colorBackground();
        const QColor foreground = settings->colorForeground();

        // This mirrors what %{ProjectName}View::switchColors() does.
        settings->setColorBackground(foreground);
        settings->setColorForeground(background);

        QCOMPARE(settings->colorBackground(), foreground);
        QCOMPARE(settings->colorForeground(), background);
    }
};

QTEST_MAIN(%{ProjectName}SettingsTest)

#include "%{ProjectNameLC}settingstest.moc"
