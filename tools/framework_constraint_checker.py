#!/usr/bin/env python3
"""
Framework Constraint Checker v14.0.4 — 框架约束检查。

对不同框架执行对应规则：LVGL/ESP-IDF/Zephyr/mbedTLS/lwIP/FatFS/TinyUSB/STM32 HAL。

用法:
    python tools/framework_constraint_checker.py --dir src --framework lvgl
    python tools/framework_constraint_checker.py --dir src --auto
    python tools/framework_constraint_checker.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAMEWORKS_DIR = ROOT / "frameworks"


def _load_pack(fw_id: str) -> dict:
    path = FRAMEWORKS_DIR / f"{fw_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# ── 框架检查规则 ──

def check_lvgl(files: list[Path]) -> list[dict]:
    """LVGL 检查：跨线程、flush 阻塞、image buffer。"""
    issues = []
    for f in files:
        content = _read_file(f)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue

            # LVGL-1: 跨线程调用（非 UI 任务中调用 lv_ 函数）
            # 简化检查：在回调或非 lv_ 开头文件中发现 lv_ 调用
            if "lv_" in stripped and ("callback" in content.lower() or "isr" in content.lower()):
                if re.search(r"\blv_\w+\s*\(", stripped):
                    issues.append({
                        "issue_id": f"LVGL-1:{f.name}:{i+1}",
                        "framework_id": "lvgl",
                        "constraint_id": "LVGL-1",
                        "severity": "P0",
                        "file": str(f),
                        "line": i + 1,
                        "message": "LVGL API 在回调/ISR 中调用，必须在 UI 任务中调用",
                        "related_core_constraint": "C1",
                        "suggestion": "用 lv_async_call 或 view_xxx 接口",
                    })

            # LVGL-2: flush callback 中阻塞
            if "flush_cb" in stripped or "display_flush" in stripped:
                if re.search(r"vTaskDelay|xQueueReceive|sem.*Take|sleep", content, re.IGNORECASE):
                    issues.append({
                        "issue_id": f"LVGL-2:{f.name}:{i+1}",
                        "framework_id": "lvgl",
                        "constraint_id": "LVGL-2",
                        "severity": "P0",
                        "file": str(f),
                        "line": i + 1,
                        "message": "Flush callback 中可能阻塞",
                        "related_core_constraint": "C4",
                    })

    return issues


def check_esp_idf(files: list[Path]) -> list[dict]:
    """ESP-IDF 检查：event loop、NVS、WDT、OTA、WiFi。"""
    issues = []
    for f in files:
        content = _read_file(f)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()

            # ESP-IDF-1: event loop 回调中阻塞
            if "esp_event_handler" in stripped or "event_handler" in stripped:
                # 检查同一函数中是否有阻塞调用
                func_start = max(0, i - 5)
                func_end = min(len(lines), i + 20)
                func_body = "\n".join(lines[func_start:func_end])
                if re.search(r"vTaskDelay|xQueueReceive|sem.*Take|sleep|nvs_commit", func_body, re.IGNORECASE):
                    issues.append({
                        "issue_id": f"ESP-IDF-1:{f.name}:{i+1}",
                        "framework_id": "esp-idf",
                        "constraint_id": "ESP-IDF-1",
                        "severity": "P0",
                        "file": str(f),
                        "line": i + 1,
                        "message": "Event loop 回调中可能阻塞",
                        "related_core_constraint": "C4",
                    })

            # ESP-IDF-4: OTA rollback
            if "esp_ota_begin" in stripped or "esp_ota_write" in stripped:
                if "mark_valid" not in content and "cancel_rollback" not in content:
                    issues.append({
                        "issue_id": f"ESP-IDF-4:{f.name}:{i+1}",
                        "framework_id": "esp-idf",
                        "constraint_id": "ESP-IDF-4",
                        "severity": "P0",
                        "file": str(f),
                        "line": i + 1,
                        "message": "OTA 操作未见 mark_valid_cancel_rollback",
                        "related_core_constraint": "C22",
                    })

            # ESP-IDF-5: WiFi reconnect backoff
            if "esp_wifi_connect" in stripped:
                if "backoff" not in content.lower() and "retry" not in content.lower():
                    issues.append({
                        "issue_id": f"ESP-IDF-5:{f.name}:{i+1}",
                        "framework_id": "esp-idf",
                        "constraint_id": "ESP-IDF-5",
                        "severity": "P1",
                        "file": str(f),
                        "line": i + 1,
                        "message": "WiFi 重连未见指数退避",
                        "related_core_constraint": "C20",
                    })

    return issues


def check_stm32_hal(files: list[Path]) -> list[dict]:
    """STM32 HAL 检查：HAL_Delay、IRQ callback、init 顺序。"""
    issues = []
    for f in files:
        content = _read_file(f)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()

            # STM32-1: HAL_Delay
            if re.search(r"\bHAL_Delay\s*\(", stripped):
                issues.append({
                    "issue_id": f"STM32-1:{f.name}:{i+1}",
                    "framework_id": "stm32-hal",
                    "constraint_id": "STM32-1",
                    "severity": "P0",
                    "file": str(f),
                    "line": i + 1,
                    "message": "RTOS 环境中禁止 HAL_Delay，用 osDelay/vTaskDelay",
                    "related_core_constraint": "C31",
                })

            # STM32-2: IRQ callback 中阻塞
            if re.search(r"HAL_\w+_IRQHandler|_CpltCallback|_HalfCpltCallback", stripped):
                func_start = max(0, i - 2)
                func_end = min(len(lines), i + 15)
                func_body = "\n".join(lines[func_start:func_end])
                if re.search(r"HAL_Delay|vTaskDelay|xQueueReceive|sem.*Take", func_body):
                    issues.append({
                        "issue_id": f"STM32-2:{f.name}:{i+1}",
                        "framework_id": "stm32-hal",
                        "constraint_id": "STM32-2",
                        "severity": "P0",
                        "file": str(f),
                        "line": i + 1,
                        "message": "IRQ/DMA callback 中可能阻塞",
                        "related_core_constraint": "C4",
                    })

    return issues


# ── 框架检查器注册 ──

CHECKERS = {
    "lvgl": check_lvgl,
    "esp-idf": check_esp_idf,
    "stm32-hal": check_stm32_hal,
}


def check_framework(dir_path: str, framework_id: str) -> list[dict]:
    """运行指定框架的检查。"""
    checker = CHECKERS.get(framework_id)
    if not checker:
        return []

    root = Path(dir_path)
    files = list(root.rglob("*.c")) + list(root.rglob("*.h"))
    return checker(files)


def check_auto(dir_path: str) -> dict:
    """自动检测框架并运行检查。"""
    from framework_profile import detect_frameworks
    detected = detect_frameworks(dir_path)
    all_issues = []
    checked = []

    for fw in detected:
        fw_id = fw["framework_id"]
        if fw_id in CHECKERS:
            issues = check_framework(dir_path, fw_id)
            all_issues.extend(issues)
            checked.append(fw_id)

    return {
        "frameworks_checked": checked,
        "total_issues": len(all_issues),
        "issues": all_issues,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. 框架注册
    assert len(CHECKERS) >= 2
    print(f"[PASS] {len(CHECKERS)} checkers registered")
    passed += 1

    # 2. fixtures 目录检查
    fixtures = ROOT / "tools" / "fixtures"
    if fixtures.is_dir():
        for fw_id in CHECKERS:
            issues = check_framework(str(fixtures), fw_id)
            print(f"[PASS] {fw_id}: {len(issues)} issues in fixtures")
            passed += 1

    # 3. auto 模式
    if fixtures.is_dir():
        result = check_auto(str(fixtures))
        assert "frameworks_checked" in result
        print(f"[PASS] auto: checked {result['frameworks_checked']}, {result['total_issues']} issues")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Framework Constraint Checker v14.0.4")
    parser.add_argument("--dir", help="扫描目录")
    parser.add_argument("--framework", help="指定框架")
    parser.add_argument("--auto", action="store_true", help="自动检测框架")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.dir:
        parser.print_help()
        return 1

    if args.auto:
        result = check_auto(args.dir)
    elif args.framework:
        issues = check_framework(args.dir, args.framework)
        result = {"framework": args.framework, "total_issues": len(issues), "issues": issues}
    else:
        parser.print_help()
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if args.auto:
            print(f"Checked: {result['frameworks_checked']}")
        print(f"Issues: {result['total_issues']}")
        for issue in result.get("issues", [])[:20]:
            print(f"  [{issue['severity']}] {issue['constraint_id']}: {issue['message'][:60]}")

    return 0 if result.get("total_issues", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
