cmake_minimum_required(VERSION 3.16)
project(lvgl_sim_runner C)

# ── Options ───────────────────────────────────────────────────────

set(LVGL_ROOT "" CACHE PATH "Path to LVGL v9 source (required)")
set(ASSET_CONTRACT_DIR "" CACHE PATH "Optional generated asset-contract directory for compile/link verification")

# ── Validate ──────────────────────────────────────────────────────

if(NOT LVGL_ROOT OR NOT EXISTS "${LVGL_ROOT}/lv_conf_template.h")
    message(FATAL_ERROR "LVGL_ROOT must point to LVGL v9 source directory (with lv_conf_template.h)")
endif()

# ── LVGL library ──────────────────────────────────────────────────

include_directories("${LVGL_ROOT}")
include_directories("${LVGL_ROOT}/src")

# LVGL source files
file(GLOB_RECURSE LVGL_SOURCES "${LVGL_ROOT}/src/*.c")

# ── Simulator sources ─────────────────────────────────────────────

set(SIM_SOURCES
    main.c
    asset_pack.c
    font_registry.c
    scene_decoder.c
    framebuffer_display.c
    object_tree_dump.c
)

# ── LVGL config ───────────────────────────────────────────────────

configure_file(lv_conf_v9.h ${CMAKE_BINARY_DIR}/lv_conf.h COPYONLY)
include_directories(${CMAKE_BINARY_DIR})

# ── Build target ──────────────────────────────────────────────────

add_executable(lvgl_sim_v9 ${SIM_SOURCES} ${LVGL_SOURCES})

target_compile_definitions(lvgl_sim_v9 PRIVATE
    LV_CONF_INCLUDE_SIMPLE=1
    LVGL_VERSION_MAJOR=9
)

if(UNIX AND NOT APPLE)
    target_link_libraries(lvgl_sim_v9 m pthread)
endif()

if(WIN32)
    target_compile_definitions(lvgl_sim_v9 PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

# CI-only resource closure target.  It compiles every generated descriptor and
# links a harness that takes the address of every symbol.  No generated source
# is silently omitted from the firmware source list.
if(ASSET_CONTRACT_DIR)
    if(NOT EXISTS "${ASSET_CONTRACT_DIR}/ui_auto_assets.cmake" OR NOT EXISTS "${ASSET_CONTRACT_DIR}/asset_link_harness.c")
        message(FATAL_ERROR "ASSET_CONTRACT_DIR is missing generated closure inputs")
    endif()
    include("${ASSET_CONTRACT_DIR}/ui_auto_assets.cmake")
    add_executable(lvgl_asset_link_harness
        "${ASSET_CONTRACT_DIR}/asset_link_harness.c"
        ${UI_AUTO_ASSET_SOURCES}
    )
    target_include_directories(lvgl_asset_link_harness PRIVATE
        "${ASSET_CONTRACT_DIR}"
        "${LVGL_ROOT}"
        "${LVGL_ROOT}/src"
        "${CMAKE_BINARY_DIR}"
    )
    target_compile_definitions(lvgl_asset_link_harness PRIVATE LV_CONF_INCLUDE_SIMPLE=1 LVGL_VERSION_MAJOR=9)
endif()

# ── Install ───────────────────────────────────────────────────────

install(TARGETS lvgl_sim_v9 RUNTIME DESTINATION bin)
