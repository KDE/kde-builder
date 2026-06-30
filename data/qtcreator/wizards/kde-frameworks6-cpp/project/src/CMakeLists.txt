add_executable(%{ProjectNameLC})

target_sources(%{ProjectNameLC} PRIVATE
    main.cpp
    %{ProjectNameLC}window.cpp
    %{ProjectNameLC}view.cpp
    %{ProjectNameLC}.qrc
)

ecm_qt_declare_logging_category(%{ProjectNameLC}
    HEADER %{ProjectNameLC}debug.h
    IDENTIFIER %{ProjectNameUC}
    CATEGORY_NAME "%{ProjectNameLC}"
)
kconfig_add_kcfg_files(%{ProjectNameLC} %{ProjectName}Settings.kcfgc)
ki18n_wrap_ui(%{ProjectNameLC}
    %{ProjectNameLC}view.ui
    settings.ui
)

target_link_libraries(%{ProjectNameLC}
    KF6::CoreAddons
    KF6::I18n
    KF6::XmlGui
    KF6::ConfigWidgets
    KF6::DBusAddons
    KF6::Crash
    Qt6::Widgets
)

install(TARGETS %{ProjectNameLC} ${KDE_INSTALL_TARGETS_DEFAULT_ARGS})
install(PROGRAMS org.example.%{ProjectNameLC}.desktop DESTINATION ${KDE_INSTALL_APPDIR})
install(FILES org.example.%{ProjectNameLC}.metainfo.xml DESTINATION ${KDE_INSTALL_METAINFODIR})
