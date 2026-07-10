#!/usr/bin/env python3
"""
RTOS Scanner — lightweight project fact scanner.

Scans RTOS primitives (task/queue/mutex/semaphore/timer/ISR/DMA/cache/OTA) from source code,
outputs topology summary. Reports only by default, does not block gate.

Usage:
    python tools/rtos_scanner.py --dir src
    python tools/rtos_scanner.py --dir src --json
    python tools/rtos_scanner.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field

ROOT = Path(__file__).resolve().parent.parent

# Import SDK lookup for platform-aware scanning
try:
    from sdk_lookup import SdkLookup
except ImportError:
    SdkLookup = None


@dataclass
class RtosSummary:
    """RTOS topology summary."""
    platform: str = "esp32"
    tasks: list = field(default_factory=list)
    queues: list = field(default_factory=list)
    mutexes: list = field(default_factory=list)
    semaphores: list = field(default_factory=list)
    timers: list = field(default_factory=list)
    isr_handlers: list = field(default_factory=list)
    dma_allocs: list = field(default_factory=list)
    ota_calls: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def collect_c_files(dir_path: Path) -> list[Path]:
    """Collect C/C++ source files."""
    return sorted(dir_path.rglob("*.c")) + sorted(dir_path.rglob("*.h"))


def strip_comments(content: str) -> str:
    """Remove C/C++ comments."""
    content = re.sub(r"//.*?$", "", content, flags=re.MULTILINE)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    return content


def scan_file(file_path: Path, lookup=None) -> dict:
    """Scan a single file, return discovered RTOS primitives."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    content = strip_comments(content)
    result = {
        "tasks": [],
        "queues": [],
        "mutexes": [],
        "semaphores": [],
        "timers": [],
        "isr_handlers": [],
        "dma_allocs": [],
        "ota_calls": [],
    }

    # Task creation patterns
    task_patterns = [
        (r"xTaskCreate\s*\(", "xTaskCreate"),
        (r"xTaskCreatePinnedToCore\s*\(", "xTaskCreatePinnedToCore"),
        (r"xTaskCreateStatic\s*\(", "xTaskCreateStatic"),
        (r"k_thread_create\s*\(", "k_thread_create"),
        (r"K_THREAD_DEFINE\s*\(", "K_THREAD_DEFINE"),
        (r"thread_fork\s*\(", "thread_fork"),
        (r"rtos_create_thread\s*\(", "rtos_create_thread"),
    ]
    for pattern, name in task_patterns:
        matches = re.findall(pattern, content)
        if matches:
            result["tasks"].append({"api": name, "count": len(matches), "file": str(file_path)})

    # Queue creation patterns
    queue_patterns = [
        (r"xQueueCreate\s*\(", "xQueueCreate"),
        (r"K_MSGQ_DEFINE\s*\(", "K_MSGQ_DEFINE"),
        (r"os_q_create\s*\(", "os_q_create"),
        (r"rtos_init_queue\s*\(", "rtos_init_queue"),
    ]
    for pattern, name in queue_patterns:
        matches = re.findall(pattern, content)
        if matches:
            result["queues"].append({"api": name, "count": len(matches), "file": str(file_path)})

    # Mutex creation patterns
    mutex_patterns = [
        (r"xSemaphoreCreateMutex\s*\(", "xSemaphoreCreateMutex"),
        (r"K_MUTEX_DEFINE\s*\(", "K_MUTEX_DEFINE"),
        (r"os_mutex_create\s*\(", "os_mutex_create"),
        (r"rtos_init_mutex\s*\(", "rtos_init_mutex"),
    ]
    for pattern, name in mutex_patterns:
        matches = re.findall(pattern, content)
        if matches:
            result["mutexes"].append({"api": name, "count": len(matches), "file": str(file_path)})

    # Semaphore creation patterns
    sem_patterns = [
        (r"xSemaphoreCreateBinary\s*\(", "xSemaphoreCreateBinary"),
        (r"xSemaphoreCreateCounting\s*\(", "xSemaphoreCreateCounting"),
        (r"K_SEM_DEFINE\s*\(", "K_SEM_DEFINE"),
        (r"os_sem_create\s*\(", "os_sem_create"),
        (r"rtos_init_semaphore\s*\(", "rtos_init_semaphore"),
    ]
    for pattern, name in sem_patterns:
        matches = re.findall(pattern, content)
        if matches:
            result["semaphores"].append({"api": name, "count": len(matches), "file": str(file_path)})

    # Timer creation patterns
    timer_patterns = [
        (r"xTimerCreate\s*\(", "xTimerCreate"),
        (r"K_TIMER_DEFINE\s*\(", "K_TIMER_DEFINE"),
        (r"sys_timer_add\s*\(", "sys_timer_add"),
        (r"rtos_init_timer\s*\(", "rtos_init_timer"),
    ]
    for pattern, name in timer_patterns:
        matches = re.findall(pattern, content)
        if matches:
            result["timers"].append({"api": name, "count": len(matches), "file": str(file_path)})

    # ISR handler patterns
    isr_pattern = re.compile(r"void\s+(\w+IRQHandler|\w+_ISR|\w+_Callback)\s*\(")
    isr_matches = isr_pattern.findall(content)
    if isr_matches:
        result["isr_handlers"].extend([{"name": m, "file": str(file_path)} for m in isr_matches])

    # DMA allocation patterns
    dma_patterns = [
        (r"heap_caps_malloc\s*\([^)]*MALLOC_CAP_DMA", "heap_caps_malloc(DMA)"),
        (r"dma_buffer_alloc\s*\(", "dma_buffer_alloc"),
    ]
    for pattern, name in dma_patterns:
        matches = re.findall(pattern, content)
        if matches:
            result["dma_allocs"].append({"api": name, "count": len(matches), "file": str(file_path)})

    # OTA patterns
    ota_patterns = [
        (r"esp_ota_begin\s*\(", "esp_ota_begin"),
        (r"esp_ota_write\s*\(", "esp_ota_write"),
        (r"esp_ota_end\s*\(", "esp_ota_end"),
        (r"boot_request_upgrade\s*\(", "boot_request_upgrade"),
    ]
    for pattern, name in ota_patterns:
        matches = re.findall(pattern, content)
        if matches:
            result["ota_calls"].append({"api": name, "count": len(matches), "file": str(file_path)})

    return result


