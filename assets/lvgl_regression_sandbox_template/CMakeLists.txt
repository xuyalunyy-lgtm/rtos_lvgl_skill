cmake_minimum_required(VERSION 3.16)
project(lvgl_regression_sandbox C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(LVGL_ROOT "" CACHE PATH "Path to an LVGL source tree")
set(SDL2_ROOT "" CACHE PATH "Path to an SDL2 development package (optional)")
set(SDL2_DIR "" CACHE PATH "Path to SDL2 CMake config (optional)")
set(UI_UNDER_TEST_DIR "" CACHE PATH "Directory containing generated ui_*.c/.h files")
set(REGRESSION_OUTPUT_DIR "${CMAKE_BINARY_DIR}/regression" CACHE PATH "Regression output directory")
set(REGRESSION_WIDTH "480" CACHE STRING "Display width")
set(REGRESSION_HEIGHT "800" CACHE STRING "Display height")

if(NOT LVGL_ROOT)
    if(EXISTS "${CMAKE_SOURCE_DIR}/third_party/lvgl/CMakeLists.txt")
        set(LVGL_ROOT "${CMAKE_SOURCE_DIR}/third_party/lvgl")
    else()
        message(FATAL_ERROR "LVGL_ROOT is required or third_party/lvgl must be present")
    endif()
endif()

# SDL2 is optional; sandbox uses null display driver by default.
set(HAVE_SDL2 FALSE)
if(SDL2_ROOT AND EXISTS "${SDL2_ROOT}/cmake")
    set(SDL2_DIR "${SDL2_ROOT}/cmake")
elseif(NOT SDL2_DIR AND EXISTS "${CMAKE_SOURCE_DIR}/third_party/sdl2/cmake")
    set(SDL2_DIR "${CMAKE_SOURCE_DIR}/third_party/sdl2/cmake")
endif()

set(SDL2_EXTRA_INCLUDE_DIRS "")
if(SDL2_DIR)
    get_filename_component(SDL2_PACKAGE_ROOT "${SDL2_DIR}/.." ABSOLUTE)
    foreach(SDL2_INCLUDE_CANDIDATE
        "${SDL2_PACKAGE_ROOT}/x86_64-w64-mingw32/include"
        "${SDL2_PACKAGE_ROOT}/i686-w64-mingw32/include"
        "${SDL2_PACKAGE_ROOT}/include"
    )
        if(EXISTS "${SDL2_INCLUDE_CANDIDATE}/SDL2/SDL.h")
            list(APPEND SDL2_EXTRA_INCLUDE_DIRS "${SDL2_INCLUDE_CANDIDATE}")
        endif()
    endforeach()
endif()

find_package(SDL2 CONFIG QUIET)
if(TARGET SDL2::SDL2)
    set(SDL2_LIBS SDL2::SDL2)
    set(HAVE_SDL2 TRUE)
    get_target_property(SDL2_TARGET_INCLUDES SDL2::SDL2 INTERFACE_INCLUDE_DIRECTORIES)
    if(SDL2_TARGET_INCLUDES)
        include_directories(${SDL2_TARGET_INCLUDES})
    endif()
elseif(SDL2_FOUND)
    set(SDL2_LIBS ${SDL2_LIBRARIES})
    set(HAVE_SDL2 TRUE)
else()
    message(STATUS "SDL2 not found; using null display driver (no screen output)")
    set(SDL2_LIBS "")
endif()
if(SDL2_EXTRA_INCLUDE_DIRS)
    include_directories(${SDL2_EXTRA_INCLUDE_DIRS})
endif()

set(CONFIG_LV_BUILD_EXAMPLES OFF CACHE BOOL "Build LVGL examples" FORCE)
set(CONFIG_LV_BUILD_DEMOS OFF CACHE BOOL "Build LVGL demos" FORCE)
set(LV_BUILD_CONF_DIR "${CMAKE_SOURCE_DIR}" CACHE PATH "Directory containing lv_conf.h" FORCE)
add_subdirectory(${LVGL_ROOT} ${CMAKE_BINARY_DIR}/lvgl_build)
if(TARGET lvgl AND SDL2_TARGET_INCLUDES)
    target_include_directories(lvgl PUBLIC ${SDL2_TARGET_INCLUDES})
endif()
if(TARGET lvgl AND SDL2_EXTRA_INCLUDE_DIRS)
    target_include_directories(lvgl PUBLIC ${SDL2_EXTRA_INCLUDE_DIRS})
endif()

set(SANDBOX_SOURCES
    src/regression_main.c
    src/ui_under_test_default.c
)

if(UI_UNDER_TEST_DIR)
    file(GLOB UI_UNDER_TEST_SOURCES CONFIGURE_DEPENDS "${UI_UNDER_TEST_DIR}/*.c")
    list(APPEND SANDBOX_SOURCES ${UI_UNDER_TEST_SOURCES})
endif()

add_executable(lvgl_regression_sandbox ${SANDBOX_SOURCES})
target_compile_definitions(lvgl_regression_sandbox PRIVATE
    LV_CONF_INCLUDE_SIMPLE
    SDL_MAIN_HANDLED
    REGRESSION_OUTPUT_DIR="${REGRESSION_OUTPUT_DIR}"
    REGRESSION_WIDTH=${REGRESSION_WIDTH}
    REGRESSION_HEIGHT=${REGRESSION_HEIGHT}
)
target_include_directories(lvgl_regression_sandbox PRIVATE
    ${CMAKE_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src
    ${LVGL_ROOT}
    ${LVGL_ROOT}/src
)
if(UI_UNDER_TEST_DIR)
    target_include_directories(lvgl_regression_sandbox PRIVATE ${UI_UNDER_TEST_DIR})
    target_compile_definitions(lvgl_regression_sandbox PRIVATE UI_UNDER_TEST_EXTERNAL=1)
endif()
target_link_libraries(lvgl_regression_sandbox PRIVATE lvgl ${SDL2_LIBS})

if(WIN32 AND NOT MSVC)
    target_link_options(lvgl_regression_sandbox PRIVATE "-mconsole")
endif()
