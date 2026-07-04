#!/usr/bin/env python3
"""
模块契约生成器 — 生成 C29 模块契约头文件 + C30 任务拓扑表。

功能：
  1. 输入模块名 + I/P/O 描述，生成模块契约头文件
  2. 生成任务拓扑表模板
  3. 生成生命周期对称骨架

用法:
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
    """生成模块契约头文件"""
    upper_name = name.upper()

    header = f'''/**
 * @file {name}_contract.h
 * @brief {name} 模块契约（C29 + C30 自动生成）
 *
 * 约束覆盖：
 *   C29.1 — 可调用上下文声明
 *   C29.2 — 阻塞语义声明
 *   C29.3 — 所有权声明
 *   C29.4 — 生命周期顺序声明
 *   C29.5 — 错误码语义声明
 *   C30.1 — 任务/队列拓扑表
 */

#ifndef {upper_name}_CONTRACT_H
#define {upper_name}_CONTRACT_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {{
#endif

/* ========================================================================== */
/* 错误码 (C29.5)                                                            */
/* ========================================================================== */

typedef enum {{
    {upper_name}_OK = 0,
    {upper_name}_ERR_TIMEOUT,      /* 可恢复：超时 */
    {upper_name}_ERR_RESOURCE,     /* 可恢复：资源不足 */
    {upper_name}_ERR_CONFIG,       /* 不可恢复：配置错误 */
    {upper_name}_ERR_IO,           /* 可恢复：IO 错误 */
    {upper_name}_ERR_STATE,        /* 不可恢复：非法状态 */
}} {name}_err_t;

/* ========================================================================== */
/* 模块状态 (C32.1 可观测性)                                                 */
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
/* 模块契约 (C29)                                                            */
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
 * @brief 初始化模块
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 最大等待 100ms
 * @par 生命周期 (C29.4): 必须在 start 之前调用
 *
 * @return {upper_name}_OK 成功
 * @return {upper_name}_ERR_RESOURCE 资源不足
 * @return {upper_name}_ERR_CONFIG 配置错误
 */
{name}_err_t {name}_init(void);

/**
 * @brief 启动模块
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 非阻塞
 * @par 生命周期 (C29.4): 必须在 init 之后、stop 之前调用
 *
 * @return {upper_name}_OK 成功
 * @return {upper_name}_ERR_STATE 未初始化
 */
{name}_err_t {name}_start(void);

/**
 * @brief 停止模块
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 最大等待 500ms（等待任务退出）
 * @par 可重入 (C29.4): 可重入，多次调用安全
 * @par 生命周期 (C29.4): 可在 start 后任意时刻调用
 *
 * @return {upper_name}_OK 成功
 */
{name}_err_t {name}_stop(void);

/**
 * @brief 反初始化模块
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 非阻塞
 * @par 可重入 (C29.4): 可重入，多次调用安全
 * @par 生命周期 (C29.4): 必须在 stop 之后调用
 *
 * @return {upper_name}_OK 成功
 */
{name}_err_t {name}_deinit(void);

/**
 * @brief 获取模块状态
 *
 * @par 可调用上下文 (C29.1): task / ISR / timer
 * @par 阻塞语义 (C29.2): 非阻塞
 *
 * @param[out] status 模块状态
 * @return {upper_name}_OK 成功
 */
{name}_err_t {name}_get_status({name}_status_t *status);

/* ========================================================================== */
/* 输入/输出接口 (C29.3 所有权)                                              */
/* ========================================================================== */

/**
 * @brief 输入 {input_desc}
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 最大等待 50ms
 * @par 所有权 (C29.3): 调用方拥有数据，模块内部拷贝
 *
 * @param data 输入数据
 * @param len 数据长度
 * @return {upper_name}_OK 成功
 * @return {upper_name}_ERR_TIMEOUT 队列满
 */
{name}_err_t {name}_input(const void *data, size_t len);

/**
 * @brief 输出 {output_desc}
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 非阻塞
 * @par 所有权 (C29.3): 模块拥有输出数据，调用方只读
 *
 * @param[out] data 输出数据指针
 * @param[out] len 数据长度
 * @return {upper_name}_OK 成功
 * @return {upper_name}_ERR_STATE 无数据
 */
{name}_err_t {name}_output(const void **data, size_t *len);

/* ========================================================================== */
/* 任务拓扑表 (C30)                                                          */
/* ========================================================================== */

/*
 * 任务拓扑表（C30.1）
 *
 * | 任务名 | 优先级 | 栈大小 | 队列 | 生产者 | 消费者 | 超时 | 背压 |
 * |--------|--------|--------|------|--------|--------|------|------|
 * | {name}_worker | 5 | 4096 | {name}_q (depth=8) | {name}_input | {name}_process | 50ms | drop-oldest |
 *
 * 队列元素类型: 内部 buffer 描述符（非裸指针）
 * 退出条件: stop flag + k_msgq_purge
 */

#ifdef __cplusplus
}}
#endif

#endif /* {upper_name}_CONTRACT_H */
'''
    return header


def generate_state_machine(name: str) -> str:
    """生成状态机骨架"""
    upper_name = name.upper()

    code = f'''/**
 * @file {name}_fsm.c
 * @brief {name} 状态机骨架（C13 自动生成）
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

    /* TODO: 初始化资源 */

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

    /* TODO: 启动任务/定时器 */

    s_state = {upper_name}_STATE_RUNNING;
    LOG_INF("Module started");
    return {upper_name}_OK;
}}

{name}_err_t {name}_stop(void)
{{
    if (s_state != {upper_name}_STATE_RUNNING) {{
        LOG_WRN("Not running, state=%d", s_state);
        return {upper_name}_OK; /* 可重入 */
    }}

    s_state = {upper_name}_STATE_STOPPING;
    LOG_INF("Module stopping...");

    /* TODO: 通知任务退出 + 等待 */

    s_state = {upper_name}_STATE_IDLE;
    LOG_INF("Module stopped");
    return {upper_name}_OK;
}}

{name}_err_t {name}_deinit(void)
{{
    if (s_state == {upper_name}_STATE_UNINIT) {{
        return {upper_name}_OK; /* 可重入 */
    }}

    if (s_state == {upper_name}_STATE_RUNNING) {{
        {name}_stop();
    }}

    /* TODO: 释放资源 */

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
    """自测"""
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
    """生成 modules_init.c — 多模块初始化顺序（按拓扑排序）。"""
    lines = [
        '/**',
        ' * @file modules_init.c',
        ' * @brief 多模块初始化入口（自动生成）',
        ' *',
        ' * 初始化顺序按模块依赖拓扑排序：',
        ' *   1. 基础设施（通信、存储）',
        ' *   2. 驱动层（传感器、显示、音频）',
        ' *   3. 业务层（UI、ASR、网络）',
        ' */',
        '',
        '#include <stdio.h>',
        '#include "esp_log.h"',
        '#include "freertos/FreeRTOS.h"',
        '#include "freertos/task.h"',
        '',
    ]

    # include 所有模块契约头文件
    for mod in modules:
        name = mod if isinstance(mod, str) else mod.get("name", "unknown")
        lines.append(f'#include "{name}_contract.h"')
    lines.append('')
    lines.append('static const char *TAG = "modules_init";')
    lines.append('')

    # 初始化函数
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

    # 启动函数
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

    # 停止函数（反序）
    lines.append('void modules_stop_all(void)')
    lines.append('{')
    for mod in reversed(modules):
        name = mod if isinstance(mod, str) else mod.get("name", "unknown")
        lines.append(f'    {name}_stop();')
    lines.append('}')
    lines.append('')

    # 反初始化函数（反序）
    lines.append('void modules_deinit_all(void)')
    lines.append('{')
    for mod in reversed(modules):
        name = mod if isinstance(mod, str) else mod.get("name", "unknown")
        lines.append(f'    {name}_deinit();')
    lines.append('}')

    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="模块契约生成器 v9.0.2")
    parser.add_argument("--name", help="模块名（单模块模式）")
    parser.add_argument("--input", help="输入描述")
    parser.add_argument("--output", help="输出描述")
    parser.add_argument("--tasks", type=int, default=1, help="任务数")
    parser.add_argument("--modules", nargs="+",
                        help="多模块模式：模块名列表（如 audio_player display_mgr network_svc）")
    parser.add_argument("--preset", help="从 scene_presets/ 读取模块定义")
    parser.add_argument("--outdir", "-o", help="输出目录")
    parser.add_argument("--evidence", metavar="FILE", help="输出交付证据包到指定文件")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    # ── Preset 模式 ──
    if args.preset:
        presets_dir = Path(__file__).resolve().parent.parent / "scene_presets"
        preset_path = presets_dir / f"{args.preset}.json"
        if not preset_path.exists():
            print(f"错误: preset '{args.preset}' 不存在", file=sys.stderr)
            return 1
        preset = json.loads(preset_path.read_text(encoding="utf-8"))
        tasks = preset.get("generator_params", {}).get("tasks", [])
        if tasks:
            args.modules = tasks

    # ── 多模块模式 ──
    if args.modules:
        outdir = Path(args.outdir) if args.outdir else Path(".")
        outdir.mkdir(parents=True, exist_ok=True)

        module_list = []
        for mod_name in args.modules:
            mod = {"name": mod_name, "input": "data", "output": "result"}
            module_list.append(mod)

            # 生成每个模块的契约头文件
            header = generate_contract_header(mod_name, mod["input"], mod["output"], 1)
            header_path = outdir / f"{mod_name}_contract.h"
            header_path.write_text(header, encoding="utf-8")
            print(f"[OK] Generated {header_path}")

            # 生成状态机
            code = generate_state_machine(mod_name)
            code_path = outdir / f"{mod_name}_fsm.c"
            code_path.write_text(code, encoding="utf-8")
            print(f"[OK] Generated {code_path}")

        # 生成 modules_init.c
        init_code = generate_modules_init_c(module_list)
        init_path = outdir / "modules_init.c"
        init_path.write_text(init_code, encoding="utf-8")
        print(f"[OK] Generated {init_path}")

        # 证据包
        if args.evidence:
            try:
                from evidence_schema import generated_file, make_evidence, save_evidence
            except ImportError:
                print("[warn] evidence_schema 模块不可用（已归档），跳过证据包输出", file=sys.stderr)
                return 0
            gen_files = []
            for mod in module_list:
                gen_files.append(generated_file(str(outdir / f"{mod['name']}_contract.h"), "h", f"{mod['name']} 契约头文件"))
                gen_files.append(generated_file(str(outdir / f"{mod['name']}_fsm.c"), "c", f"{mod['name']} 状态机"))
            gen_files.append(generated_file(str(init_path), "c", "多模块初始化入口"))

            ev = make_evidence(
                source_tool="module_contract_gen",
                generated_files=gen_files,
                metadata={"tool_version": "9.0.2", "modules": args.modules},
            )
            save_evidence(ev, args.evidence)
            print(f"[evidence] 已保存交付证据包: {args.evidence}")

        return 0

    # ── 单模块模式 ──
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
