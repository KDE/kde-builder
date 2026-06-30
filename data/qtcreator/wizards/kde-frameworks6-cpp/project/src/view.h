/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#ifndef %{ProjectNameUC}VIEW_H
#define %{ProjectNameUC}VIEW_H

#include "ui_%{ProjectNameLC}view.h"


/**
 * This class serves as the main view for %{ProjectNameLC}.
 *
 * @short Main view class
 * @author %{Author} <%{Email}>
 * @version %{Version}
 */
class %{ProjectName}View : public QWidget
{
    Q_OBJECT
public:
    /**
     * Default Constructor
     */
    explicit %{ProjectName}View(QWidget *parent);

    /**
     * Default Destructor
     */
    ~%{ProjectName}View() override;

public Q_SLOTS:
    void switchColors();
    void handleSettingsChanged();

private:
    // this is the name of the root widget inside our Ui file
    // you can rename it in designer and then change it here
    Ui::%{ProjectName}View m_ui;
};

#endif // %{ProjectNameUC}VIEW_H
