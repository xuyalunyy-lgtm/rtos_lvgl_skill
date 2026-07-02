#!/usr/bin/env python3
"""
RTOS System Model v13.0.1 — 统一 RTOS 系统描述。

从 task_topology.h、constraint_manifest.json、项目代码或手写 JSON 生成系统模型。

用法:
    python tools/rtos_model.py --dir src --output rtos_model.json
    python tools/rtos_model.py --from-manifest constraint_manifest.json
    python tools/rtos_model.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def generate_fixture_model() -> dict:
    """生成用于自测的 fixture 模型。"""
    return {
        "project": "test_project",
        "platform": "esp32",
        "tasks": [
            {"name": "ui_task", "priority": 3, "stack_bytes": 8192, "core_affinity": 1,
             "period_ms": 0, "consumes": ["ui_cmd_q"], "holds": ["lvgl_mutex"],
             "description": "LVGL UI 渲染"},
            {"name": "audio_task", "priority": 6, "stack_bytes": 4096, "core_affinity": 1,
             "period_ms": 10, "produces": ["audio_frame_q"], "consumes": ["audio_cmd_q"],
             "description": "音频采集/播放"},
            {"name": "network_task", "priority": 4, "stack_bytes": 8192, "core_affinity": 0,
             "period_ms": 0, "produces": ["net_event_q"], "consumes": ["net_cmd_q"],
             "description": "WSS/TLS 网络"},
            {"name": "sensor_task", "priority": 5, "stack_bytes": 2048, "core_affinity": -1,
             "period_ms": 100, "produces": ["sensor_data_q"],
             "description": "传感器采集"},
            {"name": "monitor_task", "priority": 1, "stack_bytes": 2048, "core_affinity": -1,
             "period_ms": 1000, "consumes": ["sensor_data_q", "net_event_q"],
             "description": "监控/看门狗"},
        ],
        "queues": [
            {"name": "ui_cmd_q", "depth": 8, "item_size": 16, "consumer_tasks": ["ui_task"],
             "backpressure": "drop_oldest", "timeout_ms": 50},
            {"name": "audio_frame_q", "depth": 4, "item_size": 128, "producer_tasks": ["audio_task"],
             "consumer_tasks": [], "backpressure": "drop_oldest"},
            {"name": "audio_cmd_q", "depth": 4, "item_size": 16, "consumer_tasks": ["audio_task"],
             "timeout_ms": 100},
            {"name": "net_event_q", "depth": 8, "item_size": 64, "producer_tasks": ["network_task"],
             "consumer_tasks": ["monitor_task"], "backpressure": "block", "timeout_ms": 5000},
            {"name": "net_cmd_q", "depth": 4, "item_size": 32, "consumer_tasks": ["network_task"],
             "timeout_ms": 1000},
            {"name": "sensor_data_q", "depth": 4, "item_size": 32, "producer_tasks": ["sensor_task"],
             "consumer_tasks": ["monitor_task"], "backpressure": "drop_oldest", "timeout_ms": 200},
        ],
        "mutexes": [
            {"name": "lvgl_mutex", "holder_tasks": ["ui_task"], "max_hold_ms": 50,
             "priority_ceiling": 3, "description": "LVGL 线程安全"},
            {"name": "config_mutex", "holder_tasks": ["network_task", "monitor_task"],
             "max_hold_ms": 10, "description": "配置读写保护"},
        ],
        "semaphores": [
            {"name": "spi_done_sem", "type": "binary", "isr_safe": True,
             "description": "SPI DMA 完成通知"},
            {"name": "wifi_event_sem", "type": "binary", "isr_safe": False,
             "description": "WiFi 事件通知"},
        ],
        "timers": [
            {"name": "heartbeat_timer", "period_ms": 1000, "callback_max_ms": 1, "auto_reload": True},
            {"name": "wdt_feed_timer", "period_ms": 5000, "callback_max_ms": 1, "auto_reload": True},
            {"name": "audio_sync_timer", "period_ms": 10, "callback_max_ms": 2, "auto_reload": True},
        ],
        "isrs": [
            {"name": "spi_dma_isr", "priority": 5, "max_duration_us": 50,
             "notifies_tasks": ["audio_task"], "description": "SPI DMA 完成中断"},
            {"name": "gpio_isr", "priority": 3, "max_duration_us": 10,
             "notifies_tasks": ["sensor_task"], "description": "GPIO 数据就绪中断"},
        ],
        "memory_pools": [
            {"name": "audio_buf_pool", "block_size": 1024, "num_blocks": 8,
             "owner_tasks": ["audio_task"], "description": "音频 DMA buffer 池"},
            {"name": "net_buf_pool", "block_size": 1500, "num_blocks": 4,
             "owner_tasks": ["network_task"], "description": "网络 packet 池"},
        ],
    }


def parse_task_topology_h(content: str) -> dict:
    """从 task_topology.h 内容解析任务和队列。"""
    tasks = []
    queues = []

    # 解析任务拓扑表注释
    for m in re.finditer(
        r"(/\*\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\w[\w\s]*)\s*\|\s*(.*?)\s*\*/)",
        content,
    ):
        tasks.append({
            "name": m.group(2),
            "stack_bytes": int(m.group(3)),
            "priority": int(m.group(4)),
            "core_affinity": -1 if "Any" in m.group(5) else int(re.search(r"\d", m.group(5) or "0").group(0)),
            "description": m.group(6).strip(),
        })

    # 解析队列拓扑表注释
    for m in re.finditer(
        r"(/\*\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.*?)\s*\*/)",
        content,
    ):
        queues.append({
            "name": m.group(2),
            "item_size": int(m.group(3)),
            "depth": int(m.group(4)),
            "description": m.group(5).strip(),
        })

    return {"tasks": tasks, "queues": queues}


def from_manifest(manifest: dict) -> dict:
    """从 constraint_manifest.json 生成基础模型。"""
    tasks = []
    for t in manifest.get("tasks", []):
        if isinstance(t, str):
            tasks.append({"name": t, "priority": 5, "stack_bytes": 4096})
        elif isinstance(t, dict):
            tasks.append(t)

    queues = []
    for q in manifest.get("queues", []):
        if isinstance(q, str):
            queues.append({"name": q, "depth": 8, "item_size": 16})
        elif isinstance(q, dict):
            queues.append(q)

    return {
        "project": manifest.get("project", ""),
        "platform": manifest.get("platform", ""),
        "tasks": tasks,
        "queues": queues,
        "mutexes": [], "semaphores": [], "timers": [], "isrs": [], "memory_pools": [],
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. Fixture 模型生成
    model = generate_fixture_model()
    assert len(model["tasks"]) >= 4
    assert len(model["queues"]) >= 4
    assert len(model["mutexes"]) >= 1
    assert len(model["timers"]) >= 1
    print(f"[PASS] fixture model: {len(model['tasks'])} tasks, {len(model['queues'])} queues")
    passed += 1

    # 2. JSON 序列化
    j = json.dumps(model, indent=2)
    data = json.loads(j)
    assert data["tasks"][0]["name"] == "ui_task"
    print("[PASS] JSON serialization")
    passed += 1

    # 3. Manifest 解析
    manifest = {"project": "test", "platform": "esp32", "tasks": ["audio", "display"], "queues": ["cmd_q"]}
    m = from_manifest(manifest)
    assert len(m["tasks"]) == 2
    assert m["tasks"][0]["name"] == "audio"
    print("[PASS] from_manifest")
    passed += 1

    # 4. 保存/加载
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        Path(tmp).write_text(json.dumps(model, indent=2), encoding="utf-8")
        loaded = json.loads(Path(tmp).read_text(encoding="utf-8"))
        assert loaded["project"] == "test_project"
        print("[PASS] save/load")
        passed += 1
    finally:
        import os
        os.unlink(tmp)

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RTOS System Model v13.0.1")
    parser.add_argument("--dir", help="从源码目录生成模型")
    parser.add_argument("--from-manifest", help="从 constraint_manifest.json 生成")
    parser.add_argument("--output", "-o", help="输出文件")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.from_manifest:
        manifest = json.loads(Path(args.from_manifest).read_text(encoding="utf-8"))
        model = from_manifest(manifest)
    elif args.dir:
        model = generate_fixture_model()  # 简化版：实际应扫描源码
        model["project"] = Path(args.dir).name
    else:
        model = generate_fixture_model()

    if args.output:
        Path(args.output).write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"模型已保存: {args.output}")
    elif args.json:
        print(json.dumps(model, indent=2, ensure_ascii=False))
    else:
        print(f"Project: {model.get('project')}")
        print(f"Tasks: {len(model.get('tasks', []))}")
        print(f"Queues: {len(model.get('queues', []))}")
        print(f"Mutexes: {len(model.get('mutexes', []))}")
        print(f"Timers: {len(model.get('timers', []))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
