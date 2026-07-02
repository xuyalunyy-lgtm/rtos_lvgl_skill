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


def scan_source_dir(dir_path: str) -> dict:
    """从真实源码扫描 RTOS 对象：xTaskCreate、queue、mutex、semaphore、timer。"""
    root = Path(dir_path)
    if not root.is_dir():
        return {"tasks": [], "queues": [], "mutexes": [], "semaphores": [], "timers": [], "isrs": []}

    tasks = []
    queues = []
    mutexes = []
    semaphores = []
    timers = []
    isrs = []

    for f in sorted(root.rglob("*.c")) + sorted(root.rglob("*.h")):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # xTaskCreate / xTaskCreatePinnedToCore
        for m in re.finditer(
            r'xTaskCreate(?:PinnedToCore)?\s*\(\s*(\w+)\s*,\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(?:NULL|\w+)\s*,\s*(\d+)\s*(?:,\s*(?:NULL|&?(\w+)))?(?:\s*,\s*(\d+))?',
            content,
        ):
            tasks.append({
                "name": m.group(2),
                "priority": int(m.group(4)),
                "stack_bytes": int(m.group(3)),
                "core_affinity": int(m.group(6)) if m.group(6) else -1,
                "source_file": str(f.relative_to(root)),
                "description": f"task {m.group(2)}",
            })

        # Zephyr k_thread_create
        for m in re.finditer(
            r'k_thread_create\s*\(\s*&(\w+)\s*,\s*(\w+)\s*,\s*(?:K_THREAD_STACK_SIZEOF\((\w+)\)|(\d+))',
            content,
        ):
            tasks.append({
                "name": m.group(1).replace("_thread_data", ""),
                "priority": 5,  # default, actual set later in code
                "stack_bytes": 2048,  # placeholder
                "core_affinity": -1,
                "source_file": str(f.relative_to(root)),
                "description": f"zephyr thread {m.group(1)}",
            })

        # xQueueCreate
        for m in re.finditer(r'(\w+)\s*=\s*xQueueCreate\s*\(\s*(\d+)\s*,\s*sizeof\s*\(\s*(\w+)\s*\)', content):
            queues.append({
                "name": m.group(1).replace("s_", "").replace("_queue", ""),
                "depth": int(m.group(2)),
                "item_size": 0,  # sizeof resolved at compile time
                "source_file": str(f.relative_to(root)),
            })

        # Zephyr K_MSGQ_DEFINE
        for m in re.finditer(r'K_MSGQ_DEFINE\s*\(\s*(\w+)\s*,\s*sizeof\s*\(\s*(\w+)\s*\)\s*,\s*(\d+)', content):
            queues.append({
                "name": m.group(1),
                "depth": int(m.group(3)),
                "item_size": 0,
                "source_file": str(f.relative_to(root)),
            })

        # xSemaphoreCreateMutex
        for m in re.finditer(r'(\w+)\s*=\s*xSemaphoreCreateMutex\s*\(', content):
            mutexes.append({
                "name": m.group(1).replace("s_", "").replace("_mutex", ""),
                "source_file": str(f.relative_to(root)),
            })

        # Zephyr K_MUTEX_DEFINE
        for m in re.finditer(r'K_MUTEX_DEFINE\s*\(\s*(\w+)\s*\)', content):
            mutexes.append({
                "name": m.group(1),
                "source_file": str(f.relative_to(root)),
            })

        # xSemaphoreCreateBinary / xSemaphoreCreateCounting
        for m in re.finditer(r'(\w+)\s*=\s*xSemaphore(?:CreateBinary|CreateCounting)\s*\(', content):
            semaphores.append({
                "name": m.group(1).replace("s_", "").replace("_sem", ""),
                "type": "binary",
                "source_file": str(f.relative_to(root)),
            })

        # Zephyr K_SEM_DEFINE
        for m in re.finditer(r'K_SEM_DEFINE\s*\(\s*(\w+)\s*,', content):
            semaphores.append({
                "name": m.group(1),
                "type": "binary",
                "source_file": str(f.relative_to(root)),
            })

        # xTimerCreate
        for m in re.finditer(r'(\w+)\s*=\s*xTimerCreate\s*\(\s*"([^"]+)"\s*,\s*(?:pdMS_TO_TICKS\s*\(\s*)?(\d+)', content):
            timers.append({
                "name": m.group(2),
                "period_ms": int(m.group(3)),
                "source_file": str(f.relative_to(root)),
            })

        # Zephyr K_TIMER_DEFINE
        for m in re.finditer(r'K_TIMER_DEFINE\s*\(\s*(\w+)\s*,', content):
            timers.append({
                "name": m.group(1).replace("_timer", ""),
                "period_ms": 0,  # set at runtime
                "source_file": str(f.relative_to(root)),
            })

        # ISR: _IRQHandler
        for m in re.finditer(r'void\s+(\w+_IRQHandler)\s*\(', content):
            isrs.append({
                "name": m.group(1),
                "source_file": str(f.relative_to(root)),
            })

    return {
        "project": root.name,
        "tasks": tasks,
        "queues": queues,
        "mutexes": mutexes,
        "semaphores": semaphores,
        "timers": timers,
        "isrs": isrs,
    }


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

    # 5. 真实源码扫描 - mini_esp32
    mini_esp32 = ROOT / "tools" / "fixtures" / "mini_esp32"
    if mini_esp32.is_dir():
        scanned = scan_source_dir(str(mini_esp32))
        assert len(scanned["tasks"]) >= 3, f"Expected >=3 tasks, got {len(scanned['tasks'])}"
        assert len(scanned["queues"]) >= 2, f"Expected >=2 queues, got {len(scanned['queues'])}"
        assert len(scanned["mutexes"]) >= 1, f"Expected >=1 mutexes, got {len(scanned['mutexes'])}"
        assert len(scanned["timers"]) >= 1, f"Expected >=1 timers, got {len(scanned['timers'])}"
        print(f"[PASS] scan mini_esp32: {len(scanned['tasks'])} tasks, {len(scanned['queues'])} queues, {len(scanned['mutexes'])} mutexes, {len(scanned['timers'])} timers")
        passed += 1
    else:
        print("[SKIP] mini_esp32 not found")

    # 6. 真实源码扫描 - mini_zephyr
    mini_zephyr = ROOT / "tools" / "fixtures" / "mini_zephyr"
    if mini_zephyr.is_dir():
        scanned = scan_source_dir(str(mini_zephyr))
        assert len(scanned["tasks"]) >= 2, f"Expected >=2 tasks, got {len(scanned['tasks'])}"
        assert len(scanned["queues"]) >= 2, f"Expected >=2 queues, got {len(scanned['queues'])}"
        print(f"[PASS] scan mini_zephyr: {len(scanned['tasks'])} tasks, {len(scanned['queues'])} queues")
        passed += 1
    else:
        print("[SKIP] mini_zephyr not found")

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def from_generation_manifest(manifest: dict) -> dict:
    """从 generation_manifest.json 1.2 生成 RTOS 模型。"""
    from manifest_normalizer import normalize_manifest
    normalized = normalize_manifest(manifest)

    tasks = []
    for t in normalized.get("tasks", []):
        tasks.append({
            "name": t.get("name", ""),
            "priority": t.get("priority", 5),
            "stack_bytes": t.get("stack_bytes", 4096),
            "core_affinity": t.get("core_affinity", -1),
            "period_ms": t.get("period_ms", 0),
            "deadline_ms": t.get("deadline_ms", 0),
            "wcet_ms": t.get("wcet_ms", 0),
            "produces": t.get("produces", []),
            "consumes": t.get("consumes", []),
            "holds": t.get("holds", []),
            "description": t.get("description", ""),
        })

    queues = []
    for q in normalized.get("queues", []):
        queues.append({
            "name": q.get("name", ""),
            "depth": q.get("depth", 8),
            "item_size": q.get("item_size", 16),
            "producer_tasks": q.get("producer_tasks", []),
            "consumer_tasks": q.get("consumer_tasks", []),
            "backpressure": q.get("full_policy", q.get("backpressure", "")),
            "timeout_ms": q.get("send_timeout_ms", q.get("timeout_ms", 0)),
            "isr_safe": q.get("isr_safe", False),
            "description": q.get("description", ""),
        })

    mutexes = []
    for l in normalized.get("locks", []):
        if l.get("type") in ("mutex", "recursive_mutex"):
            mutexes.append({
                "name": l.get("name", ""),
                "holder_tasks": l.get("holder_tasks", []),
                "max_hold_ms": l.get("max_hold_ms", 0),
                "priority_ceiling": 0,
                "description": l.get("description", ""),
            })

    semaphores = []
    for l in normalized.get("locks", []):
        if l.get("type") in ("binary_semaphore", "counting_semaphore"):
            semaphores.append({
                "name": l.get("name", ""),
                "type": "binary" if "binary" in l.get("type", "") else "counting",
                "isr_safe": False,
                "description": l.get("description", ""),
            })

    timers = []
    for t in normalized.get("timers", []):
        timers.append({
            "name": t.get("name", ""),
            "period_ms": t.get("period_ms", 0),
            "callback_max_ms": t.get("callback_max_ms", 0),
            "auto_reload": t.get("auto_reload", True),
            "description": t.get("description", ""),
        })

    pools = []
    for p in normalized.get("memory_pools", []):
        pools.append({
            "name": p.get("name", ""),
            "block_size": p.get("block_size", 0),
            "num_blocks": p.get("num_blocks", 0),
            "owner_tasks": p.get("owner_tasks", []),
            "description": p.get("description", ""),
        })

    return {
        "project": normalized.get("generator", ""),
        "platform": normalized.get("platform", ""),
        "tasks": tasks,
        "queues": queues,
        "mutexes": mutexes,
        "semaphores": semaphores,
        "timers": timers,
        "isrs": [],
        "memory_pools": pools,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="RTOS System Model v13.0.1")
    parser.add_argument("--dir", help="从源码目录生成模型")
    parser.add_argument("--from-manifest", help="从 constraint_manifest.json 生成")
    parser.add_argument("--from-generation-manifest", help="从 generation_manifest.json 1.2 生成")
    parser.add_argument("--output", "-o", help="输出文件")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.from_generation_manifest:
        manifest = json.loads(Path(args.from_generation_manifest).read_text(encoding="utf-8"))
        model = from_generation_manifest(manifest)
    elif args.from_manifest:
        manifest = json.loads(Path(args.from_manifest).read_text(encoding="utf-8"))
        model = from_manifest(manifest)
    elif args.dir:
        model = scan_source_dir(args.dir)
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
