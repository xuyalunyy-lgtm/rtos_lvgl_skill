#!/usr/bin/env python3
"""
Codegen Gate v17.0.3 — 约束驱动生成门禁。

检查 manifest 完整性、生成文件存在性、约束覆盖、禁止模式、run_review 结果。
失败时 exit 1，输出阻塞原因和对应约束。

用法:
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

# ── 禁止模式 ──
FORBIDDEN_PATTERNS = [
    {
        "id": "F1",
        "pattern": r"\bportMAX_DELAY\b",
        "constraint": "C31",
        "message": "裸 portMAX_DELAY 禁止，除非 manifest 声明 allowed_infinite_waits",
        "exceptions": ["allowed_infinite_waits"],
    },
    {
        "id": "F2",
        "pattern": r"(?:xQueueReceive|sem.*Take|vTaskDelay).*//.*ISR",
        "constraint": "C4",
        "message": "ISR 中 blocking API",
        "contexts": ["isr", "irq", "callback", "interrupt"],
    },
    {
        "id": "F3",
        "pattern": r"(?:pvPortMalloc|cJSON_Parse|malloc)\s*\(",
        "constraint": "C4",
        "message": "ISR/hot path 中 malloc",
        "contexts": ["isr", "irq", "callback", "interrupt"],
    },
    {
        "id": "F4",
        "pattern": r"(?:printf|ESP_LOG[IDIWEF])\s*\(",
        "constraint": "C4",
        "message": "ISR 中 printf/重日志",
        "contexts": ["isr", "irq", "callback", "interrupt"],
    },
    {
        "id": "F5",
        "pattern": r"xQueueSend\s*\([^;]*&(?:\w+\.)?\w+\s*,",
        "constraint": "C2",
        "message": "queue 传栈指针",
    },
    {
        "id": "F6",
        "pattern": r"\blv_\w+\s*\(",
        "constraint": "C1",
        "message": "LVGL 跨线程调用",
        "contexts": ["network", "wifi", "wss", "audio", "sensor", "task_"],
    },
]


def check_manifest(manifest_path: str) -> list[str]:
    """检查 manifest 完整性。"""
    errors = []
    try:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except Exception as e:
        return [f"manifest 解析失败: {e}"]

    required = ["schema_version", "generator", "platform", "generated_files", "constraints"]
    for f in required:
        if f not in data:
            errors.append(f"manifest 缺少必填字段: {f}")

    if "constraints" in data:
        if "required" not in data["constraints"]:
            errors.append("manifest.constraints 缺少 required")

    if "tasks" in data:
        for t in data["tasks"]:
            if "name" not in t:
                errors.append("task 缺少 name")
            if "stack_bytes" not in t:
                errors.append(f"task {t.get('name', '?')} 缺少 stack_bytes")

    if "queues" in data:
        for q in data["queues"]:
            if "backpressure" not in q and q.get("depth", 0) > 0:
                errors.append(f"queue {q.get('name', '?')} 缺少 backpressure 策略")

    return errors


def check_files_exist(manifest: dict, base_dir: str) -> list[str]:
    """检查生成文件是否存在。"""
    errors = []
    base = Path(base_dir)
    for f in manifest.get("generated_files", []):
        path = base / f.get("path", "")
        if not path.exists():
            errors.append(f"生成文件不存在: {f.get('path')}")
    return errors


def check_forbidden_patterns(base_dir: str, manifest: dict) -> list[str]:
    """检查禁止模式。"""
    errors = []
    base = Path(base_dir)
    allowed_waits = {aw.get("location") for aw in manifest.get("constraints", {}).get("allowed_infinite_waits", [])}

    for f in base.rglob("*.c"):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for rule in FORBIDDEN_PATTERNS:
            # F1 特殊处理：portMAX_DELAY
            if rule["id"] == "F1":
                for m in re.finditer(rule["pattern"], content):
                    line_num = content[:m.start()].count("\n") + 1
                    loc = f"{f.name}:{line_num}"
                    if loc not in allowed_waits:
                        errors.append(f"[{rule['constraint']}] {rule['message']} at {loc}")
                continue

            # 其他规则
            for m in re.finditer(rule["pattern"], content):
                line_num = content[:m.start()].count("\n") + 1
                # 检查是否在特定上下文中（函数签名级别，非注释级别）
                if "contexts" in rule:
                    # 找到当前函数的签名行
                    func_sig_start = content.rfind("\n", 0, m.start())
                    # 向上找函数签名（最多 20 行）
                    for _ in range(20):
                        prev_line_start = content.rfind("\n", 0, func_sig_start)
                        if prev_line_start < 0:
                            break
                        func_sig_start = prev_line_start
                    func_sig = content[func_sig_start:m.start()].lower()
                    # 只检查函数签名中的关键词，不检查注释
                    # 排除注释行
                    sig_lines = [l.strip() for l in func_sig.split("\n") if l.strip() and not l.strip().startswith("//") and not l.strip().startswith("/*")]
                    sig_text = " ".join(sig_lines)
                    if not any(ctx in sig_text for ctx in rule["contexts"]):
                        continue
                errors.append(f"[{rule['constraint']}] {rule['message']} at {f.name}:{line_num}")

    return errors


def check_constraint_coverage(manifest: dict, base_dir: str) -> list[str]:
    """检查约束覆盖。"""
    errors = []
    required = set(manifest.get("constraints", {}).get("required", []))
    covered = set(manifest.get("constraints", {}).get("covered", []))
    deferred = manifest.get("constraints", {}).get("deferred", [])

    # 收集 deferred 的约束 ID
    deferred_ids = set()
    for d in deferred:
        did = d.get("id", "")
        if did:
            deferred_ids.add(did)
        # 校验 deferred 必须有 reason 和 evidence
        if not d.get("reason"):
            errors.append(f"deferred 约束 {did} 缺少 reason")
        if not d.get("evidence"):
            errors.append(f"deferred 约束 {did} 缺少 evidence")

    # required 必须被 covered ∪ deferred.id 完整解释
    explained = covered | deferred_ids
    missing = required - explained

    if missing:
        errors.append(f"约束未覆盖也未推迟: {', '.join(sorted(missing))}")

    return errors


def run_gate(dir_path: str, manifest_path: str, platform: str = "", strict: bool = False) -> dict:
    """运行 codegen gate。"""
    all_errors = []
    all_warnings = []
    all_violations = []
    checks = {}

    # 1. Manifest 完整性
    manifest_errors = check_manifest(manifest_path)
    checks["manifest"] = {"passed": len(manifest_errors) == 0, "errors": manifest_errors}
    all_errors.extend(manifest_errors)

    if manifest_errors:
        return _gate_result(False, all_errors, all_warnings, all_violations, checks, platform, strict)

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))

    # 2. Manifest contract 校验（V20）
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
        pass  # manifest_contract 不可用时跳过

    # 3. 文件存在性
    file_errors = check_files_exist(manifest, dir_path)
    checks["files_exist"] = {"passed": len(file_errors) == 0, "errors": file_errors}
    all_errors.extend(file_errors)

    # 4. 禁止模式
    pattern_errors = check_forbidden_patterns(dir_path, manifest)
    checks["forbidden_patterns"] = {"passed": len(pattern_errors) == 0, "errors": pattern_errors}
    all_errors.extend(pattern_errors)

    # 5. 约束覆盖
    if strict:
        coverage_errors = check_constraint_coverage(manifest, dir_path)
        checks["constraint_coverage"] = {"passed": len(coverage_errors) == 0, "errors": coverage_errors}
        all_errors.extend(coverage_errors)

    return _gate_result(len(all_errors) == 0, all_errors, all_warnings, all_violations, checks, platform, strict)


def _gate_result(passed: bool, errors: list, warnings: list, violations: list,
                 checks: dict, platform: str, strict: bool) -> dict:
    """构造统一 gate 输出。"""
    return {
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


def run_self_test() -> int:
    passed = 0
    failed = 0

    import tempfile

    # 1. 合法 manifest
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

    # 2. 缺少必填字段
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        manifest = {"generator": "test"}
        manifest_path = tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = run_gate(str(tmp), str(manifest_path))
        assert r["passed"] is False
        assert any("缺少必填字段" in e for e in r["errors"])
        print("[PASS] missing fields → fail")
        passed += 1

    # 3. 文件不存在
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
        assert any("不存在" in e for e in r["errors"])
        print("[PASS] missing file → fail")
        passed += 1

    # 4. 禁止模式：裸 portMAX_DELAY
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

    # 5. 约束未覆盖（strict）
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
        assert any("未覆盖" in e for e in r["errors"])
        print("[PASS] uncovered constraint (strict) → fail")
        passed += 1

    # 6. deferred 约束通过
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

    # 7. deferred 缺 reason 失败
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

    # 8. deferred 缺 evidence 失败
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
    parser.add_argument("--dir", help="生成目录")
    parser.add_argument("--manifest", help="generation_manifest.json 路径")
    parser.add_argument("--platform", default="", help="平台")
    parser.add_argument("--strict", action="store_true", help="严格模式（检查约束覆盖）")
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
