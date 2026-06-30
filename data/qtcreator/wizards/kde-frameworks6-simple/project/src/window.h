/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#ifndef %{ProjectNameUC}WINDOW_H
#define %{ProjectNameUC}WINDOW_H

#include "ui_%{ProjectNameLC}.h"

#include <QMainWindow>

/**
 * This class serves as the main window for %{ProjectName}.  It handles the
 * menus, toolbars and status bars.
 *
 * @short Main window class
 * @author %{Author} <%{Email}>
 * @version %{Version}
 */
class %{ProjectName}Window : public QMainWindow
{
    Q_OBJECT
public:
    /**
     * Default Constructor
     */
    %{ProjectName}Window();

    /**
     * Default Destructor
     */
    ~%{ProjectName}Window() override;

private:
    // this is the name of the root widget inside our Ui file
    // you can rename it in designer and then change it here
    Ui::mainWidget m_ui;
};

#endif // %{ProjectNameUC}WINDOW_H
