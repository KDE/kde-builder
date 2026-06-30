/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#include "%{ProjectNameLC}window.h"

%{ProjectName}Window::%{ProjectName}Window()
    : QMainWindow()
{
    QWidget *widget = new QWidget(this);
    setCentralWidget(widget);
    m_ui.setupUi(widget);
}

%{ProjectName}Window::~%{ProjectName}Window()
{
}

#include "moc_%{ProjectNameLC}window.cpp"
