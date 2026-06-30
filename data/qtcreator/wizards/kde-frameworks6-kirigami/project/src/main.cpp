/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#include <KAboutData>
#include <KLocalizedContext>
#include <KLocalizedString>

#if __has_include(<kiconthemes_version.h>)
#include <KIconTheme>
#include <kiconthemes_version.h>
#endif

#include <QApplication>
#include <QCommandLineParser>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>

using namespace Qt::StringLiterals;

int main(int argc, char *argv[])
{
#if defined(KICONTHEMES_VERSION) && KICONTHEMES_VERSION >= QT_VERSION_CHECK(6, 3, 0)
    KIconTheme::initTheme();
#endif

    QApplication application(argc, argv);

    KLocalizedString::setApplicationDomain("%{ProjectNameLC}");
    QCoreApplication::setOrganizationName(u"KDE"_s);

    KAboutData aboutData(QStringLiteral("%{ProjectNameLC}"),
                         i18n("%{ProjectName}"),
                         QStringLiteral("%{Version}"),
                         i18n("A Kirigami application written with KDE Frameworks"),
                         KAboutLicense::GPL,
                         i18n("Copyright %{CurrentYear}, %{Author} <%{Email}>"));
    aboutData.addAuthor(i18n("%{Author}"), i18n("Author"), QStringLiteral("%{Email}"));
    aboutData.setOrganizationDomain("kde.org");
    aboutData.setDesktopFileName(QStringLiteral("org.kde.%{ProjectNameLC}"));

    KAboutData::setApplicationData(aboutData);
    QApplication::setWindowIcon(QIcon::fromTheme(QStringLiteral("%{ProjectNameLC}")));

    if (qEnvironmentVariableIsEmpty("QT_QUICK_CONTROLS_STYLE")) {
        QQuickStyle::setStyle(u"org.kde.desktop"_s);
        QQuickStyle::setFallbackStyle(u"Fusion"_s);
    }

    QCommandLineParser parser;
    aboutData.setupCommandLine(&parser);
    parser.process(application);
    aboutData.processCommandLine(&parser);

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextObject(new KLocalizedContext(&engine));
    engine.loadFromModule("org.kde.%{ProjectNameLC}", u"Main"_s);

    if (engine.rootObjects().isEmpty()) {
        return -1;
    }

    return application.exec();
}
