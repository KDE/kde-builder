include(ECMAddTests)

find_package(Qt6Test ${QT_MIN_VERSION} CONFIG QUIET)

if(NOT TARGET Qt6::Test)
    message(STATUS "Qt6Test not found, autotests will not be built.")
    return()
endif()

# Build the KConfigXT settings class (shared with the application) into the test.
kconfig_add_kcfg_files(%{ProjectNameLC}settingstest_SRCS ${CMAKE_SOURCE_DIR}/src/%{ProjectName}Settings.kcfgc)

ecm_add_test(
    %{ProjectNameLC}settingstest.cpp
    ${%{ProjectNameLC}settingstest_SRCS}
    TEST_NAME %{ProjectNameLC}settingstest
    LINK_LIBRARIES Qt6::Test Qt6::Gui KF6::ConfigGui
)

target_include_directories(%{ProjectNameLC}settingstest PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