def scan_directory(dir_path: Path, platform: str = "esp32") -> RtosSummary:
    """Scan directory, generate RTOS topology summary."""
    summary = RtosSummary(platform=platform)
    c_files = collect_c_files(dir_path)

    if not c_files:
        summary.warnings.append(f"No C/C++ files found in {dir_path}")
        return summary

    lookup = None
    if SdkLookup:
        try:
            lookup = SdkLookup(platform)
        except Exception:
            pass

    for f in c_files:
        result = scan_file(f, lookup)
        if not result:
            continue

        for key in ["tasks", "queues", "mutexes", "semaphores", "timers",
                     "isr_handlers", "dma_allocs", "ota_calls"]:
            getattr(summary, key).extend(result.get(key, []))

    return summary


def format_summary(summary: RtosSummary) -> str:
    """Format summary as readable text."""
    lines = [f"RTOS Topology Summary (platform: {summary.platform})"]
    lines.append("=" * 50)

    if summary.tasks:
        lines.append(f"\nTasks ({len(summary.tasks)}):")
        for t in summary.tasks:
            lines.append(f"  - {t['api']} x{t['count']} in {Path(t['file']).name}")

    if summary.queues:
        lines.append(f"\nQueues ({len(summary.queues)}):")
        for q in summary.queues:
            lines.append(f"  - {q['api']} x{q['count']} in {Path(q['file']).name}")

    if summary.mutexes:
        lines.append(f"\nMutexes ({len(summary.mutexes)}):")
        for m in summary.mutexes:
            lines.append(f"  - {m['api']} x{m['count']} in {Path(m['file']).name}")

    if summary.semaphores:
        lines.append(f"\nSemaphores ({len(summary.semaphores)}):")
        for s in summary.semaphores:
            lines.append(f"  - {s['api']} x{s['count']} in {Path(s['file']).name}")

    if summary.timers:
        lines.append(f"\nTimers ({len(summary.timers)}):")
        for t in summary.timers:
            lines.append(f"  - {t['api']} x{t['count']} in {Path(t['file']).name}")

    if summary.isr_handlers:
        lines.append(f"\nISR Handlers ({len(summary.isr_handlers)}):")
        for i in summary.isr_handlers:
            lines.append(f"  - {i['name']} in {Path(i['file']).name}")

    if summary.dma_allocs:
        lines.append(f"\nDMA Allocations ({len(summary.dma_allocs)}):")
        for d in summary.dma_allocs:
            lines.append(f"  - {d['api']} x{d['count']} in {Path(d['file']).name}")

    if summary.ota_calls:
        lines.append(f"\nOTA Calls ({len(summary.ota_calls)}):")
        for o in summary.ota_calls:
            lines.append(f"  - {o['api']} x{o['count']} in {Path(o['file']).name}")

    if summary.warnings:
        lines.append(f"\nWarnings:")
        for w in summary.warnings:
            lines.append(f"  - {w}")

    total = (len(summary.tasks) + len(summary.queues) + len(summary.mutexes) +
             len(summary.semaphores) + len(summary.timers))
    lines.append(f"\nTotal RTOS primitives: {total}")

    return "\n".join(lines)


def run_self_test() -> int:
    """Run self-test."""
    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name}")

    # Test with fixtures directory
    fixtures_dir = ROOT / "tools" / "fixtures"
    if fixtures_dir.is_dir():
        summary = scan_directory(fixtures_dir, "esp32")
        check("Scan fixtures directory", len(summary.tasks) > 0 or len(summary.queues) > 0)
        check("Format summary", len(format_summary(summary)) > 0)

    # Test with examples directory
    examples_dir = ROOT / "examples"
    if examples_dir.is_dir():
        summary = scan_directory(examples_dir, "esp32")
        check("Scan examples directory", True)  # Should not crash
        check("Summary has platform", summary.platform == "esp32")

    # Test JSON output
    summary = RtosSummary(platform="zephyr")
    summary.tasks.append({"api": "k_thread_create", "count": 1, "file": "test.c"})
    json_out = json.dumps({"platform": summary.platform, "tasks": summary.tasks})
    check("JSON output", "k_thread_create" in json_out)

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="RTOS Scanner — lightweight topology scanner")
    parser.add_argument("--dir", type=str, help="Source directory to scan")
    parser.add_argument("--platform", default="esp32",
                        choices=["esp32", "stm32", "jl", "bk", "zephyr"],
                        help="Target platform")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--self-test", action="store_true", help="Run self-test")

    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.dir:
        parser.error("--dir is required")

    dir_path = Path(args.dir)
    if not dir_path.is_dir():
        print(f"Error: directory not found: {dir_path}", file=sys.stderr)
        return 1

    summary = scan_directory(dir_path, args.platform)

    if args.json:
        import dataclasses
        print(json.dumps(dataclasses.asdict(summary), indent=2, ensure_ascii=False))
    else:
        print(format_summary(summary))

    return 0


if __name__ == "__main__":
    sys.exit(main())
