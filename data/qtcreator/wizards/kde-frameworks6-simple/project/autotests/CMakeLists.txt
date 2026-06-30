include(ECMAddTests)

find_package(Qt6Test ${QT_MIN_VERSION} CONFIG QUIET)

if(NOT TARGET Qt6::Test)
    message(STATUS "Qt6Test not found, autotests will not be built.")
    return()
endif()

# The window class lives in ../src; pull it (and its form) into the test.
ki18n_wrap_ui(%{ProjectNameLC}windowtest_SRCS ${CMAKE_SOURCE_DIR}/src/%{ProjectNameLC}.ui)

ecm_add_test(
    %{ProjectNameLC}windowtest.cpp
    ${CMAKE_SOURCE_DIR}/src/%{ProjectNameLC}window.cpp
    ${%{ProjectNameLC}windowtest_SRCS}
    TEST_NAME %{ProjectNameLC}windowtest
    GUI
    LINK_LIBRARIES Qt6::Test Qt6::Widgets KF6::CoreAddons KF6::I18n
)

target_include_directories(%{ProjectNameLC}windowtest PRIVATE
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_CURRENT_BINARY_DIR}
)

# Run headless so the test works without a display (CI, build servers).
set_tests_properties(%{ProjectNameLC}windowtest PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
