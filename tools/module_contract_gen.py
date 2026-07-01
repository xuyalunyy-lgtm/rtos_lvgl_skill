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


def main() -> int:
    parser = argparse.ArgumentParser(description="模块契约生成器")
    parser.add_argument("--name", help="模块名")
    parser.add_argument("--input", help="输入描述")
    parser.add_argument("--output", help="输出描述")
    parser.add_argument("--tasks", type=int, default=1, help="任务数")
    parser.add_argument("--outdir", "-o", help="输出目录")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

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
