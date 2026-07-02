#!/usr/bin/env python3
"""
Manifest Normalizer v19.0.1 — 统一 manifest 版本转换。

把旧 preset 的 string task/queue 转成 manifest 1.2 对象。
旧 schema 1.0/1.1 只兼容读取；V19 生成器一律输出 1.2。

用法:
    python tools/manifest_normalizer.py --input old_manifest.json --output new_manifest.json
    python tools/manifest_normalizer.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ── 默认值 ──

TASK_DEFAULTS = {
    "entry": "",
    "stack_bytes": 4096,
    "priority": 5,
    "core_affinity": -1,
    "lifecycle": "long_running",
    "exit_policy": "stop_token",
    "watchdog": "feed",
    "period_ms": 0,
    "deadline_ms": 0,
    "wcet_ms": 0,
    "produces": [],
    "consumes": [],
    "holds": [],
    "description": "",
}

QUEUE_DEFAULTS = {
    "depth": 8,
    "item_type": "generic",
    "item_size": 16,
    "producer_tasks": [],
    "consumer_tasks": [],
    "send_timeout_ms": 50,
    "recv_timeout_ms": 50,
    "full_policy": "drop_oldest",
    "drop_counter": "",
    "backpressure": "drop_oldest",
    "timeout_ms": 50,
    "isr_safe": False,
    "description": "",
}

LOCK_DEFAULTS = {
    "type": "mutex",
    "holder_tasks": [],
    "max_hold_ms": 50,
    "lock_order": 0,
    "priority_inheritance": True,
    "description": "",
}

TIMER_DEFAULTS = {
    "period_ms": 1000,
    "auto_reload": True,
    "callback_max_ms": 5,
    "notifies_tasks": [],
    "callback_policy": "deferred",
    "description": "",
}

POOL_DEFAULTS = {
    "block_size": 256,
    "num_blocks": 4,
    "owner_tasks": [],
    "full_policy": "block",
    "runtime_expand_allowed": False,
    "description": "",
}


def _normalize_task(task) -> dict:
    """规范化单个 task。"""
    if isinstance(task, str):
        return {**TASK_DEFAULTS, "name": task, "entry": f"{task}_func"}
    if isinstance(task, dict):
        result = {**TASK_DEFAULTS, **task}
        if not result.get("entry"):
            result["entry"] = f"{result['name']}_func"
        return result
    return {**TASK_DEFAULTS, "name": str(task), "entry": "unknown_func"}


def _normalize_queue(queue, tasks: list[dict] = None) -> dict:
    """规范化单个 queue。"""
    task_map = {t["name"]: t for t in (tasks or [])}

    if isinstance(queue, str):
        result = {**QUEUE_DEFAULTS, "name": queue}
    elif isinstance(queue, dict):
        result = {**QUEUE_DEFAULTS, **queue}
    else:
        result = {**QUEUE_DEFAULTS, "name": str(queue)}

    # 自动填充 producer/consumer 从 task 的 produces/consumes
    if not result.get("producer_tasks") and tasks:
        for t in tasks:
            if result["name"] in t.get("produces", []):
                result["producer_tasks"].append(t["name"])
    if not result.get("consumer_tasks") and tasks:
        for t in tasks:
            if result["name"] in t.get("consumes", []):
                result["consumer_tasks"].append(t["name"])

    return result


def _normalize_lock(lock) -> dict:
    """规范化单个 lock。"""
    if isinstance(lock, str):
        return {**LOCK_DEFAULTS, "name": lock}
    if isinstance(lock, dict):
        return {**LOCK_DEFAULTS, **lock}
    return {**LOCK_DEFAULTS, "name": str(lock)}


def _normalize_timer(timer) -> dict:
    """规范化单个 timer。"""
    if isinstance(timer, str):
        return {**TIMER_DEFAULTS, "name": timer}
    if isinstance(timer, dict):
        return {**TIMER_DEFAULTS, **timer}
    return {**TIMER_DEFAULTS, "name": str(timer)}


def _normalize_pool(pool) -> dict:
    """规范化单个 memory pool。"""
    if isinstance(pool, str):
        return {**POOL_DEFAULTS, "name": pool}
    if isinstance(pool, dict):
        return {**POOL_DEFAULTS, **pool}
    return {**POOL_DEFAULTS, "name": str(pool)}


def normalize_manifest(data: dict) -> dict:
    """规范化 manifest 到 1.2 格式。"""
    version = data.get("schema_version", "1.0")

    # 已经是 1.2 且字段完整，直接返回
    if version == "1.2":
        return data

    # 规范化 tasks
    tasks = [_normalize_task(t) for t in data.get("tasks", [])]

    # 规范化 queues（依赖 tasks 信息）
    queues = [_normalize_queue(q, tasks) for q in data.get("queues", [])]

    # 规范化 locks
    locks = [_normalize_lock(l) for l in data.get("locks", [])]

    # 规范化 timers
    timers = [_normalize_timer(t) for t in data.get("timers", [])]

    # 规范化 memory_pools
    pools = [_normalize_pool(p) for p in data.get("memory_pools", [])]

    # constraints 兼容
    constraints = data.get("constraints", {})
    if "evidence" not in constraints:
        constraints["evidence"] = []

    result = {
        **data,
        "schema_version": "1.2",
        "tasks": tasks,
        "queues": queues,
        "locks": locks,
        "timers": timers,
        "memory_pools": pools,
        "constraints": constraints,
    }

    return result


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. String task normalization
    t = _normalize_task("audio_task")
    assert t["name"] == "audio_task"
    assert t["entry"] == "audio_task_func"
    assert t["lifecycle"] == "long_running"
    assert t["exit_policy"] == "stop_token"
    print("[PASS] string task normalization")
    passed += 1

    # 2. Dict task normalization
    t = _normalize_task({"name": "ui_task", "priority": 3, "stack_bytes": 8192})
    assert t["priority"] == 3
    assert t["stack_bytes"] == 8192
    assert t["lifecycle"] == "long_running"  # default
    print("[PASS] dict task normalization")
    passed += 1

    # 3. String queue normalization
    q = _normalize_queue("cmd_q")
    assert q["name"] == "cmd_q"
    assert q["full_policy"] == "drop_oldest"
    assert q["send_timeout_ms"] == 50
    print("[PASS] string queue normalization")
    passed += 1

    # 4. Queue with task context
    tasks = [{"name": "producer", "produces": ["data_q"], "consumes": []}]
    q = _normalize_queue("data_q", tasks)
    assert "producer" in q["producer_tasks"]
    print("[PASS] queue auto-fill from tasks")
    passed += 1

    # 5. Full manifest normalization
    old = {
        "schema_version": "1.0",
        "generator": "test",
        "platform": "esp32",
        "generated_files": [],
        "tasks": ["sensor", "ui"],
        "queues": ["sensor_q", "ui_cmd_q"],
        "constraints": {"required": ["C8"], "covered": ["C8"]},
    }
    result = normalize_manifest(old)
    assert result["schema_version"] == "1.2"
    assert len(result["tasks"]) == 2
    assert result["tasks"][0]["entry"] == "sensor_func"
    assert len(result["queues"]) == 2
    assert result["queues"][0]["full_policy"] == "drop_oldest"
    print("[PASS] full manifest normalization")
    passed += 1

    # 6. Already 1.2 passthrough
    v12 = {"schema_version": "1.2", "generator": "test", "platform": "esp32",
           "generated_files": [], "tasks": [], "queues": [], "locks": [], "timers": [],
           "memory_pools": [], "constraints": {"required": []}}
    result = normalize_manifest(v12)
    assert result["schema_version"] == "1.2"
    print("[PASS] 1.2 passthrough")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manifest Normalizer v19.0.1")
    parser.add_argument("--input", help="输入 manifest JSON")
    parser.add_argument("--output", help="输出规范化 manifest JSON")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.input:
        parser.print_help()
        return 1

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = normalize_manifest(data)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"已保存: {args.output}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
