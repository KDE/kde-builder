include(ECMAddTests)

find_package(Qt6Test ${QT_MIN_VERSION} CONFIG QUIET)
find_package(Qt6QuickTest ${QT_MIN_VERSION} CONFIG QUIET)

if(NOT TARGET Qt6::Test)
    message(STATUS "Qt6Test not found, autotests will not be built.")
    return()
endif()

# C++ unit test of the backend (no QML engine / display required).
ecm_add_test(
    %{ProjectNameLC}greetertest.cpp
    ${CMAKE_SOURCE_DIR}/src/greeter.cpp
    TEST_NAME %{ProjectNameLC}greetertest
    LINK_LIBRARIES Qt6::Test Qt6::Qml KF6::CoreAddons KF6::I18n
)

target_include_directories(%{ProjectNameLC}greetertest PRIVATE ${CMAKE_SOURCE_DIR}/src)

# QML unit test (Qt Quick Test). Runs every tst_*.qml in this directory, headless.
if(TARGET Qt6::QuickTest)
    ecm_add_test(
        qmltest.cpp
        TEST_NAME %{ProjectNameLC}qmltest
        GUI
        LINK_LIBRARIES Qt6::QuickTest Qt6::Qml
    )
    target_compile_definitions(%{ProjectNameLC}qmltest PRIVATE QUICK_TEST_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")
    set_tests_properties(%{ProjectNameLC}qmltest PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
endif()
