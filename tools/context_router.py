#!/usr/bin/env python3
"""
Context Router — 上下文路由器。

根据 workflow、platform、constraints 输出最小读取计划，帮助 agent
确定性知道：该读哪些文件、别读哪些文件、默认最多读多少。

用法:
    python tools/context_router.py --workflow code_review --platform esp32 --json
    python tools/context_router.py --workflow crash_debug --platform zephyr --constraints C2 C3 --json
    python tools/context_router.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Workflow 定义 ──

WORKFLOWS = {
    "code_review": {
        "file": "workflows/l2_code_review.md",
        "constraint_shards": ["review", "memory"],
        "description": "代码审查",
    },
    "project_review": {
        "file": "workflows/l2_project_review.md",
        "constraint_shards": ["review", "platform"],
        "description": "项目审查",
    },
    "crash_debug": {
        "file": "workflows/debug_crash.md",
        "constraint_shards": ["review", "rtos", "platform"],
        "description": "崩溃调试",
    },
    "memory_analysis": {
        "file": "workflows/l2_memory_analysis.md",
        "constraint_shards": ["memory", "rtos"],
        "description": "内存分析",
    },
    "sdk_trim": {
        "file": "workflows/l3_sdk_trim.md",
        "constraint_shards": ["platform"],
        "description": "SDK 裁剪",
    },
    "new_module": {
        "file": "workflows/l3_new_module.md",
        "constraint_shards": ["rtos", "review"],
        "description": "新模块",
    },
    "bring_up": {
        "file": "workflows/l3_bring_up.md",
        "constraint_shards": ["platform", "rtos"],
        "description": "板级 Bring-up",
    },
    "lvgl_page": {
        "file": "workflows/l3_lvgl_page.md",
        "constraint_shards": ["review", "media"],
        "description": "LVGL 页面生成",
    },
    "hw_sw_debug": {
        "file": "workflows/hw_sw_cocodebug.md",
        "constraint_shards": ["platform", "review"],
        "description": "软硬联调",
    },
}

# ── 约束分片映射 ──

CONSTRAINT_SHARDS = {
    "review": "references/constraint_review.md",
    "memory": "references/constraint_memory.md",
    "rtos": "references/constraint_rtos.md",
    "platform": "references/constraint_platform.md",
    "media": "references/constraint_media.md",
    "ota": "references/constraint_ota.md",
    "recover": "references/constraint_recover.md",
}

# ── 约束 ID → 分片映射 ──

CONSTRAINT_TO_SHARD = {
    "C1": "review", "C2": "review", "C3": "review", "C4": "review",
    "C5": "review", "C6": "review",
    "C7": "memory", "C28": "memory", "C36": "memory",
    "C8": "rtos", "C15": "rtos", "C17": "rtos",
    "C29": "rtos", "C30": "rtos", "C31": "rtos", "C32": "rtos",
    "C33": "rtos", "C34": "rtos", "C35": "rtos",
    "C43": "rtos", "C44": "rtos",
    "C18": "platform", "C19": "platform", "C20": "platform", "C21": "platform",
    "C23": "platform", "C42": "platform", "C45": "platform",
    "C25": "media", "C26": "media", "C27": "media",
    "C9": "ota", "C22": "ota", "C24": "ota",
    "C37": "recover", "C38": "recover", "C39": "recover",
    "C40": "recover", "C41": "recover",
    "C10": "media", "C11": "review", "C12": "review", "C13": "review",
    "C14": "review", "C16": "review",
}

# ── 平台文档映射 ──

PLATFORM_DOCS = {
    "esp32": {
        "primary": True,
        "doc": "platforms/esp32.md",
        "sdk_map": "platforms/esp32_sdk_map.yaml",
    },
    "zephyr": {
        "primary": True,
        "doc": "platforms/zephyr.md",
        "sdk_map": "platforms/zephyr_sdk_map.yaml",
    },
    "stm32": {
        "primary": False,
        "doc": "platforms/stm32.md",
        "sdk_map": "platforms/stm32_sdk_map.yaml",
    },
    "jl": {
        "primary": False,
        "doc": "platforms/jl.md",
        "sdk_map": "platforms/jl_sdk_map.yaml",
    },
    "bk": {
        "primary": False,
        "doc": "platforms/bk.md",
        "sdk_map": "platforms/bk_sdk_map.yaml",
    },
}

# ── 禁止默认加载的文件 ──

FORBIDDEN_BY_DEFAULT = [
    "references/constraint_detail.md",
    "references/iteration_log.md",
    "references/CHANGELOG_archive.md",
    "references/iteration_log_archive_2026Q2.md",
]

# ── Token 预算估算（粗略） ──

def estimate_tokens(file_path: Path) -> int:
    """粗略估算文件 token 数（1 token ≈ 4 bytes）。"""
    if not file_path.is_file():
        return 0
    return file_path.stat().st_size // 4


def build_load_plan(workflow: str, platform: str, constraints: list[str] | None = None) -> dict:
    """构建读取计划。"""
    wf = WORKFLOWS.get(workflow)
    if not wf:
        return {"error": f"Unknown workflow: {workflow}"}

    plat = PLATFORM_DOCS.get(platform)
    if not plat:
        return {"error": f"Unknown platform: {platform}"}

    required_files = []
    reasons = {}

    # 1. 必读：quick index
    qi = "references/constraint_quick_index.md"
    required_files.append(qi)
    reasons[qi] = "C1-C45 快速查找索引"

    # 2. 必读：workflow 文件
    required_files.append(wf["file"])
    reasons[wf["file"]] = f"Workflow: {wf['description']}"

    # 3. 按 workflow 选择约束分片
    shards = set(wf["constraint_shards"])
    # 如果指定了约束，缩小范围
    if constraints:
        for c in constraints:
            shard = CONSTRAINT_TO_SHARD.get(c.upper())
            if shard:
                shards.add(shard)
    for shard_name in sorted(shards):
        shard_file = CONSTRAINT_SHARDS.get(shard_name)
        if shard_file and shard_file not in required_files:
            required_files.append(shard_file)
            reasons[shard_file] = f"约束分片: {shard_name}"

    # 4. 按 platform 选择平台文档
    if plat["doc"] not in required_files:
        required_files.append(plat["doc"])
        reasons[plat["doc"]] = f"平台文档: {platform}"
    if plat["sdk_map"] not in required_files:
        required_files.append(plat["sdk_map"])
        reasons[plat["sdk_map"]] = f"SDK 映射: {platform}"

    # 5. SDK abstraction（checker 需要）
    sdk_abs = "references/sdk_abstraction.yaml"
    if sdk_abs not in required_files:
        required_files.append(sdk_abs)
        reasons[sdk_abs] = "SDK 抽象注册表"

    # 6. 核心规则
    core = "references/core_rules.md"
    if core not in required_files:
        required_files.append(core)
        reasons[core] = "核心规则"

    # 计算 token 预算
    total_tokens = 0
    files_with_reason = []
    for f in required_files:
        fp = ROOT / f
        tokens = estimate_tokens(fp)
        total_tokens += tokens
        files_with_reason.append({
            "path": f,
            "reason": reasons.get(f, ""),
            "estimated_tokens": tokens,
        })

    return {
        "workflow": workflow,
        "workflow_description": wf["description"],
        "platform": platform,
        "platform_primary": plat["primary"],
        "required_files": files_with_reason,
        "forbidden_by_default": FORBIDDEN_BY_DEFAULT,
        "token_budget_hint": total_tokens,
        "constraint_shards_loaded": sorted(shards),
    }


def run_self_test() -> int:
    """运行自测。"""
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

    # 测试所有 9 个 workflow
    for wf_id in WORKFLOWS:
        plan = build_load_plan(wf_id, "esp32")
        check(f"{wf_id}: no error", "error" not in plan)
        check(f"{wf_id}: has required_files", len(plan.get("required_files", [])) > 0)
        check(f"{wf_id}: has token_budget_hint", plan.get("token_budget_hint", 0) > 0)

    # 测试 platform 选择
    plan_esp32 = build_load_plan("code_review", "esp32")
    plan_zephyr = build_load_plan("code_review", "zephyr")
    check("esp32 platform doc", any("esp32" in f["path"] for f in plan_esp32["required_files"]))
    check("zephyr platform doc", any("zephyr" in f["path"] for f in plan_zephyr["required_files"]))

    # 测试 constraints 缩小范围
    plan_c3 = build_load_plan("code_review", "esp32", ["C3"])
    check("C3 adds review shard", any("constraint_review" in f["path"] for f in plan_c3["required_files"]))

    # 测试 forbidden_by_default
    plan = build_load_plan("crash_debug", "esp32")
    check("forbidden_by_default present", len(plan.get("forbidden_by_default", [])) > 0)
    check("constraint_detail forbidden", "references/constraint_detail.md" in plan.get("forbidden_by_default", []))

    # 测试未知 workflow
    plan_bad = build_load_plan("unknown_workflow", "esp32")
    check("unknown workflow returns error", "error" in plan_bad)

    # 测试未知 platform
    plan_bad_plat = build_load_plan("code_review", "unknown_platform")
    check("unknown platform returns error", "error" in plan_bad_plat)

    # 测试 JSON 输出
    plan_json = json.dumps(build_load_plan("code_review", "esp32"), ensure_ascii=False)
    check("JSON output valid", len(plan_json) > 100)

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Context Router — 上下文路由器")
    parser.add_argument("--workflow", "-w",
                        choices=list(WORKFLOWS.keys()),
                        help="Workflow ID")
    parser.add_argument("--platform", "-p",
                        choices=list(PLATFORM_DOCS.keys()),
                        default="esp32",
                        help="目标平台")
    parser.add_argument("--constraints", "-c", nargs="*",
                        help="约束 ID（如 C2 C3），缩小读取范围")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 格式")
    parser.add_argument("--self-test", action="store_true",
                        help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.workflow:
        parser.error("--workflow is required")

    plan = build_load_plan(args.workflow, args.platform, args.constraints)

    if args.json:
        json.dump(plan, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        if "error" in plan:
            print(f"Error: {plan['error']}", file=sys.stderr)
            return 1

        print(f"Context Router: {plan['workflow_description']} @ {plan['platform']}")
        print(f"Token budget hint: ~{plan['token_budget_hint']} tokens")
        print(f"\nRequired files ({len(plan['required_files'])}):")
        for f in plan["required_files"]:
            print(f"  {f['path']} — {f['reason']} (~{f['estimated_tokens']} tokens)")
        print(f"\nForbidden by default:")
        for f in plan["forbidden_by_default"]:
            print(f"  {f}")
        print(f"\nConstraint shards: {', '.join(plan['constraint_shards_loaded'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
