add_executable(%{ProjectNameLC})

qt_add_qml_module(%{ProjectNameLC}
    URI org.kde.%{ProjectNameLC}
    # Embed the module under :/qt/qml, which is on the default QML import path, so
    # engine.loadFromModule() resolves it whether the app is run from the build tree,
    # installed, or launched by an IDE.
    RESOURCE_PREFIX "/qt/qml"
    QML_FILES
        Main.qml
    SOURCES
        main.cpp
        greeter.cpp
        greeter.h
)

target_link_libraries(%{ProjectNameLC} PRIVATE
    KF6::CoreAddons
    KF6::I18n
    KF6::IconThemes
    Qt6::Quick
    Qt6::QuickControls2
    Qt6::Widgets
)

install(TARGETS %{ProjectNameLC} ${KDE_INSTALL_TARGETS_DEFAULT_ARGS})
install(PROGRAMS org.kde.%{ProjectNameLC}.desktop DESTINATION ${KDE_INSTALL_APPDIR})
install(FILES org.kde.%{ProjectNameLC}.metainfo.xml DESTINATION ${KDE_INSTALL_METAINFODIR})
