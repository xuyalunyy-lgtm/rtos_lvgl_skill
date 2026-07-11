cmake_minimum_required(VERSION 3.16)
project(lvgl_sim_runner C)

# ── Options ───────────────────────────────────────────────────────

set(LVGL_VERSION "v9" CACHE STRING "LVGL version (v8 or v9)")
set(LVGL_ROOT "" CACHE PATH "Path to LVGL source")
set(BUILD_SHARED_LIBS OFF)

# ── Validate ──────────────────────────────────────────────────────

if(NOT LVGL_ROOT OR NOT EXISTS "${LVGL_ROOT}")
    message(FATAL_ERROR "LVGL_ROOT must point to LVGL source directory")
endif()

# ── LVGL library ──────────────────────────────────────────────────

# Include LVGL headers
include_directories("${LVGL_ROOT}")
include_directories("${LVGL_ROOT}/src")

# LVGL source files (minimal subset for headless rendering)
file(GLOB_RECURSE LVGL_SOURCES
    "${LVGL_ROOT}/src/*.c"
)

# ── Simulator sources ─────────────────────────────────────────────

set(SIM_SOURCES
    main.c
    scene_decoder.c
    framebuffer_display.c
    object_tree_dump.c
)

# ── LVGL config ───────────────────────────────────────────────────

if(LVGL_VERSION STREQUAL "v9")
    add_definitions(-DLVGL_VERSION_MAJOR=9)
    configure_file(lv_conf_v9.h ${CMAKE_BINARY_DIR}/lv_conf.h COPYONLY)
else()
    add_definitions(-DLVGL_VERSION_MAJOR=8)
    configure_file(lv_conf_v8.h ${CMAKE_BINARY_DIR}/lv_conf.h COPYONLY)
endif()

include_directories(${CMAKE_BINARY_DIR})

# ── Build target ──────────────────────────────────────────────────

add_executable(lvgl_sim_${LVGL_VERSION} ${SIM_SOURCES} ${LVGL_SOURCES})

target_compile_definitions(lvgl_sim_${LVGL_VERSION} PRIVATE
    LV_CONF_INCLUDE_SIMPLE=1
)

if(UNIX AND NOT APPLE)
    target_link_libraries(lvgl_sim_${LVGL_VERSION} m pthread)
endif()

# ── Install ───────────────────────────────────────────────────────

install(TARGETS lvgl_sim_${LVGL_VERSION}
    RUNTIME DESTINATION bin
)
