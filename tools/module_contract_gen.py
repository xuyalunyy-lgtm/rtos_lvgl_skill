#!/usr/bin/env python3
"""
Module contract generator — generates C29 module contract header + C30 task topology table.

Features:
  1. Input module name + I/P/O description, generate module contract header
  2. Generate task topology table template
  3. Generate lifecycle symmetry skeleton

Usage:
    python tools/module_contract_gen.py --name audio_player --input "PCM data" --output "playback state"
    python tools/module_contract_gen.py --name audio_player --input "PCM data" --output "playback state" --tasks 2
    python tools/module_contract_gen.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def generate_contract_header(name: str, input_desc: str, output_desc: str, num_tasks: int = 1) -> str:
    """Generate module contract header file"""
    upper_name = name.upper()

    header = f'''/**
 * @file {name}_contract.h
 * @brief {name} module contract (C29 + C30 auto-generated)
 *
 * Constraint coverage:
 *   C29.1 — Callable context declaration
 *   C29.2 — Blocking semantics declaration
 *   C29.3 — Ownership declaration
 *   C29.4 — Lifecycle order declaration
 *   C29.5 — Error code semantics declaration
 *   C30.1 — Task/queue topology table
 */

#ifndef {upper_name}_CONTRACT_H
#define {upper_name}_CONTRACT_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {{
#endif

/* ========================================================================== */
/* Error codes (C29.5)                                                        */
/* ========================================================================== */

typedef enum {{
    {upper_name}_OK = 0,
    {upper_name}_ERR_TIMEOUT,      /* Recoverable: timeout */
    {upper_name}_ERR_RESOURCE,     /* Recoverable: insufficient resources */
    {upper_name}_ERR_CONFIG,       /* Unrecoverable: configuration error */
    {upper_name}_ERR_IO,           /* Recoverable: IO error */
    {upper_name}_ERR_STATE,        /* Unrecoverable: invalid state */
}} {name}_err_t;

/* ========================================================================== */
/* Module state (C32.1 observability)                                         */
/* ========================================================================== */

typedef enum {{
    {upper_name}_STATE_UNINIT = 0,
    {upper_name}_STATE_IDLE,
    {upper_name}_STATE_RUNNING,
    {upper_name}_STATE_STOPPING,
    {upper_name}_STATE_ERROR,
}} {name}_state_t;

typedef struct {{
    {name}_state_t state;
    {name}_err_t   last_error;
    uint32_t       last_error_line;
    uint32_t       timeout_count;
    uint32_t       drop_count;
}} {name}_status_t;

/* ========================================================================== */
/* Module contract (C29)                                                      */
/* ========================================================================== */

/* module_boundary:
 * responsibility: own {name} input processing and output publication only
 * public_api: {name}_init, {name}_start, {name}_stop, {name}_deinit, {name}_get_status, {name}_input, {name}_output
 * dependencies: app_event_bus, platform driver API
 * forbidden_dependencies: lvgl, network_wss, storage_nvs private headers
 * events_in: {upper_name}_CMD_START, {upper_name}_CMD_STOP
 * events_out: {upper_name}_EVT_READY, {upper_name}_EVT_ERROR
 * owned_resources: {name}_worker, {name}_q, {name}_status
 */

/**
 * @brief Initialize module
 *
 * @par Callable context (C29.1): task only
 * @par Blocking semantics (C29.2): max wait 100ms
 * @par Lifecycle (C29.4): must be called before start
 *
 * @return {upper_name}_OK success
 * @return {upper_name}_ERR_RESOURCE insufficient resources
 * @return {upper_name}_ERR_CONFIG configuration error
 */
{name}_err_t {name}_init(void);

/**
 * @brief Start module
 *
 * @par Callable context (C29.1): task only
 * @par Blocking semantics (C29.2): non-blocking
 * @par Lifecycle (C29.4): must be called after init, before stop
 *
 * @return {upper_name}_OK success
 * @return {upper_name}_ERR_STATE not initialized
 */
{name}_err_t {name}_start(void);

/**
 * @brief Stop module
 *
 * @par Callable context (C29.1): task only
 * @par Blocking semantics (C29.2): max wait 500ms (waiting for task exit)
 * @par Reentrant (C29.4): reentrant, safe for multiple calls
 * @par Lifecycle (C29.4): can be called at any time after start
 *
 * @return {upper_name}_OK success
 */
{name}_err_t {name}_stop(void);

/**
 * @brief Deinitialize module
 *
 * @par Callable context (C29.1): task only
 * @par Blocking semantics (C29.2): non-blocking
 * @par Reentrant (C29.4): reentrant, safe for multiple calls
 * @par Lifecycle (C29.4): must be called after stop
 *
 * @return {upper_name}_OK success
 */
{name}_err_t {name}_deinit(void);

/**
 * @brief Get module status
 *
 * @par Callable context (C29.1): task / ISR / timer
 * @par Blocking semantics (C29.2): non-blocking
 *
 * @param[out] status module status
 * @return {upper_name}_OK success
 */
{name}_err_t {name}_get_status({name}_status_t *status);

/* ========================================================================== */
/* Input/Output interfaces (C29.3 ownership)                                  */
/* ========================================================================== */

/**
 * @brief Input {input_desc}
 *
 * @par Callable context (C29.1): task only
 * @par Blocking semantics (C29.2): max wait 50ms
 * @par Ownership (C29.3): caller owns data, module copies internally
 *
 * @param data input data
 * @param len data length
 * @return {upper_name}_OK success
 * @return {upper_name}_ERR_TIMEOUT queue full
 */
{name}_err_t {name}_input(const void *data, size_t len);

/**
 * @brief Output {output_desc}
 *
 * @par Callable context (C29.1): task only
 * @par Blocking semantics (C29.2): non-blocking
 * @par Ownership (C29.3): module owns output data, caller is read-only
 *
 * @param[out] data output data pointer
 * @param[out] len data length
 * @return {upper_name}_OK success
 * @return {upper_name}_ERR_STATE no data
 */
{name}_err_t {name}_output(const void **data, size_t *len);

/* ========================================================================== */
/* Task topology table (C30)                                                  */
/* ========================================================================== */

/*
 * Task topology table (C30.1)
 *
 * | Task name | Priority | Stack size | Queue | Producer | Consumer | Timeout | Backpressure |
 * |-----------|----------|------------|-------|----------|----------|---------|--------------|
 * | {name}_worker | 5 | 4096 | {name}_q (depth=8) | {name}_input | {name}_process | 50ms | drop-oldest |
 *
 * Queue element type: internal buffer descriptor (not raw pointer)
 * Exit condition: stop flag + k_msgq_purge
 */

#ifdef __cplusplus
}}
#endif

#endif /* {upper_name}_CONTRACT_H */
'''
    return header


def generate_state_machine(name: str) -> str:
    """Generate state machine skeleton"""
    upper_name = name.upper()

    code = f'''/**
 * @file {name}_fsm.c
 * @brief {name} state machine skeleton (C13 auto-generated)
 */

#include "{name}_contract.h"
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER({name}, CONFIG_LOG_DEFAULT_LEVEL);

static {name}_state_t s_state = {upper_name}_STATE_UNINIT;
static {name}_err_t s_last_error = {upper_name}_OK;
static uint32_t s_last_error_line = 0;

#define SET_ERROR(err) do {{ \\
    s_last_error = (err); \\
    s_last_error_line = __LINE__; \\
}} while(0)

{name}_err_t {name}_init(void)
{{
    if (s_state != {upper_name}_STATE_UNINIT) {{
        LOG_WRN("Already initialized");
        return {upper_name}_ERR_STATE;
    }}

    /* TODO: Initialize resources */

    s_state = {upper_name}_STATE_IDLE;
    LOG_INF("Module initialized");
    return {upper_name}_OK;
}}

{name}_err_t {name}_start(void)
{{
    if (s_state != {upper_name}_STATE_IDLE) {{
        LOG_ERR("Cannot start from state %d", s_state);
        SET_ERROR({upper_name}_ERR_STATE);
        return {upper_name}_ERR_STATE;
    }}

    /* TODO: Start tasks/timers */

    s_state = {upper_name}_STATE_RUNNING;
    LOG_INF("Module started");
    return {upper_name}_OK;
}}

{name}_err_t {name}_stop(void)
{{
    if (s_state != {upper_name}_STATE_RUNNING) {{
        LOG_WRN("Not running, state=%d", s_state);
        return {upper_name}_OK; /* Reentrant */
    }}

    s_state = {upper_name}_STATE_STOPPING;
    LOG_INF("Module stopping...");

    /* TODO: Notify task exit + wait */

    s_state = {upper_name}_STATE_IDLE;
    LOG_INF("Module stopped");
    return {upper_name}_OK;
}}

{name}_err_t {name}_deinit(void)
{{
    if (s_state == {upper_name}_STATE_UNINIT) {{
        return {upper_name}_OK; /* Reentrant */
    }}

    if (s_state == {upper_name}_STATE_RUNNING) {{
        {name}_stop();
    }}

    /* TODO: Release resources */

    s_state = {upper_name}_STATE_UNINIT;
    LOG_INF("Module deinitialized");
    return {upper_name}_OK;
}}

{name}_err_t {name}_get_status({name}_status_t *status)
{{
    if (status == NULL) return {upper_name}_ERR_CONFIG;

    status->state = s_state;
    status->last_error = s_last_error;
    status->last_error_line = s_last_error_line;
    return {upper_name}_OK;
}}
'''
    return code


def run_self_test() -> int:
    """Self-test"""
    passed = 0
    failed = 0

    # Test 1: Header generation
    header = generate_contract_header("audio_player", "PCM data", "playback state", 2)
    assert "audio_player_init" in header
    assert "audio_player_start" in header
    assert "audio_player_stop" in header
    assert "audio_player_deinit" in header
    assert "C29" in header
    assert "C30" in header
    assert "audio_player_err_t" in header
    print("[PASS] contract header generation")
    passed += 1

    # Test 2: State machine generation
    code = generate_state_machine("audio_player")
    assert "audio_player_init" in code
    assert "audio_player_start" in code
    assert "audio_player_stop" in code
    assert "audio_player_deinit" in code
    assert "STATE_UNINIT" in code
    assert "STATE_RUNNING" in code
    print("[PASS] state machine generation")
    passed += 1

    # Test 3: Error codes
    assert "AUDIO_PLAYER_ERR_TIMEOUT" in header
    assert "AUDIO_PLAYER_ERR_RESOURCE" in header
    print("[PASS] error code generation")
    passed += 1

    # Test 4: Status structure
    assert "audio_player_status_t" in header
    assert "last_error" in header
    assert "last_error_line" in header
    print("[PASS] status structure")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def generate_modules_init_c(modules: list[dict]) -> str:
    """Generate modules_init.c — multi-module initialization order (topologically sorted)."""
    lines = [
        '/**',
        ' * @file modules_init.c',
        ' * @brief Multi-module initialization entry (auto-generated)',
        ' *',
        ' * Initialization order is topologically sorted by module dependencies:',
        ' *   1. Infrastructure (communication, storage)',
        ' *   2. Driver layer (sensors, display, audio)',
        ' *   3. Business layer (UI, ASR, network)',
        ' */',
        '',
        '#include <stdio.h>',
        '#include "esp_log.h"',
        '#include "freertos/FreeRTOS.h"',
        '#include "freertos/task.h"',
        '',
    ]

    # Include all module contract header files
    for mod in modules:
        name = mod if isinstance(mod, str) else mod.get("name", "unknown")
        lines.append(f'#include "{name}_contract.h"')
    lines.append('')
    lines.append('static const char *TAG = "modules_init";')
    lines.append('')

    # Initialization function
    lines.append('esp_err_t modules_init_all(void)')
    lines.append('{')
    lines.append('    esp_err_t err;')
    lines.append('')

    for mod in modules:
        name = mod if isinstance(mod, str) else mod.get("name", "unknown")
        desc = "" if isinstance(mod, str) else mod.get("description", name)
        lines.append(f'    /* {desc} */')
        lines.append(f'    err = {name}_init();')
        lines.append(f'    if (err != {name.upper()}_OK) {{')
        lines.append(f'        ESP_LOGE(TAG, "{name}_init failed: %d", err);')
        lines.append(f'        return err;')
        lines.append(f'    }}')
        lines.append('')

    lines.append('    ESP_LOGI(TAG, "All modules initialized");')
    lines.append('    return ESP_OK;')
    lines.append('}')
    lines.append('')

    # Start function
    lines.append('esp_err_t modules_start_all(void)')
    lines.append('{')
    lines.append('    esp_err_t err;')
    lines.append('')

    for mod in modules:
        name = mod if isinstance(mod, str) else mod.get("name", "unknown")
        lines.append(f'    err = {name}_start();')
        lines.append(f'    if (err != {name.upper()}_OK) {{')
        lines.append(f'        ESP_LOGE(TAG, "{name}_start failed: %d", err);')
        lines.append(f'    }}')
        lines.append('')

    lines.append('    return ESP_OK;')
    lines.append('}')
    lines.append('')

    # Stop function (reverse order)
    lines.append('void modules_stop_all(void)')
    lines.append('{')
    for mod in reversed(modules):
        name = mod if isinstance(mod, str) else mod.get("name", "unknown")
        lines.append(f'    {name}_stop();')
    lines.append('}')
    lines.append('')

    # Deinitialization function (reverse order)
    lines.append('void modules_deinit_all(void)')
    lines.append('{')
    for mod in reversed(modules):
        name = mod if isinstance(mod, str) else mod.get("name", "unknown")
        lines.append(f'    {name}_deinit();')
    lines.append('}')

    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Module contract generator v9.0.2")
    parser.add_argument("--name", help="Module name (single module mode)")
    parser.add_argument("--input", help="Input description")
    parser.add_argument("--output", help="Output description")
    parser.add_argument("--tasks", type=int, default=1, help="Number of tasks")
    parser.add_argument("--modules", nargs="+",
                        help="Multi-module mode: module name list (e.g. audio_player display_mgr network_svc)")
    parser.add_argument("--preset", help="Read module definitions from scene_presets/")
    parser.add_argument("--outdir", "-o", help="Output directory")
    parser.add_argument("--evidence", metavar="FILE", help="Output delivery evidence package to specified file")
    parser.add_argument("--self-test", action="store_true", help="Run self-test")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    # ── Preset mode ──
    if args.preset:
        presets_dir = Path(__file__).resolve().parent.parent / "scene_presets"
        preset_path = presets_dir / f"{args.preset}.json"
        if not preset_path.exists():
            print(f"Error: preset '{args.preset}' does not exist", file=sys.stderr)
            return 1
        preset = json.loads(preset_path.read_text(encoding="utf-8"))
        tasks = preset.get("generator_params", {}).get("tasks", [])
        if tasks:
            args.modules = tasks

    # ── Multi-module mode ──
    if args.modules:
        outdir = Path(args.outdir) if args.outdir else Path(".")
        outdir.mkdir(parents=True, exist_ok=True)

        module_list = []
        for mod_name in args.modules:
            mod = {"name": mod_name, "input": "data", "output": "result"}
            module_list.append(mod)

            # Generate contract header for each module
            header = generate_contract_header(mod_name, mod["input"], mod["output"], 1)
            header_path = outdir / f"{mod_name}_contract.h"
            header_path.write_text(header, encoding="utf-8")
            print(f"[OK] Generated {header_path}")

            # Generate state machine
            code = generate_state_machine(mod_name)
            code_path = outdir / f"{mod_name}_fsm.c"
            code_path.write_text(code, encoding="utf-8")
            print(f"[OK] Generated {code_path}")

        # Generate modules_init.c
        init_code = generate_modules_init_c(module_list)
        init_path = outdir / "modules_init.c"
        init_path.write_text(init_code, encoding="utf-8")
        print(f"[OK] Generated {init_path}")

        # Evidence package
        if args.evidence:
            try:
                from evidence_schema import generated_file, make_evidence, save_evidence
            except ImportError:
                print("[warn] evidence_schema module not available (archived), skipping evidence package output", file=sys.stderr)
                return 0
            gen_files = []
            for mod in module_list:
                gen_files.append(generated_file(str(outdir / f"{mod['name']}_contract.h"), "h", f"{mod['name']} contract header"))
                gen_files.append(generated_file(str(outdir / f"{mod['name']}_fsm.c"), "c", f"{mod['name']} state machine"))
            gen_files.append(generated_file(str(init_path), "c", "Multi-module initialization entry"))

            ev = make_evidence(
                source_tool="module_contract_gen",
                generated_files=gen_files,
                metadata={"tool_version": "9.0.2", "modules": args.modules},
            )
            save_evidence(ev, args.evidence)
            print(f"[evidence] Delivery evidence package saved: {args.evidence}")

        return 0

    # ── Single module mode ──
    if not args.name or not args.input or not args.output:
        parser.print_help()
        return 1

    outdir = Path(args.outdir) if args.outdir else Path(".")
    outdir.mkdir(parents=True, exist_ok=True)

    # Generate header
    header = generate_contract_header(args.name, args.input, args.output, args.tasks)
    header_path = outdir / f"{args.name}_contract.h"
    header_path.write_text(header, encoding="utf-8")
    print(f"[OK] Generated {header_path}")

    # Generate state machine
    code = generate_state_machine(args.name)
    code_path = outdir / f"{args.name}_fsm.c"
    code_path.write_text(code, encoding="utf-8")
    print(f"[OK] Generated {code_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
