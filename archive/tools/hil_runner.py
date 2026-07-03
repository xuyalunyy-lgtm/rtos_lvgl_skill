#!/usr/bin/env python3
"""
HIL Runner v12.0.2 — 硬件在环测试运行器。

支持 probe/build/flash/monitor/smoke/run/report，默认 --dry-run。
真实烧录必须显式 --apply 且 board policy 允许。

用法:
    python tools/hil_runner.py probe --board fake-esp32
    python tools/hil_runner.py run --board fake-esp32 --scenario boot_smoke --dry-run
    python tools/hil_runner.py run --board fake-esp32 --scenario boot_smoke --apply
    python tools/hil_runner.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARDS_DIR = ROOT / ".codex" / "boards"
SCENARIOS_DIR = ROOT / ".codex" / "hil_scenarios"


def load_board(board_id: str) -> dict:
    path = BOARDS_DIR / f"{board_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Board 不存在: {board_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_scenario(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario 不存在: {scenario_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_boards() -> list[str]:
    if not BOARDS_DIR.is_dir():
        return []
    return sorted(p.stem for p in BOARDS_DIR.glob("*.json"))


def list_scenarios() -> list[str]:
    if not SCENARIOS_DIR.is_dir():
        return []
    return sorted(p.stem for p in SCENARIOS_DIR.glob("*.json"))


def _run_cmd(cmd: str, timeout: int = 30) -> dict:
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(ROOT),
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "error": "timeout"}
    except Exception as e:
        return {"exit_code": -1, "error": str(e)}


def cmd_probe(board: dict, dry_run: bool) -> dict:
    """探测板卡连接状态。"""
    probe_cmd = board.get("probe_cmd", "")
    if not probe_cmd:
        return {"ok": False, "error": "board 未定义 probe_cmd"}

    if dry_run:
        return {"ok": True, "board_id": board["board_id"], "output": f"[DRY-RUN] {probe_cmd}"}

    r = _run_cmd(probe_cmd)
    return {"ok": r["exit_code"] == 0, "board_id": board["board_id"], "output": r.get("stdout", "")}


def cmd_build(board: dict, dry_run: bool) -> dict:
    """构建固件。"""
    build_cmd = board.get("build_cmd", "")
    if not build_cmd:
        return {"ok": False, "error": "board 未定义 build_cmd"}

    if dry_run:
        return {"ok": True, "output": f"[DRY-RUN] {build_cmd}"}

    r = _run_cmd(build_cmd, timeout=300)
    return {"ok": r["exit_code"] == 0, "output": r.get("stdout", "")[-500:]}


def cmd_flash(board: dict, firmware: str, dry_run: bool) -> dict:
    """烧录固件。"""
    if not board.get("safety_flags", {}).get("allow_flash", False):
        return {"ok": False, "error": "board safety_flags.allow_flash=false"}

    flash_cmd = board.get("flash_cmd", "").replace("{firmware}", firmware)
    if not flash_cmd:
        return {"ok": False, "error": "board 未定义 flash_cmd"}

    if dry_run:
        return {"ok": True, "output": f"[DRY-RUN] {flash_cmd}"}

    r = _run_cmd(flash_cmd, timeout=120)
    return {"ok": r["exit_code"] == 0, "output": r.get("stdout", "")[-500:]}


def cmd_monitor(board: dict, duration: int, dry_run: bool) -> tuple[list[str], dict]:
    """监控串口日志。"""
    if dry_run:
        # 返回模拟日志
        fake_log = [
            "I (100) boot: ESP-IDF v5.1 starting",
            "I (200) heap: free=245760",
            "I (300) wifi: connected to AP",
            "I (400) main: app started",
            "I (500) task: audio_task alive",
        ]
        return fake_log, {"ok": True, "output": "[DRY-RUN] monitor"}

    monitor_cmd = board.get("monitor_cmd", "")
    if not monitor_cmd:
        return [], {"ok": False, "error": "board 未定义 monitor_cmd"}

    # 实际监控（简化版：运行指定时间后停止）
    r = _run_cmd(f"{monitor_cmd} --duration {duration}", timeout=duration + 10)
    lines = (r.get("stdout", "") + r.get("stderr", "")).splitlines()
    return lines, {"ok": r["exit_code"] == 0}


def cmd_reset(board: dict, dry_run: bool) -> dict:
    """复位板卡。"""
    if not board.get("safety_flags", {}).get("allow_reset", False):
        return {"ok": False, "error": "board safety_flags.allow_reset=false"}

    reset_cmd = board.get("reset_cmd", "")
    if not reset_cmd:
        return {"ok": False, "error": "board 未定义 reset_cmd"}

    if dry_run:
        return {"ok": True, "output": f"[DRY-RUN] {reset_cmd}"}

    r = _run_cmd(reset_cmd)
    return {"ok": r["exit_code"] == 0, "output": r.get("stdout", "")}


def match_events(log_lines: list[str], expected_events: list[dict]) -> list[dict]:
    """匹配日志行与期望事件。"""
    results = []
    for event in expected_events:
        pattern = event.get("pattern", "")
        matched = False
        actual_line = ""
        for line in log_lines:
            if re.search(pattern, line, re.IGNORECASE):
                matched = True
                actual_line = line.strip()
                break
        results.append({
            "pattern": pattern,
            "matched": matched,
            "actual_line": actual_line[:200],
            "required": event.get("required", True),
        })
    return results


def run_scenario(board: dict, scenario: dict, dry_run: bool = True) -> dict:
    """运行 HIL 场景。"""
    run_id = f"hil-{int(time.time())}"
    start = time.time()

    # 检查 board capabilities
    board_caps = set(board.get("capabilities", []))
    required_caps = set(scenario.get("required_capabilities", []))
    missing_caps = required_caps - board_caps
    if missing_caps and not dry_run:
        return {
            "run_id": run_id, "board_id": board["board_id"],
            "scenario_id": scenario["scenario_id"],
            "status": "error", "dry_run": dry_run,
            "failure_reason": f"Board 缺少能力: {missing_caps}",
        }

    # 执行步骤
    log_lines = []
    steps_ok = True

    for step in scenario.get("steps", []):
        action = step.get("action", "")
        value = step.get("value", "")

        if action == "reset":
            r = cmd_reset(board, dry_run)
            if not r["ok"]:
                steps_ok = False
                break
        elif action == "wait":
            if not dry_run:
                time.sleep(min(step.get("timeout_seconds", 5), 10))
        elif action == "send_cmd":
            if dry_run:
                log_lines.append(f"[DRY-RUN] cmd: {value}")
            else:
                r = _run_cmd(f"echo '{value}' > {board['serial_port']}", timeout=5)
        elif action == "wait_event":
            if dry_run:
                log_lines.append(f"[DRY-RUN] wait_event: {value}")
        elif action == "flash":
            r = cmd_flash(board, value, dry_run)
            if not r["ok"]:
                steps_ok = False
                break

    # 监控日志
    monitor_duration = scenario.get("timeout_seconds", 30)
    monitor_lines, _ = cmd_monitor(board, min(monitor_duration, 10), dry_run)
    log_lines.extend(monitor_lines)

    # 匹配事件
    events_matched = match_events(log_lines, scenario.get("expected_events", []))

    # 判定状态
    all_required = all(
        e["matched"] for e in events_matched if e.get("required", True)
    )
    status = "pass" if (steps_ok and all_required) else "fail"

    # 失败归因
    failure_reason = ""
    failure_attribution = ""
    if not steps_ok:
        failure_reason = "步骤执行失败"
    elif not all_required:
        unmatched = [e for e in events_matched if not e["matched"] and e.get("required", True)]
        failure_reason = f"未匹配事件: {[e['pattern'] for e in unmatched]}"
        # 归因
        attr_map = scenario.get("failure_attribution", {})
        for key, val in attr_map.items():
            if any(key in e.get("actual_line", "").lower() or key in e["pattern"].lower() for e in unmatched):
                failure_attribution = val
                break

    duration = time.time() - start

    return {
        "run_id": run_id,
        "board_id": board["board_id"],
        "scenario_id": scenario["scenario_id"],
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(duration, 2),
        "dry_run": dry_run,
        "events_matched": events_matched,
        "telemetry_summary": {
            "boot_ok": any("boot" in l.lower() or "started" in l.lower() for l in log_lines),
            "heap_free_min": 245760 if dry_run else None,
        },
        "failure_reason": failure_reason,
        "failure_attribution": failure_attribution,
        "related_constraints": scenario.get("related_constraints", []),
        "raw_log_path": "",
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. Board loading
    boards = list_boards()
    assert len(boards) >= 1, f"Expected >=1 boards, got {len(boards)}"
    print(f"[PASS] {len(boards)} boards found")
    passed += 1

    # 2. Scenario loading
    scenarios = list_scenarios()
    assert len(scenarios) >= 1
    print(f"[PASS] {len(scenarios)} scenarios found")
    passed += 1

    # 3. Load fake board
    board = load_board("fake-esp32")
    assert board["board_id"] == "fake-esp32"
    assert "flash" in board["capabilities"]
    print("[PASS] load fake-esp32")
    passed += 1

    # 4. Probe dry-run
    r = cmd_probe(board, dry_run=True)
    assert r["ok"]
    print("[PASS] probe dry-run")
    passed += 1

    # 5. Flash dry-run
    r = cmd_flash(board, "firmware.bin", dry_run=True)
    assert r["ok"]
    print("[PASS] flash dry-run")
    passed += 1

    # 6. Flash blocked by safety
    board_no_flash = {**board, "safety_flags": {"allow_flash": False}}
    r = cmd_flash(board_no_flash, "firmware.bin", dry_run=False)
    assert not r["ok"]
    print("[PASS] flash blocked by safety")
    passed += 1

    # 7. Run scenario dry-run
    scenario = load_scenario("boot_smoke")
    result = run_scenario(board, scenario, dry_run=True)
    assert result["status"] == "pass"
    assert result["dry_run"] is True
    print("[PASS] boot_smoke dry-run")
    passed += 1

    # 8. Event matching
    logs = ["I (100) boot: started", "I (200) heap: free=100000"]
    events = [{"pattern": "boot.*started", "required": True}, {"pattern": "WIFI_CONNECTED", "required": True}]
    results = match_events(logs, events)
    assert results[0]["matched"] is True
    assert results[1]["matched"] is False
    print("[PASS] event matching")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="HIL Runner v12.0.2")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("probe", help="探测板卡").add_argument("--board", required=True)
    sub.add_parser("list-boards", help="列出板卡")
    sub.add_parser("list-scenarios", help="列出场景")

    p_run = sub.add_parser("run", help="运行场景")
    p_run.add_argument("--board", required=True)
    p_run.add_argument("--scenario", required=True)
    p_run.add_argument("--dry-run", action="store_true", default=True)
    p_run.add_argument("--apply", action="store_true", help="真实执行（覆盖 dry-run）")
    p_run.add_argument("--output", "-o", help="结果输出文件")
    p_run.add_argument("--json", action="store_true")

    parser.add_argument("--self-test", action="store_true")

    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "list-boards":
        for b in list_boards():
            print(b)
        return 0

    if args.command == "list-scenarios":
        for s in list_scenarios():
            print(s)
        return 0

    board = load_board(args.board)

    if args.command == "probe":
        r = cmd_probe(board, dry_run=True)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r["ok"] else 1

    if args.command == "run":
        scenario = load_scenario(args.scenario)
        dry_run = not args.apply
        result = run_scenario(board, scenario, dry_run=dry_run)

        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"结果已保存: {args.output}")

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Board:    {result['board_id']}")
            print(f"Scenario: {result['scenario_id']}")
            print(f"Status:   {result['status']}")
            print(f"Dry-run:  {result['dry_run']}")
            if result.get("failure_reason"):
                print(f"Failure:  {result['failure_reason']}")

        return 0 if result["status"] == "pass" else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
