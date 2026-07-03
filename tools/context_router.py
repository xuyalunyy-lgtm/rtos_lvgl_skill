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

# ── 微分片映射 ──

MICRO_SHARDS = {
    "C3": "references/micro_C03.md",
    "C4": "references/micro_C04.md",
    "C7": "references/micro_C07.md",
    "C8": "references/micro_C08.md",
    "C9": "references/micro_C09.md",
    "C22": "references/micro_C22.md",
    "C25": "references/micro_C25.md",
    "C28": "references/micro_C28.md",
    "C31": "references/micro_C31.md",
    "C36": "references/micro_C36.md",
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

# ── 质量样例 ──

QUALITY_CASES = {
    "cjson_review_esp32": {
        "title": "ESP32 cJSON 泄漏审查",
        "workflow": "code_review",
        "platform": "esp32",
        "constraints": ["C3", "C7"],
        "quality_expectations": [
            "识别 cJSON_Parse/Delete 配对问题",
            "推荐 goto cleanup 模板",
            "注意 PSRAM/heap 差异",
        ],
        "upgrade_triggers": [
            "需要完整 cJSON checker 规则",
            "需要 ESP32 heap_caps 详细 API",
        ],
    },
    "zephyr_crash_log": {
        "title": "Zephyr kernel oops 诊断",
        "workflow": "crash_debug",
        "platform": "zephyr",
        "constraints": ["C4", "C8", "C31"],
        "quality_expectations": [
            "识别 ISR 阻塞问题",
            "识别启动顺序错误",
            "识别永久等待",
        ],
        "upgrade_triggers": [
            "需要完整 Zephyr kernel API",
            "需要 devicetree 配置细节",
        ],
    },
    "esp32_memory_pressure": {
        "title": "ESP32 堆持续下降",
        "workflow": "memory_analysis",
        "platform": "esp32",
        "constraints": ["C7", "C28", "C36"],
        "quality_expectations": [
            "识别未配对 free",
            "识别 PSRAM 误用",
            "识别 DMA cache 问题",
        ],
        "upgrade_triggers": [
            "需要完整 heap_caps API",
            "需要 DMA buffer 对齐细节",
        ],
    },
    "ota_rollback_review": {
        "title": "ESP32 OTA 自动回滚",
        "workflow": "code_review",
        "platform": "esp32",
        "constraints": ["C9", "C22"],
        "quality_expectations": [
            "识别未 mark_valid",
            "识别签名验证缺失",
            "识别回滚路径不清",
        ],
        "upgrade_triggers": [
            "需要完整 OTA API",
            "需要 secure boot 配置",
        ],
    },
    "media_dma_lifecycle": {
        "title": "ESP32 音视频 DMA buffer 生命周期",
        "workflow": "code_review",
        "platform": "esp32",
        "constraints": ["C25", "C28"],
        "quality_expectations": [
            "识别 DMA buffer 未对齐",
            "识别 cache 未 invalidate",
            "识别旧帧复用",
        ],
        "upgrade_triggers": [
            "需要完整 DMA API",
            "需要 cache clean/invalidate 细节",
        ],
    },
}

# ── Token 预算估算（粗略） ──

def estimate_tokens(file_path: Path) -> int:
    """粗略估算文件 token 数（1 token ≈ 4 bytes）。"""
    if not file_path.is_file():
        return 0
    return file_path.stat().st_size // 4


def build_load_plan(workflow: str, platform: str, constraints: list[str] | None = None, budget: str = "compact") -> dict:
    """构建读取计划。

    Args:
        workflow: workflow ID
        platform: platform ID
        constraints: optional constraint IDs to narrow scope
        budget: "compact" (default), "standard", or "full"
    """
    wf = WORKFLOWS.get(workflow)
    if not wf:
        return {"error": f"Unknown workflow: {workflow}"}

    plat = PLATFORM_DOCS.get(platform)
    if not plat:
        return {"error": f"Unknown platform: {platform}"}

    required_files = []
    reasons = {}
    optional_files = []
    upgrade_hints = []
    quality_risks = []
    micro_constraints_loaded = []
    fallback_shards = []
    uncovered_constraints = []
    constraint_doc_mode = "full_shards"

    # ── Compact 模式（默认） ──
    if budget == "compact":
        # 1. quick index（替代完整 constraint_index）
        qi = "references/constraint_quick_index.md"
        required_files.append(qi)
        reasons[qi] = "C1-C45 快速查找索引"

        # 2. workflow 文件
        required_files.append(wf["file"])
        reasons[wf["file"]] = f"Workflow: {wf['description']}"

        # 3. core_rules_quick（替代完整 core_rules）
        core_quick = "references/core_rules_quick.md"
        required_files.append(core_quick)
        reasons[core_quick] = "核心规则速查"

        # 4. sdk_abstraction_quick（替代完整 yaml）
        sdk_quick = "references/sdk_abstraction_quick.md"
        required_files.append(sdk_quick)
        reasons[sdk_quick] = "SDK 抽象速查"

        # 5. 平台 quick（替代完整平台文档）
        plat_quick = f"platforms/{platform}_quick.md"
        if Path(ROOT / plat_quick).is_file():
            required_files.append(plat_quick)
            reasons[plat_quick] = f"平台速查: {platform}"
        else:
            # 没有 quick 文件时加载完整文档
            required_files.append(plat["doc"])
            reasons[plat["doc"]] = f"平台文档: {platform}（无 quick 版）"

        # 6. 约束微分片优先加载
        micro_constraints_loaded = []
        fallback_shards = []
        uncovered_constraints = []
        constraint_doc_mode = "shards"  # 默认模式

        if constraints:
            # 有明确 C 号时，优先加载微分片
            constraint_doc_mode = "micro"
            for c in constraints:
                c_upper = c.upper()
                micro_file = MICRO_SHARDS.get(c_upper)
                if micro_file and Path(ROOT / micro_file).is_file():
                    # 有微分片，加载它
                    if micro_file not in required_files:
                        required_files.append(micro_file)
                        reasons[micro_file] = f"微分片: {c_upper}"
                    micro_constraints_loaded.append(c_upper)
                else:
                    # 没有微分片，回退到完整 shard
                    shard = CONSTRAINT_TO_SHARD.get(c_upper)
                    if shard:
                        shard_file = CONSTRAINT_SHARDS.get(shard)
                        if shard_file and shard_file not in required_files:
                            required_files.append(shard_file)
                            reasons[shard_file] = f"约束分片: {shard}（回退）"
                        fallback_shards.append(shard)
                    else:
                        uncovered_constraints.append(c_upper)

            # 如果有回退，标记为混合模式
            if fallback_shards:
                constraint_doc_mode = "mixed"
        else:
            # 无明确 C 号时，按 workflow 加载完整 shard
            shards = set(wf["constraint_shards"])
            for shard_name in sorted(shards):
                shard_file = CONSTRAINT_SHARDS.get(shard_name)
                if shard_file and shard_file not in required_files:
                    required_files.append(shard_file)
                    reasons[shard_file] = f"约束分片: {shard_name}"

        # upgrade hints
        upgrade_hints = [
            "需要平台 API 细节时升级到 standard",
            "需要迁移/历史追溯时升级到 full",
        ]
        quality_risks = ["compact 模式可能遗漏平台特定细节"]

    # ── Standard 模式 ──
    elif budget == "standard":
        # 1. quick index
        qi = "references/constraint_quick_index.md"
        required_files.append(qi)
        reasons[qi] = "C1-C45 快速查找索引"

        # 2. workflow 文件
        required_files.append(wf["file"])
        reasons[wf["file"]] = f"Workflow: {wf['description']}"

        # 3. 完整 core_rules
        core = "references/core_rules.md"
        required_files.append(core)
        reasons[core] = "核心规则"

        # 4. 完整 SDK abstraction
        sdk_abs = "references/sdk_abstraction.yaml"
        required_files.append(sdk_abs)
        reasons[sdk_abs] = "SDK 抽象注册表"

        # 5. 完整平台文档 + SDK map
        required_files.append(plat["doc"])
        reasons[plat["doc"]] = f"平台文档: {platform}"
        required_files.append(plat["sdk_map"])
        reasons[plat["sdk_map"]] = f"SDK 映射: {platform}"

        # 6. 约束分片
        shards = set(wf["constraint_shards"])
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

        upgrade_hints = ["需要历史/迁移资料时升级到 full"]
        quality_risks = []

    # ── Full 模式 ──
    elif budget == "full":
        # 1. quick index
        qi = "references/constraint_quick_index.md"
        required_files.append(qi)
        reasons[qi] = "C1-C45 快速查找索引"

        # 2. workflow 文件
        required_files.append(wf["file"])
        reasons[wf["file"]] = f"Workflow: {wf['description']}"

        # 3. 完整 core_rules
        core = "references/core_rules.md"
        required_files.append(core)
        reasons[core] = "核心规则"

        # 4. 完整 SDK abstraction
        sdk_abs = "references/sdk_abstraction.yaml"
        required_files.append(sdk_abs)
        reasons[sdk_abs] = "SDK 抽象注册表"

        # 5. 完整平台文档 + SDK map
        required_files.append(plat["doc"])
        reasons[plat["doc"]] = f"平台文档: {platform}"
        required_files.append(plat["sdk_map"])
        reasons[plat["sdk_map"]] = f"SDK 映射: {platform}"

        # 6. 约束分片
        shards = set(wf["constraint_shards"])
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

        # 7. Full 模式额外加载
        extra_files = [
            ("references/skill_structure.md", "Skill 结构说明"),
            ("references/platform_diff_matrix.md", "平台差异矩阵"),
            ("references/constraint_graph.md", "约束知识图谱"),
        ]
        for f, r in extra_files:
            if f not in required_files and Path(ROOT / f).is_file():
                required_files.append(f)
                reasons[f] = r

        upgrade_hints = []
        quality_risks = []

    else:
        return {"error": f"Unknown budget: {budget}"}

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

    # 预算警告
    budget_warning = None
    if budget == "compact" and total_tokens > 15000:
        budget_warning = f"compact 模式预估 {total_tokens} tokens，超过 15k 建议升级到 standard"
    elif budget == "standard" and total_tokens > 30000:
        budget_warning = f"standard 模式预估 {total_tokens} tokens，超过 30k 建议升级到 full"

    return {
        "workflow": workflow,
        "workflow_description": wf["description"],
        "platform": platform,
        "platform_primary": plat["primary"],
        "budget_mode": budget,
        "required_files": files_with_reason,
        "forbidden_by_default": FORBIDDEN_BY_DEFAULT,
        "estimated_tokens": total_tokens,
        "budget_warning": budget_warning,
        "upgrade_hint": upgrade_hints,
        "quality_risk": quality_risks,
        "constraint_doc_mode": constraint_doc_mode,
        "micro_constraints_loaded": micro_constraints_loaded,
        "fallback_shards": fallback_shards,
        "uncovered_constraints": uncovered_constraints,
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

    # 测试所有 9 个 workflow × 3 个预算档位
    for wf_id in WORKFLOWS:
        for budget in ["compact", "standard", "full"]:
            plan = build_load_plan(wf_id, "esp32", budget=budget)
            check(f"{wf_id}+{budget}: no error", "error" not in plan)
            check(f"{wf_id}+{budget}: has required_files", len(plan.get("required_files", [])) > 0)
            check(f"{wf_id}+{budget}: has estimated_tokens", plan.get("estimated_tokens", 0) > 0)
            check(f"{wf_id}+{budget}: has budget_mode", plan.get("budget_mode") == budget)

    # 测试 platform 选择
    plan_esp32 = build_load_plan("code_review", "esp32")
    plan_zephyr = build_load_plan("code_review", "zephyr")
    check("esp32 platform doc", any("esp32" in f["path"] for f in plan_esp32["required_files"]))
    check("zephyr platform doc", any("zephyr" in f["path"] for f in plan_zephyr["required_files"]))

    # 测试 constraints 缩小范围
    plan_c3 = build_load_plan("code_review", "esp32", ["C3"])
    check("C3 adds micro-shard", any("micro_C03" in f["path"] for f in plan_c3["required_files"]))

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

    # 测试质量样例
    for case_id, case in QUALITY_CASES.items():
        plan = build_load_plan(case["workflow"], case["platform"], case.get("constraints", []), "compact")
        check(f"case {case_id}: no error", "error" not in plan)
        check(f"case {case_id}: has required_files", len(plan.get("required_files", [])) > 0)
        check(f"case {case_id}: budget_mode is compact", plan.get("budget_mode") == "compact")
        # 检查不包含 forbidden 文件
        for f in plan.get("required_files", []):
            if f["path"] in FORBIDDEN_BY_DEFAULT:
                check(f"case {case_id}: no forbidden file {f['path']}", False)
                break
        else:
            check(f"case {case_id}: no forbidden files", True)

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
    parser.add_argument("--budget", "-b",
                        choices=["compact", "standard", "full"],
                        default="compact",
                        help="预算档位：compact（默认）/ standard / full")
    parser.add_argument("--case",
                        choices=list(QUALITY_CASES.keys()),
                        help="质量样例 ID，自动解析为 workflow/platform/constraints")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 格式")
    parser.add_argument("--self-test", action="store_true",
                        help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    # --case 模式：自动解析为 workflow/platform/constraints
    if args.case:
        case = QUALITY_CASES[args.case]
        workflow = case["workflow"]
        platform = case["platform"]
        constraints = case.get("constraints", [])
        # 允许 --budget 覆盖
        budget = args.budget
    elif args.workflow:
        workflow = args.workflow
        platform = args.platform
        constraints = args.constraints
        budget = args.budget
    else:
        parser.error("--workflow or --case is required")

    plan = build_load_plan(workflow, platform, constraints, budget)

    # --case 模式：附加质量期望和升级触发
    if args.case and "error" not in plan:
        case = QUALITY_CASES[args.case]
        plan["case_id"] = args.case
        plan["case_title"] = case["title"]
        plan["quality_expectations"] = case["quality_expectations"]
        plan["upgrade_triggers"] = case["upgrade_triggers"]

    if args.json:
        json.dump(plan, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        if "error" in plan:
            print(f"Error: {plan['error']}", file=sys.stderr)
            return 1

        print(f"Context Router: {plan['workflow_description']} @ {plan['platform']}")
        print(f"Budget mode: {plan['budget_mode']}")
        print(f"Estimated tokens: ~{plan['estimated_tokens']}")
        if plan.get("budget_warning"):
            print(f"Warning: {plan['budget_warning']}")
        print(f"\nRequired files ({len(plan['required_files'])}):")
        for f in plan["required_files"]:
            print(f"  {f['path']} — {f['reason']} (~{f['estimated_tokens']} tokens)")
        print(f"\nForbidden by default:")
        for f in plan["forbidden_by_default"]:
            print(f"  {f}")
        print(f"\nConstraint shards: {', '.join(plan['constraint_shards_loaded'])}")
        if plan.get("upgrade_hint"):
            print(f"\nUpgrade hints:")
            for h in plan["upgrade_hint"]:
                print(f"  - {h}")
        if plan.get("quality_risk"):
            print(f"\nQuality risks:")
            for r in plan["quality_risk"]:
                print(f"  - {r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
