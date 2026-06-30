/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#ifndef GREETER_H
#define GREETER_H

#include <QObject>
#include <QString>

#include <qqmlregistration.h>

/**
 * A small example backend object, exposed to QML as a type.
 *
 * @short Example C++ backend for %{ProjectName}
 * @author %{Author} <%{Email}>
 */
class Greeter : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString greeting READ greeting CONSTANT)

public:
    explicit Greeter(QObject *parent = nullptr);

    QString greeting() const;
};

#endif // GREETER_H
