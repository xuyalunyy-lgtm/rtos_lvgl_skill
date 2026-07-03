#!/usr/bin/env python3
"""
Session Guard v15.0.3 — 会话严格模式纪律检查。

检查输出是否满足 skill 纪律：workflow 选择、平台/框架声明、约束引用、验证计划。

用法:
    python tools/session_guard.py --check-response response.md
    python tools/session_guard.py --check-plan plan.json --strict
    python tools/session_guard.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── 关键词库 ──

WORKFLOW_KEYWORDS = {
    "l2_code_review": ["code review", "代码审查", "审查", "review", "run_review"],
    "debug_crash": ["crash", "崩溃", "hardfault", "backtrace", "coredump", "复位"],
    "l3_new_module": ["新模块", "new module", "module_contract", "生成模块"],
    "l3_bring_up": ["bring up", "项目生成", "scaffold", "新项目", "project_scaffold"],
    "l2_auto_repair": ["auto fix", "自动修复", "fix plan", "修复建议"],
    "l2_memory_analysis": ["内存", "memory", "泄漏", "leak", "heap", "stack"],
    "l2_rtos_system_review": ["RTOS", "任务拓扑", "调度", "优先级", "task graph"],
    "l2_release_qualification": ["发布", "release", "qualification"],
}

PLATFORM_KEYWORDS = ["esp32", "stm32", "zephyr", "jl", "bk", "freertos"]
FRAMEWORK_KEYWORDS = ["esp-idf", "lvgl", "mbedtls", "lwip", "fatfs", "littlefs", "tinyusb", "cmsis", "stm32-hal"]
CONSTRAINT_PATTERN = re.compile(r"\bC\d{1,2}(?:\.\d+)?\b|\b[A-Z]+-\d+\b")
VERIFICATION_KEYWORDS = ["self-test", "skill_iterate", "run_review", "checker", "验证", "验证命令"]


def check_response(text: str, strict: bool = False) -> dict:
    """检查响应是否满足 skill 纪律。"""
    text_lower = text.lower()
    issues = []
    checks = {}

    # 1. Workflow 选择
    workflow_found = []
    for wf, keywords in WORKFLOW_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                workflow_found.append(wf)
                break
    checks["workflow_selected"] = len(workflow_found) > 0
    if strict and not workflow_found:
        issues.append("严格模式：未选择 workflow")

    # 2. 平台声明
    platform_found = [p for p in PLATFORM_KEYWORDS if p in text_lower]
    checks["platform_declared"] = len(platform_found) > 0
    if strict and not platform_found:
        issues.append("严格模式：未声明目标平台")

    # 3. 框架声明
    framework_found = [f for f in FRAMEWORK_KEYWORDS if f in text_lower]
    checks["framework_declared"] = len(framework_found) > 0

    # 4. 约束引用
    constraints = CONSTRAINT_PATTERN.findall(text)
    checks["constraint_referenced"] = len(constraints) > 0
    if strict and not constraints:
        issues.append("严格模式：未引用约束域")

    # 5. 验证计划
    verification_found = [v for v in VERIFICATION_KEYWORDS if v in text_lower]
    checks["verification_planned"] = len(verification_found) > 0

    # 6. 非 RTOS 降级检测
    non_rtos_indicators = ["python", "javascript", "css", "html", "数据库", "sql", "api 网关"]
    is_non_rtos = any(ind in text_lower for ind in non_rtos_indicators) and not any(
        rtos in text_lower for rtos in ["freertos", "rtos", "嵌入式", "固件", "mcu"]
    )
    checks["is_rtos_task"] = not is_non_rtos
    if is_non_rtos:
        issues = [i for i in issues if "严格模式" not in i]  # 非 RTOS 任务放宽

    passed = len(issues) == 0 if strict else (
        checks.get("workflow_selected", False) or checks.get("platform_declared", False)
    )

    return {
        "passed": passed,
        "strict": strict,
        "checks": checks,
        "issues": issues,
        "detected": {
            "workflows": workflow_found,
            "platforms": platform_found,
            "frameworks": framework_found,
            "constraints": constraints[:10],
        },
    }


def check_plan(plan: dict, strict: bool = False) -> dict:
    """检查计划是否满足 skill 纪律。"""
    issues = []

    # 1. 有 intent
    if not plan.get("intent"):
        issues.append("计划缺少 intent")

    # 2. 有 files_to_change
    if not plan.get("files_to_change"):
        issues.append("计划缺少 files_to_change")

    # 3. 有 risk_level
    if not plan.get("risk_level"):
        issues.append("计划缺少 risk_level")

    # 4. strict 模式额外检查
    if strict:
        # 必须有 verification_commands 或 acceptance_tests
        if not plan.get("verification_commands") and not plan.get("acceptance_tests"):
            issues.append("严格模式：计划缺少验证命令或验收条件")

        # 必须有 rollback
        if not plan.get("rollback") and not plan.get("rollback_strategy"):
            issues.append("严格模式：计划缺少回滚方式")

    passed = len(issues) == 0

    return {
        "passed": passed,
        "strict": strict,
        "issues": issues,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. 完整 RTOS 响应
    text = """
    我将使用 l2_code_review 工作流审查这段 ESP32 代码。
    涉及框架：ESP-IDF、LVGL。
    相关约束：C1（LVGL 线程安全）、C4（ISR 安全）、C29（模块契约）。
    验证：运行 run_review.py --self-test 和 skill_iterate.py --check。
    """
    r = check_response(text, strict=True)
    assert r["passed"] is True
    assert r["checks"]["workflow_selected"] is True
    assert r["checks"]["platform_declared"] is True
    assert r["checks"]["constraint_referenced"] is True
    print("[PASS] complete RTOS response → pass")
    passed += 1

    # 2. 缺平台信息
    text2 = "我来帮你审查这段代码。"
    r2 = check_response(text2, strict=True)
    assert r2["passed"] is False
    assert any("平台" in i for i in r2["issues"])
    print("[PASS] missing platform → fail in strict")
    passed += 1

    # 3. 非 RTOS 任务降级
    text3 = "帮我写一个 Python 脚本处理 CSV 文件。"
    r3 = check_response(text3, strict=True)
    assert r3["checks"]["is_rtos_task"] is False
    print("[PASS] non-RTOS task → relaxed")
    passed += 1

    # 4. 非严格模式宽松通过
    text4 = "ESP32 项目代码审查"
    r4 = check_response(text4, strict=False)
    assert r4["passed"] is True
    print("[PASS] non-strict mode → pass")
    passed += 1

    # 5. 计划检查 - 完整
    plan = {
        "intent": "修复 cJSON 泄漏",
        "files_to_change": ["tools/test.py"],
        "risk_level": "low",
        "verification_commands": ["python tools/run_review.py --self-test"],
        "rollback": "git checkout .",
    }
    r5 = check_plan(plan, strict=True)
    assert r5["passed"] is True
    print("[PASS] complete plan → pass")
    passed += 1

    # 6. 计划检查 - 缺验证
    plan2 = {"intent": "test", "files_to_change": ["x.py"], "risk_level": "low"}
    r6 = check_plan(plan2, strict=True)
    assert r6["passed"] is False
    assert any("验证" in i for i in r6["issues"])
    print("[PASS] plan missing verification → fail")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Session Guard v15.0.3")
    parser.add_argument("--check-response", help="检查响应文件")
    parser.add_argument("--check-plan", help="检查计划文件")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.check_response:
        text = Path(args.check_response).read_text(encoding="utf-8")
        r = check_response(text, strict=args.strict)
    elif args.check_plan:
        plan = json.loads(Path(args.check_plan).read_text(encoding="utf-8"))
        r = check_plan(plan, strict=args.strict)
    else:
        parser.print_help()
        return 1

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Passed: {r['passed']}")
        if r.get("issues"):
            for i in r["issues"]:
                print(f"  - {i}")
        if r.get("detected"):
            d = r["detected"]
            if d.get("workflows"):
                print(f"  Workflows: {d['workflows']}")
            if d.get("platforms"):
                print(f"  Platforms: {d['platforms']}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
