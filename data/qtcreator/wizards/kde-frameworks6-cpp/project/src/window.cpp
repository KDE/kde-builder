/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

// application headers
#include "%{ProjectNameLC}window.h"

#include "%{ProjectNameLC}view.h"
#include "%{ProjectNameLC}debug.h"

// KF headers
#include <KActionCollection>
#include <KConfigDialog>


%{ProjectName}Window::%{ProjectName}Window()
    : KXmlGuiWindow()
{
    m_%{ProjectNameLC}View = new %{ProjectName}View(this);
    setCentralWidget(m_%{ProjectNameLC}View);

    KActionCollection* actionCollection = this->actionCollection();
    m_switchAction = actionCollection->addAction(QStringLiteral("switch_action"));
    m_switchAction->setText(i18nc("@action", "Switch Colors"));
    m_switchAction->setIcon(QIcon::fromTheme(QStringLiteral("fill-color")));
    connect(m_switchAction, &QAction::triggered, m_%{ProjectNameLC}View, &%{ProjectName}View::switchColors);

    KStandardAction::openNew(this, SLOT(fileNew()), actionCollection);
    KStandardAction::quit(qApp, SLOT(closeAllWindows()), actionCollection);
    KStandardAction::preferences(this, SLOT(settingsConfigure()), actionCollection);

    setupGUI();
}

%{ProjectName}Window::~%{ProjectName}Window()
{
}

void %{ProjectName}Window::fileNew()
{
    qCDebug(%{ProjectNameUC}) << "%{ProjectName}Window::fileNew()";
    (new %{ProjectName}Window)->show();
}

void %{ProjectName}Window::settingsConfigure()
{
    qCDebug(%{ProjectNameUC}) << "%{ProjectName}Window::settingsConfigure()";
    // The preference dialog is derived from prefs_base.ui
    //
    // compare the names of the widgets in the .ui file
    // to the names of the variables in the .kcfg file
    //avoid to have 2 dialogs shown
    if (KConfigDialog::showDialog(QStringLiteral("settings"))) {
        return;
    }

    KConfigDialog *dialog = new KConfigDialog(this, QStringLiteral("settings"), %{ProjectName}Settings::self());
    QWidget *generalSettingsPage = new QWidget;
    m_settings.setupUi(generalSettingsPage);
    dialog->addPage(generalSettingsPage, i18nc("@title:tab", "General"), QStringLiteral("package_setting"));
    connect(dialog, &KConfigDialog::settingsChanged, m_%{ProjectNameLC}View, &%{ProjectName}View::handleSettingsChanged);
    dialog->setAttribute(Qt::WA_DeleteOnClose);
    dialog->show();
}

#include "moc_%{ProjectNameLC}window.cpp"
