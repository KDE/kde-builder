/*
    SPDX-License-Identifier: LicenseRef-KDE-Accepted-GPL
    SPDX-FileCopyrightText: %{CurrentYear} %{Author} <%{Email}>
*/

#ifndef %{ProjectNameUC}WINDOW_H
#define %{ProjectNameUC}WINDOW_H

#include <KXmlGuiWindow>

#include "ui_settings.h"
#include "%{ProjectName}Settings.h"

class %{ProjectName}View;

/**
 * This class serves as the main window for %{ProjectNameLC}.  It handles the
 * menus, toolbars and status bars.
 *
 * @short Main window class
 * @author %{Author} <%{Email}>
 * @version %{Version}
 */
class %{ProjectName}Window : public KXmlGuiWindow
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

private Q_SLOTS:
    /**
     * Create a new window
     */
    void fileNew();

    /**
     * Open the settings dialog
     */
    void settingsConfigure();

private:
    // this is the name of the root widget inside our Ui file
    // you can rename it in designer and then change it here
    Ui::Settings m_settings;
    QAction *m_switchAction;
    %{ProjectName}View *m_%{ProjectNameLC}View;
};

#endif // %{ProjectNameUC}WINDOW_H
