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

# ── 症状路由表 ──

SYMPTOM_ROUTES_PATH = ROOT / "references" / "log_symptom_routes.json"

# ── 平台推断关键词 ──

PLATFORM_KEYWORDS = {
    "esp32": ["esp32", "esp-idf", "idf", "esp_", "heap_caps", "esp_log", "gpio_config",
              "nvs_", "esp_ota", "esp_wifi", "esp_deep_sleep", "esp_task_wdt",
              "guru meditation", "esp_flash"],
    "zephyr": ["zephyr", "k_thread", "k_sem", "k_mutex", "k_msgq", "k_timer",
               "k_work", "k_msleep", "k_malloc", "k_free", "kernel oops",
               "zephyr_fatal", "devicetree", "prj.conf", "mcuboot", "west build"],
    "stm32": ["stm32", "hal_", "cubemx", "cmsis", "stm32xx"],
    "jl": ["jl", "ac79", "jieli", "thread_fork", "os_sem_pend", "os_q_create"],
    "bk": ["bk", "beken", "bk7258", "rtos_create_thread", "rtos_push_to_queue",
           "BEKEN_WAIT_FOREVER", "bk_ota"],
}


def infer_platform(text: str) -> tuple[str, float, list[str]]:
    """从文本推断平台。

    Args:
        text: 用户问题描述或日志内容

    Returns:
        (platform, confidence, matched_terms)
    """
    text_lower = text.lower()
    scores = {}
    matched_terms = {}

    for plat, keywords in PLATFORM_KEYWORDS.items():
        score = 0
        terms = []
        for kw in keywords:
            if kw.lower() in text_lower:
                score += 1
                terms.append(kw)
        if score > 0:
            scores[plat] = score
            matched_terms[plat] = terms

    if not scores:
        return "esp32", 0.0, []  # 默认

    best_plat = max(scores, key=scores.get)
    best_score = scores[best_plat]

    # 置信度计算
    if best_score >= 3:
        confidence = 0.9
    elif best_score >= 2:
        confidence = 0.7
    else:
        confidence = 0.5

    return best_plat, confidence, matched_terms.get(best_plat, [])


