add_executable(%{ProjectNameLC})

target_sources(%{ProjectNameLC} PRIVATE
    main.cpp
    %{ProjectNameLC}window.cpp
)

ki18n_wrap_ui(%{ProjectNameLC} %{ProjectNameLC}.ui)

target_link_libraries(%{ProjectNameLC}
    KF6::CoreAddons
    KF6::I18n
    Qt6::Widgets
)

install(TARGETS %{ProjectNameLC} ${KDE_INSTALL_TARGETS_DEFAULT_ARGS})
install(PROGRAMS org.example.%{ProjectNameLC}.desktop DESTINATION ${KDE_INSTALL_APPDIR})
install(FILES org.example.%{ProjectNameLC}.metainfo.xml DESTINATION ${KDE_INSTALL_METAINFODIR})
