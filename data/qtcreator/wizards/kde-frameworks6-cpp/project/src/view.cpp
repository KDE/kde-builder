/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

// application headers
#include "%{ProjectNameLC}view.h"

#include "%{ProjectName}Settings.h"
#include "%{ProjectNameLC}debug.h"


%{ProjectName}View::%{ProjectName}View(QWidget *parent)
    : QWidget(parent)
{
    m_ui.setupUi(this);
    handleSettingsChanged();
}

%{ProjectName}View::~%{ProjectName}View()
{
}

void %{ProjectName}View::switchColors()
{
    // switch the foreground/background colors of the label
    QColor color = %{ProjectName}Settings::colorBackground();
    %{ProjectName}Settings::setColorBackground(%{ProjectName}Settings::colorForeground());
    %{ProjectName}Settings::setColorForeground(color);

    handleSettingsChanged();
}

void %{ProjectName}View::handleSettingsChanged()
{
    qCDebug(%{ProjectNameUC}) << "%{ProjectName}View::handleSettingsChanged()";
    QPalette palette = m_ui.templateLabel->palette();
    palette.setColor(QPalette::Window, %{ProjectName}Settings::colorBackground());
    palette.setColor(QPalette::WindowText, %{ProjectName}Settings::colorForeground());
    m_ui.templateLabel->setPalette(palette);

    // i18n : internationalization
    m_ui.templateLabel->setText(i18n("This project is %1 days old", %{ProjectName}Settings::ageInDays()));
}

#include "moc_%{ProjectNameLC}view.cpp"
