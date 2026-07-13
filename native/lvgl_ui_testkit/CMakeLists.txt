cmake_minimum_required(VERSION 3.16)
project(lvgl_ui_testkit C)

set(LVGL_ROOT "" CACHE PATH "Path to pinned LVGL v9 source")
set(UI_GENERATED_DIR "" CACHE PATH "Directory produced by the UI generator")

if(NOT LVGL_ROOT OR NOT EXISTS "${LVGL_ROOT}/lv_conf_template.h")
    message(FATAL_ERROR "LVGL_ROOT must point to an LVGL v9 source tree")
endif()
if(NOT UI_GENERATED_DIR OR NOT EXISTS "${UI_GENERATED_DIR}/ui_generated.cmake")
    message(FATAL_ERROR "UI_GENERATED_DIR must contain ui_generated.cmake")
endif()
if(NOT EXISTS "${UI_GENERATED_DIR}/ui_test_adapter.c")
    message(FATAL_ERROR "UI_GENERATED_DIR must contain ui_test_adapter.c")
endif()

configure_file(
    "${CMAKE_CURRENT_LIST_DIR}/../lvgl_sim_runner/lv_conf_v9.h"
    "${CMAKE_BINARY_DIR}/lv_conf.h"
    COPYONLY
)

include("${UI_GENERATED_DIR}/ui_generated.cmake")
file(GLOB_RECURSE LVGL_SOURCES CONFIGURE_DEPENDS "${LVGL_ROOT}/src/*.c")

add_executable(lvgl_ui_testkit
    src/testkit_main.c
    "${CMAKE_CURRENT_LIST_DIR}/../lvgl_sim_runner/framebuffer_display.c"
    "${CMAKE_CURRENT_LIST_DIR}/../lvgl_sim_runner/object_tree_dump.c"
    "${UI_GENERATED_DIR}/ui_test_adapter.c"
    ${UI_GENERATED_SOURCES}
    ${LVGL_SOURCES}
)

target_include_directories(lvgl_ui_testkit PRIVATE
    include
    "${CMAKE_CURRENT_LIST_DIR}/../lvgl_sim_runner"
    "${UI_GENERATED_DIR}"
    "${LVGL_ROOT}"
    "${LVGL_ROOT}/src"
    "${CMAKE_BINARY_DIR}"
)
target_compile_definitions(lvgl_ui_testkit PRIVATE
    LV_CONF_INCLUDE_SIMPLE=1
    LVGL_VERSION_MAJOR=9
    UI_APP_TEST_MODE=1
)

if(UNIX AND NOT APPLE)
    target_link_libraries(lvgl_ui_testkit m pthread)
endif()
if(WIN32)
    target_compile_definitions(lvgl_ui_testkit PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