def match_symptoms(text: str) -> list[dict]:
    """匹配自然语言文本到症状路由。

    Args:
        text: 用户问题描述或日志内容

    Returns:
        匹配的症状列表，按置信度排序
    """
    if not SYMPTOM_ROUTES_PATH.is_file():
        return []

    try:
        data = json.loads(SYMPTOM_ROUTES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    text_lower = text.lower()
    matches = []

    for symptom in data.get("symptoms", []):
        score = 0
        matched_patterns = []
        match_type = "none"  # none / weak / medium / strong

        # 匹配技术模式（正则）
        for pattern in symptom.get("patterns", []):
            try:
                import re
                if re.search(pattern, text, re.IGNORECASE):
                    score += 2
                    matched_patterns.append(pattern)
                    match_type = "medium"
            except re.error:
                pass

        # 匹配自然语言模式
        for np in symptom.get("natural_patterns", []):
            if np.lower() in text_lower:
                score += 3  # 自然语言匹配权重更高
                matched_patterns.append(np)
                match_type = "strong"

        # 弱信号词匹配（如"崩溃""卡死""异常"）
        for wp in symptom.get("weak_patterns", []):
            if wp.lower() in text_lower:
                score += 1
                matched_patterns.append(wp)
                if match_type == "none":
                    match_type = "weak"

        if score > 0:
            # 限制候选根因数量
            root_causes = symptom.get("root_cause_hints", [])[:3]

            matches.append({
                "id": symptom["id"],
                "name": symptom.get("name", ""),
                "score": score,
                "match_type": match_type,
                "matched_patterns": matched_patterns,
                "constraints": symptom.get("constraints", []),
                "root_cause_hints": root_causes,
                "verify_steps": symptom.get("verify_steps", []),
                "missing_facts": symptom.get("missing_facts", []),
                "hardware_challenge": symptom.get("hardware_challenge", []),
                "do_not_patch_until": symptom.get("do_not_patch_until"),
                "diagnostic_probes": symptom.get("diagnostic_probes", {}),
                "log_signals": symptom.get("log_signals", []),
                "checker_targets": symptom.get("checker_targets", []),
                "stop_conditions": symptom.get("stop_conditions", []),
            })

    # 按分数排序
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches


def build_symptom_plan(text: str, platform: str, budget: str = "compact",
                       probe_detail: str = "compact", allow_weak_route: bool = False) -> dict:
    """根据症状文本构建读取计划。

    Args:
        text: 用户问题描述
        platform: 目标平台（如果为空则自动推断）
        budget: 预算档位
        probe_detail: 探针详细程度（compact/full）
        allow_weak_route: 弱匹配时是否强制继续路由

    Returns:
        包含症状匹配和读取计划的字典
    """
    matches = match_symptoms(text)

    # 平台推断
    inferred_platform, platform_confidence, matched_platform_terms = infer_platform(text)

    # 如果用户未显式指定平台，使用推断结果
    if platform == "esp32" and inferred_platform != "esp32" and platform_confidence > 0.5:
        platform = inferred_platform
        platform_source = "inferred"
    else:
        platform_source = "explicit"

    if not matches:
        return {
            "symptom_text": text,
            "routing_decision": "ask_more",
            "matched_symptoms": [],
            "likely_constraints": [],
            "top_hypotheses": [],
            "verify_steps": [],
            "missing_facts": ["无法识别症状，请提供更具体的描述或日志"],
            "diagnostic_probes": {},
            "checker_targets": [],
            "log_signals": [],
            "stop_conditions": [],
            "error": "No matching symptoms found",
        }

    # 取 top 3 症状
    top_matches = matches[:3]

    # 置信度判断
    overall_confidence = top_matches[0].get("match_type", "medium")

    # 弱匹配策略
    if overall_confidence == "weak" and not allow_weak_route:
        # 弱匹配：只返回 missing_facts，不加载大上下文
        missing_facts = []
        for m in top_matches:
            for fact in m.get("missing_facts", []):
                if fact not in missing_facts:
                    missing_facts.append(fact)

        return {
            "symptom_text": text,
            "routing_decision": "ask_more",
            "inferred_platform": inferred_platform,
            "platform_source": platform_source,
            "platform_confidence": platform_confidence,
            "matched_platform_terms": matched_platform_terms,
            "match_confidence": "weak",
            "matched_symptoms": [{
                "id": m["id"],
                "name": m["name"],
                "score": m["score"],
                "match_type": m.get("match_type", "weak"),
                "matched": m["matched_patterns"],
            } for m in top_matches],
            "likely_constraints": [],
            "top_hypotheses": [],
            "verify_steps": [],
            "missing_facts": ["信息不足，无法确定根因"] + missing_facts[:2],
            "diagnostic_probes": {},
            "checker_targets": [],
            "log_signals": [],
            "stop_conditions": [],
        }

    # 收集所有相关约束
    all_constraints = []
    for m in top_matches:
        for c in m["constraints"]:
            if c not in all_constraints:
                all_constraints.append(c)

    # 收集候选根因
    top_hypotheses = []
    for m in top_matches:
        for hint in m["root_cause_hints"][:2]:  # 每个症状取 top 2
            if hint not in top_hypotheses:
                top_hypotheses.append(hint)
    top_hypotheses = top_hypotheses[:5]  # 最多 5 个

    # 收集验证步骤
    verify_steps = []
    for m in top_matches:
        for step in m.get("verify_steps", []):
            if step not in verify_steps:
                verify_steps.append(step)

    # 收集缺失事实
    missing_facts = []
    for m in top_matches:
        for fact in m.get("missing_facts", []):
            if fact not in missing_facts:
                missing_facts.append(fact)
    missing_facts = missing_facts[:3]  # 最多 3 个

    # 收集诊断探针
    diagnostic_probes = {}
    for m in top_matches:
        probes = m.get("diagnostic_probes", {})
        for key, values in probes.items():
            if key not in diagnostic_probes:
                diagnostic_probes[key] = []
            for v in values:
                if v not in diagnostic_probes[key]:
                    diagnostic_probes[key].append(v)

    # compact 模式：每个探针类别最多 2 条
    if probe_detail == "compact":
        for key in diagnostic_probes:
            diagnostic_probes[key] = diagnostic_probes[key][:2]

    # 收集 checker targets
    checker_targets = []
    for m in top_matches:
        for ct in m.get("checker_targets", []):
            if ct not in checker_targets:
                checker_targets.append(ct)

    # 收集 log signals
    log_signals = []
    for m in top_matches:
        for ls in m.get("log_signals", []):
            if ls not in log_signals:
                log_signals.append(ls)

    # 收集 stop conditions
    stop_conditions = []
    for m in top_matches:
        for sc in m.get("stop_conditions", []):
            if sc not in stop_conditions:
                stop_conditions.append(sc)

    # 推断 workflow
    workflow = _infer_workflow(top_matches[0]["id"])

    # routing_decision
    routing_decision = "diagnose" if overall_confidence in ("strong", "medium") else "ask_more"

    # 构建读取计划
    plan = build_load_plan(workflow, platform, all_constraints, budget)

    # 附加症状信息
    plan["symptom_text"] = text
    plan["routing_decision"] = routing_decision
    plan["matched_symptoms"] = [{
        "id": m["id"],
        "name": m["name"],
        "score": m["score"],
        "match_type": m.get("match_type", "medium"),
        "matched": m["matched_patterns"],
    } for m in top_matches]
    plan["likely_constraints"] = all_constraints
    plan["top_hypotheses"] = top_hypotheses
    plan["verify_steps"] = verify_steps
    plan["missing_facts"] = missing_facts

    # 平台推断信息
    plan["inferred_platform"] = inferred_platform
    plan["platform_source"] = platform_source
    plan["platform_confidence"] = platform_confidence
    plan["matched_platform_terms"] = matched_platform_terms

    # 置信度
    plan["match_confidence"] = overall_confidence

    # 诊断探针
    plan["diagnostic_probes"] = diagnostic_probes
    plan["checker_targets"] = checker_targets
    plan["log_signals"] = log_signals
    plan["stop_conditions"] = stop_conditions

    # 硬件质疑
    hw_challenges = []
    for m in top_matches:
        for hc in m.get("hardware_challenge", []):
            if hc not in hw_challenges:
                hw_challenges.append(hc)
    if hw_challenges:
        plan["hardware_challenges"] = hw_challenges[:5]

    # 禁止盲修提示
    dnp = []
    for m in top_matches:
        if m.get("do_not_patch_until"):
            dnp.append(m["do_not_patch_until"])
    if dnp:
        plan["do_not_patch_until"] = dnp

    return plan


def _infer_workflow(symptom_id: str) -> str:
    """根据症状 ID 推断最可能的 workflow。"""
    mapping = {
        "WDT_RESET": "crash_debug",
        "HARDFAULT": "crash_debug",
        "STACK_OVERFLOW": "crash_debug",
        "HEAP_EXHAUSTION": "memory_analysis",
        "QUEUE_FULL": "code_review",
        "OTA_ROLLBACK": "code_review",
        "DMA_CACHE_ERROR": "code_review",
        "AUDIO_UNDERRUN": "code_review",
        "LVGL_CRASH": "crash_debug",
        "ZEPHYR_KERNEL_OOPS": "crash_debug",
        "SENSOR_TIMEOUT": "code_review",
        "BROWNOUT_RESET": "crash_debug",
        "PERIPHERAL_NO_ACK": "crash_debug",
        "LIFECYCLE_CHAOS": "code_review",
        "HOT_PATH_BLOCKED": "code_review",
    }
    return mapping.get(symptom_id, "code_review")


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
    parser.add_argument("--symptom-text",
                        help="自然语言问题描述，自动匹配症状和约束")
    parser.add_argument("--symptom-file",
                        help="日志或笔记文件，自动匹配症状和约束")
    parser.add_argument("--probe-detail",
                        choices=["compact", "full"],
                        default="compact",
                        help="探针详细程度：compact（默认）/ full")
    parser.add_argument("--allow-weak-route",
                        action="store_true",
                        help="低置信时强制继续路由（默认只返回 missing_facts）")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 格式")
    parser.add_argument("--self-test", action="store_true",
                        help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    # --symptom-text / --symptom-file 模式
    if args.symptom_text or args.symptom_file:
        symptom_text = args.symptom_text
        if args.symptom_file:
            sf = Path(args.symptom_file)
            if not sf.is_file():
                parser.error(f"Symptom file not found: {sf}")
            symptom_text = sf.read_text(encoding="utf-8", errors="ignore")
        if not symptom_text:
            parser.error("No symptom text provided")

        plan = build_symptom_plan(symptom_text, args.platform, args.budget,
                                   args.probe_detail, args.allow_weak_route)

        if args.json:
            json.dump(plan, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            if "error" in plan:
                print(f"Error: {plan['error']}", file=sys.stderr)
                return 1
            print(f"Symptom: {plan['symptom_text'][:80]}...")
            print(f"Routing decision: {plan.get('routing_decision', 'unknown')}")
            print(f"Match confidence: {plan.get('match_confidence', 'unknown')}")
            print(f"Matched: {', '.join(m['name'] for m in plan.get('matched_symptoms', []))}")
            print(f"Platform: {plan.get('inferred_platform', 'unknown')} ({plan.get('platform_source', 'unknown')})")
            print(f"Likely constraints: {', '.join(plan.get('likely_constraints', []))}")
            if plan.get('top_hypotheses'):
                print(f"Top hypotheses: {', '.join(plan.get('top_hypotheses', []))}")
            if plan.get('diagnostic_probes'):
                print(f"\nDiagnostic probes:")
                for key, values in plan.get('diagnostic_probes', {}).items():
                    print(f"  {key}: {', '.join(values[:3])}")
            if plan.get('checker_targets'):
                print(f"Checker targets: {', '.join(plan.get('checker_targets', []))}")
            if plan.get('log_signals'):
                print(f"Log signals: {', '.join(plan.get('log_signals', []))}")
            if plan.get('stop_conditions'):
                print(f"Stop conditions: {', '.join(plan.get('stop_conditions', []))}")
            if plan.get('missing_facts'):
                print(f"Missing facts: {', '.join(plan.get('missing_facts', []))}")
            print(f"\nBudget: {plan.get('budget_mode')} | Tokens: ~{plan.get('estimated_tokens')}")
        return 0

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
        parser.error("--workflow, --case, or --symptom-text is required")

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
