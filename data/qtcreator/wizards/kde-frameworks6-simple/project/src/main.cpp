/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

// application header
#include "%{ProjectNameLC}window.h"

// KF headers
#include <KAboutData>
#include <KLocalizedString>

// Qt headers
#include <QApplication>
#include <QCommandLineParser>
#include <QIcon>

int main(int argc, char **argv)
{
    QApplication application(argc, argv);

    KLocalizedString::setApplicationDomain("%{ProjectNameLC}");

    KAboutData aboutData(QStringLiteral("%{ProjectNameLC}"),
                         i18n("%{ProjectName}"),
                         QStringLiteral("%{Version}"),
                         i18n("A Simple Application written with KDE Frameworks"),
                         KAboutLicense::GPL,
                         i18n("Copyright %{CurrentYear}, %{Author} <%{Email}>"));

    aboutData.addAuthor(i18n("%{Author}"),i18n("Author"), QStringLiteral("%{Email}"));
    aboutData.setOrganizationDomain("example.org");
    aboutData.setDesktopFileName(QStringLiteral("org.example.%{ProjectNameLC}"));

    KAboutData::setApplicationData(aboutData);
    application.setWindowIcon(QIcon::fromTheme(QStringLiteral("%{ProjectNameLC}")));

    QCommandLineParser parser;
    aboutData.setupCommandLine(&parser);

    parser.process(application);
    aboutData.processCommandLine(&parser);

    %{ProjectName}Window *mainWindow = new %{ProjectName}Window;
    mainWindow->show();

    return application.exec();
}
