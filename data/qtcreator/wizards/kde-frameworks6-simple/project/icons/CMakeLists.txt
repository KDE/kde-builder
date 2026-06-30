set(%{ProjectNameLC}_ICONS
  16-apps-%{ProjectNameLC}.png
  22-apps-%{ProjectNameLC}.png
  32-apps-%{ProjectNameLC}.png
  48-apps-%{ProjectNameLC}.png
)

ecm_install_icons(ICONS ${%{ProjectNameLC}_ICONS} DESTINATION ${KDE_INSTALL_ICONDIR} THEME hicolor)
