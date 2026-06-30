/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#include "greeter.h"

#include <KLocalizedString>

Greeter::Greeter(QObject *parent)
    : QObject(parent)
{
}

QString Greeter::greeting() const
{
    return i18n("Hello from %1!", QStringLiteral("%{ProjectName}"));
}

#include "moc_greeter.cpp"
