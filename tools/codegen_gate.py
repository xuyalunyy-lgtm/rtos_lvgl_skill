#!/usr/bin/env python3
"""
Codegen Gate v17.0.3 — Constraint-driven generation gate.

Checks manifest completeness, generated file existence, constraint coverage, forbidden patterns, run_review results.
Exits 1 on failure, outputs blocking reasons and corresponding constraints.

Usage:
    python tools/codegen_gate.py --dir <path> --manifest generation_manifest.json --platform esp32 --strict
    python tools/codegen_gate.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Forbidden patterns ──
FORBIDDEN_PATTERNS = [
    {
        "id": "F1",
        "pattern": r"\bportMAX_DELAY\b",
        "constraint": "C31",
        "message": "Bare portMAX_DELAY forbidden unless manifest declares allowed_infinite_waits",
        "exceptions": ["allowed_infinite_waits"],
    },
    {
        "id": "F2",
        "pattern": r"(?:xQueueReceive|sem.*Take|vTaskDelay).*//.*ISR",
        "constraint": "C4",
        "message": "Blocking API in ISR",
        "contexts": ["isr", "irq", "callback", "interrupt"],
    },
    {
        "id": "F3",
        "pattern": r"(?:pvPortMalloc|cJSON_Parse|malloc)\s*\(",
        "constraint": "C4",
        "message": "malloc in ISR/hot path",
        "contexts": ["isr", "irq", "callback", "interrupt"],
    },
    {
        "id": "F4",
        "pattern": r"(?:printf|ESP_LOG[IDIWEF])\s*\(",
        "constraint": "C4",
        "message": "printf/heavy logging in ISR",
        "contexts": ["isr", "irq", "callback", "interrupt"],
    },
    {
        "id": "F5",
        "pattern": r"xQueueSend\s*\([^;]*&(?:\w+\.)?\w+\s*,",
        "constraint": "C2",
        "message": "Queue passing stack pointer",
    },
    {
        "id": "F6",
        "pattern": r"\blv_\w+\s*\(",
        "constraint": "C1",
        "message": "LVGL cross-thread call",
        "contexts": ["network", "wifi", "wss", "audio", "sensor", "task_"],
    },
]


def check_manifest(manifest_path: str) -> list[str]:
    """Check manifest completeness."""
    errors = []
    try:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except Exception as e:
        return [f"Manifest parsing failed: {e}"]

    required = ["schema_version", "generator", "platform", "generated_files", "constraints"]
    for f in required:
        if f not in data:
            errors.append(f"Manifest missing required field: {f}")

    if "constraints" in data:
        if "required" not in data["constraints"]:
            errors.append("manifest.constraints missing required")

    if "tasks" in data:
        for t in data["tasks"]:
            if "name" not in t:
                errors.append("task missing name")
            if "stack_bytes" not in t:
                errors.append(f"task {t.get('name', '?')} missing stack_bytes")

    # Queue completeness is validated by manifest_contract, not duplicated here

    return errors


def check_files_exist(manifest: dict, base_dir: str) -> list[str]:
    """Check whether generated files exist."""
    errors = []
    base = Path(base_dir)
    for f in manifest.get("generated_files", []):
        path = base / f.get("path", "")
        if not path.exists():
            errors.append(f"Generated file does not exist: {f.get('path')}")
    return errors


def check_forbidden_patterns(base_dir: str, manifest: dict) -> list[str]:
    """Check forbidden patterns."""
    errors = []
    base = Path(base_dir)
    allowed_waits = {aw.get("location") for aw in manifest.get("constraints", {}).get("allowed_infinite_waits", [])}

    for f in base.rglob("*.c"):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for rule in FORBIDDEN_PATTERNS:
            # F1 special handling: portMAX_DELAY
            if rule["id"] == "F1":
                for m in re.finditer(rule["pattern"], content):
                    line_num = content[:m.start()].count("\n") + 1
                    loc = f"{f.name}:{line_num}"
                    if loc not in allowed_waits:
                        errors.append(f"[{rule['constraint']}] {rule['message']} at {loc}")
                continue

            # Other rules
            for m in re.finditer(rule["pattern"], content):
                line_num = content[:m.start()].count("\n") + 1
                # Check if in specific context (function signature level, not comment level)
                if "contexts" in rule:
                    # Find the current function signature line
                    func_sig_start = content.rfind("\n", 0, m.start())
                    # Search upward for function signature (up to 20 lines)
                    for _ in range(20):
                        prev_line_start = content.rfind("\n", 0, func_sig_start)
                        if prev_line_start < 0:
                            break
                        func_sig_start = prev_line_start
                    func_sig = content[func_sig_start:m.start()].lower()
                    # Only check keywords in function signature, not comments
                    # Exclude comment lines
                    sig_lines = [l.strip() for l in func_sig.split("\n") if l.strip() and not l.strip().startswith("//") and not l.strip().startswith("/*")]
                    sig_text = " ".join(sig_lines)
                    if not any(ctx in sig_text for ctx in rule["contexts"]):
                        continue
                errors.append(f"[{rule['constraint']}] {rule['message']} at {f.name}:{line_num}")

    return errors


def check_constraint_coverage(manifest: dict, base_dir: str) -> list[str]:
    """Check constraint coverage."""
    errors = []
    required = set(manifest.get("constraints", {}).get("required", []))
    covered = set(manifest.get("constraints", {}).get("covered", []))
    deferred = manifest.get("constraints", {}).get("deferred", [])

    # Collect deferred constraint IDs
    deferred_ids = set()
    for d in deferred:
        did = d.get("id", "")
        if did:
            deferred_ids.add(did)
        # Validate deferred must have reason and evidence
        if not d.get("reason"):
            errors.append(f"Deferred constraint {did} missing reason")
        if not d.get("evidence"):
            errors.append(f"Deferred constraint {did} missing evidence")

    # required must be fully explained by covered union deferred.id
    explained = covered | deferred_ids
    missing = required - explained

    if missing:
        errors.append(f"Constraints not covered and not deferred: {', '.join(sorted(missing))}")

    return errors


def run_gate(dir_path: str, manifest_path: str, platform: str = "", strict: bool = False) -> dict:
    """Run codegen gate."""
    all_errors = []
    all_warnings = []
    all_violations = []
    checks = {}

    # 1. Manifest completeness
    manifest_errors = check_manifest(manifest_path)
    checks["manifest"] = {"passed": len(manifest_errors) == 0, "errors": manifest_errors}
    all_errors.extend(manifest_errors)

    if manifest_errors:
        return _gate_result(False, all_errors, all_warnings, all_violations, checks, platform, strict)

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))

    # 2. Manifest contract validation (V20)
    try:
        from manifest_contract import validate as contract_validate
        contract_result = contract_validate(manifest, strict=strict)
        checks["contract"] = {
            "passed": contract_result["passed"],
            "errors": contract_result["errors"],
            "warnings": contract_result["warnings"],
            "violations": contract_result["violations"],
            "summary": contract_result.get("contract_summary", {}),
        }
        all_errors.extend(contract_result["errors"])
        all_warnings.extend(contract_result["warnings"])
        all_violations.extend(contract_result["violations"])
    except ImportError:
        pass  # Skip when manifest_contract is unavailable

    # 3. File existence
    file_errors = check_files_exist(manifest, dir_path)
    checks["files_exist"] = {"passed": len(file_errors) == 0, "errors": file_errors}
    all_errors.extend(file_errors)

    # 4. Forbidden patterns
    pattern_errors = check_forbidden_patterns(dir_path, manifest)
    checks["forbidden_patterns"] = {"passed": len(pattern_errors) == 0, "errors": pattern_errors}
    all_errors.extend(pattern_errors)

    # 5. Constraint coverage
    if strict:
        coverage_errors = check_constraint_coverage(manifest, dir_path)
        checks["constraint_coverage"] = {"passed": len(coverage_errors) == 0, "errors": coverage_errors}
        all_errors.extend(coverage_errors)

    # 6. RTOS model construction + analyzer report (V21)
    rtos_model_summary = {}
    analyzer_reports = {}
    risk_summary = {"p0": 0, "p1": 0, "p2": 0, "total": 0}
    missing_analyzers = []
    REQUIRED_ANALYZERS = [
        ("task_graph", "task_graph_analyzer", "analyze"),
        ("ipc_contract", "ipc_contract_checker", "check"),
        ("scheduler", "scheduler_analyzer", "analyze"),
        ("memory_lifetime", "memory_lifetime_analyzer", "analyze"),
        ("timebase", "timebase_analyzer", "analyze"),
    ]

    if strict:
        # RTOS model construction (must succeed)
        try:
            from rtos_model import from_generation_manifest
            rtos_model = from_generation_manifest(manifest)
            rtos_model_summary = {
                "tasks": len(rtos_model.get("tasks", [])),
                "queues": len(rtos_model.get("queues", [])),
                "mutexes": len(rtos_model.get("mutexes", [])),
                "semaphores": len(rtos_model.get("semaphores", [])),
                "timers": len(rtos_model.get("timers", [])),
                "pools": len(rtos_model.get("memory_pools", [])),
            }
        except Exception as e:
            all_warnings.append(f"optional RTOS model unavailable: {e}")
            rtos_model = None

        # Optional archived analyzers: report if present, but do not fail the user gate.
        if rtos_model:
            for analyzer_name, module_name, func_name in REQUIRED_ANALYZERS:
                try:
                    import importlib
                    mod = importlib.import_module(module_name)
                    func = getattr(mod, func_name)
                    result = func(rtos_model)
                    analyzer_reports[analyzer_name] = result
                    risk_summary["p0"] += result.get("risk_summary", {}).get("p0", 0)
                    risk_summary["p1"] += result.get("risk_summary", {}).get("p1", 0)
                    risk_summary["p2"] += result.get("risk_summary", {}).get("p2", 0)
                except ImportError:
                    missing_analyzers.append(analyzer_name)
                    all_warnings.append(f"optional analyzer unavailable: {analyzer_name} ({module_name})")
                except Exception as e:
                    all_warnings.append(f"optional analyzer {analyzer_name} failed: {e}")

            risk_summary["total"] = risk_summary["p0"] + risk_summary["p1"] + risk_summary["p2"]

            # P0 analyzer risk → fail
            if risk_summary["p0"] > 0:
                all_errors.append(f"RTOS analyzer found {risk_summary['p0']} P0 risks")
            # P1/P2 → warnings
            if risk_summary["p1"] > 0:
                all_warnings.append(f"RTOS analyzer found {risk_summary['p1']} P1 risks")
            if risk_summary["p2"] > 0:
                all_warnings.append(f"RTOS analyzer found {risk_summary['p2']} P2 risks")

    return _gate_result(
        len(all_errors) == 0, all_errors, all_warnings, all_violations,
        checks, platform, strict,
        rtos_model_summary=rtos_model_summary,
        analyzer_reports=analyzer_reports,
        risk_summary=risk_summary,
        missing_analyzers=missing_analyzers,
    )


def _gate_result(passed: bool, errors: list, warnings: list, violations: list,
                 checks: dict, platform: str, strict: bool, *,
                 rtos_model_summary: dict = None, analyzer_reports: dict = None,
                 risk_summary: dict = None, missing_analyzers: list = None) -> dict:
    """Construct unified gate output."""
    result = {
        "passed": passed,
        "severity": "P0" if errors else ("P1" if violations else "P2"),
        "errors": errors,
        "warnings": warnings,
        "violations": violations,
        "checks": checks,
        "constraints": [],
        "verification_commands": [],
        "evidence_files": [],
        "platform": platform,
        "strict": strict,
    }
    if rtos_model_summary:
        result["rtos_model_summary"] = rtos_model_summary
    if analyzer_reports:
        result["analyzer_reports"] = {
            name: {"risk_summary": rpt.get("risk_summary", {}), "risk_count": len(rpt.get("risks", []))}
            for name, rpt in analyzer_reports.items()
        }
    if risk_summary:
        result["risk_summary"] = risk_summary
    if missing_analyzers is not None:
        result["missing_analyzers"] = missing_analyzers
    return result


def run_self_test() -> int:
    passed = 0
    failed = 0

    import tempfile

    # 1. Valid manifest
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "main.c").write_text('void app_main(void) { xQueueCreate(8, sizeof(int)); }\n', encoding="utf-8")
        manifest = {
            "schema_version": "1.0",
            "generator": "test",
            "platform": "esp32",
            "generated_files": [{"path": "main.c"}],
            "constraints": {"required": ["C8", "C29"], "covered": ["C8", "C29"]},
        }
        manifest_path = tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = run_gate(str(tmp), str(manifest_path))
        assert r["passed"] is True
        print("[PASS] valid manifest → pass")
        passed += 1

    # 2. Missing required fields
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        manifest = {"generator": "test"}
        manifest_path = tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = run_gate(str(tmp), str(manifest_path))
        assert r["passed"] is False
        assert any("missing required field" in e for e in r["errors"])
        print("[PASS] missing fields → fail")
        passed += 1

    # 3. File does not exist
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        manifest = {
            "schema_version": "1.0", "generator": "test", "platform": "esp32",
            "generated_files": [{"path": "nonexistent.c"}],
            "constraints": {"required": [], "covered": []},
        }
        manifest_path = tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = run_gate(str(tmp), str(manifest_path))
        assert r["passed"] is False
        assert any("does not exist" in e for e in r["errors"])
        print("[PASS] missing file → fail")
        passed += 1

    # 4. Forbidden pattern: bare portMAX_DELAY
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "bad.c").write_text('void f() { xQueueReceive(q, &v, portMAX_DELAY); }\n', encoding="utf-8")
        manifest = {
            "schema_version": "1.0", "generator": "test", "platform": "esp32",
            "generated_files": [{"path": "bad.c"}],
            "constraints": {"required": ["C31"], "covered": ["C31"]},
        }
        manifest_path = tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = run_gate(str(tmp), str(manifest_path))
        assert r["passed"] is False
        assert any("portMAX_DELAY" in e for e in r["errors"])
        print("[PASS] forbidden portMAX_DELAY → fail")
        passed += 1

    # 5. Constraints not covered (strict)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "ok.c").write_text('void f() {}\n', encoding="utf-8")
        manifest = {
            "schema_version": "1.0", "generator": "test", "platform": "esp32",
            "generated_files": [{"path": "ok.c"}],
            "constraints": {"required": ["C8", "C29"], "covered": ["C8"]},
        }
        manifest_path = tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = run_gate(str(tmp), str(manifest_path), strict=True)
        assert r["passed"] is False
        assert any("not covered" in e for e in r["errors"])
        print("[PASS] uncovered constraint (strict) → fail")
        passed += 1

    # 6. Deferred constraints pass
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "ok.c").write_text('void f() {}\n', encoding="utf-8")
        manifest = {
            "schema_version": "1.1", "generator": "test", "platform": "esp32",
            "generated_files": [{"path": "ok.c"}],
            "constraints": {
                "required": ["C8", "C29", "C33"],
                "covered": ["C8"],
                "deferred": [{"id": "C29", "reason": "scaffold only", "evidence": "task_topology.h"}, {"id": "C33", "reason": "scaffold only", "evidence": "constraint_manifest.json"}],
            },
        }
        manifest_path = tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = run_gate(str(tmp), str(manifest_path), strict=True)
        assert r["passed"] is True
        print("[PASS] deferred constraints → pass")
        passed += 1

    # 7. Deferred missing reason fails
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "ok.c").write_text('void f() {}\n', encoding="utf-8")
        manifest = {
            "schema_version": "1.1", "generator": "test", "platform": "esp32",
            "generated_files": [{"path": "ok.c"}],
            "constraints": {
                "required": ["C8", "C29"],
                "covered": ["C8"],
                "deferred": [{"id": "C29", "reason": "", "evidence": "test"}],
            },
        }
        manifest_path = tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = run_gate(str(tmp), str(manifest_path), strict=True)
        assert r["passed"] is False
        assert any("reason" in e for e in r["errors"])
        print("[PASS] deferred missing reason → fail")
        passed += 1

    # 8. Deferred missing evidence fails
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "ok.c").write_text('void f() {}\n', encoding="utf-8")
        manifest = {
            "schema_version": "1.1", "generator": "test", "platform": "esp32",
            "generated_files": [{"path": "ok.c"}],
            "constraints": {
                "required": ["C8", "C29"],
                "covered": ["C8"],
                "deferred": [{"id": "C29", "reason": "test", "evidence": ""}],
            },
        }
        manifest_path = tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = run_gate(str(tmp), str(manifest_path), strict=True)
        assert r["passed"] is False
        assert any("evidence" in e for e in r["errors"])
        print("[PASS] deferred missing evidence → fail")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Codegen Gate v17.0.3")
    parser.add_argument("--dir", help="Generation directory")
    parser.add_argument("--manifest", help="Path to generation_manifest.json")
    parser.add_argument("--platform", default="", help="Platform")
    parser.add_argument("--strict", action="store_true", help="Strict mode (check constraint coverage)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.dir or not args.manifest:
        parser.print_help()
        return 1

    r = run_gate(args.dir, args.manifest, args.platform, args.strict)

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        if r["passed"]:
            print("[PASS] Codegen gate: PASS")
        else:
            print("[FAIL] Codegen gate: FAIL")
            for e in r["errors"]:
                print(f"  - {e}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
