#!/usr/bin/env python3
"""
Context Router — 上下文路由器。

根据 workflow、platform、constraints 输出最小读取计划，帮助 agent
确定性知道：该读哪些文件、别读哪些文件、默认最多读多少。

用法:
    python tools/context_router.py --workflow code_review --platform esp32 --json
    python tools/context_router.py --workflow crash_debug --platform esp32 --rtos freertos --constraints C2 C3 --json
    python tools/context_router.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 路由配置 ──

CROSS_DOMAIN_AMBIGUITY_THRESHOLD = 0.5  # Tuned on 60-sample dev set; see tests/fixtures/routing_sampling.json

# ── 请求分类关键词表（与 SKILL.md 路由表对齐）──

ROUTE_KEYWORDS: dict[str, dict] = {
    "crash_debug": {
        "domain": "debug",
        "priority": 1,
        "exclude": [],
        "keywords": ["crash", "HardFault", "WDT", "deadlock", "frozen", "死机",
                      "看门狗", "崩溃", "backtrace", "Guru Meditation", "watchdog",
                      "stack overflow crash", "exception", "卡在", "卡死", "重启"],
    },
    "code_review": {
        "domain": "review",
        "priority": 2,
        "exclude": ["crash", "死机", "卡死", "卡在", "重启"],
        "keywords": ["review", "audit", "审查", "check", "ISR", "DMA", "cJSON", "代码质量",
                      "code quality", "static analysis", "lint", "OTA", "安全", "看看代码",
                      "代码规范", "code review"],
    },
    "memory_analysis": {
        "domain": "review",
        "priority": 2,
        "exclude": ["crash", "死机", "卡死"],
        "keywords": ["memory", "leak", "内存", "堆栈", "heap", "stack overflow",
                      "memory analysis", "pool", "fragmentation", "堆栈溢出", "内存泄漏"],
    },
    "project_review": {
        "domain": "review",
        "priority": 2,
        "exclude": ["crash", "死机"],
        "keywords": ["project review", "项目审查", "workspace review", "全项目", "整个项目",
                      "整个工程", "project audit", "项目检查"],
    },
    "hw_sw_debug": {
        "domain": "review",
        "priority": 2,
        "exclude": [],
        "keywords": ["co-debug", "GPIO conflict", "硬件协同", "GPIO", "IO conflict",
                      "peripheral conflict", "pin mux", "引脚冲突", "pin conflict"],
    },
    "lvgl_page": {
        "domain": "generate",
        "priority": 3,
        "exclude": ["crash", "死机", "卡死", "frozen", "卡在"],
        "keywords": ["LVGL", "UI", "page", "页面", "设计截图", "design",
                      "界面", "GUI", "widget"],
    },
    "app_manifest": {
        "domain": "generate",
        "priority": 3,
        "exclude": [],
        "keywords": ["manifest", "多页", "multi-page", "Router", "Presenter",
                      "Model", "脚手架", "scaffold", "app architecture", "应用架构",
                      "多页面"],
    },
    "new_module": {
        "domain": "generate",
        "priority": 3,
        "exclude": ["crash", "review", "审查", "leak", "内存"],
        "keywords": ["new module", "新模块", "task", "任务", "multitask",
                      "module design", "模块设计", "module", "模块"],
    },
    "bring_up": {
        "domain": "generate",
        "priority": 3,
        "exclude": [],
        "keywords": ["bring-up", "板级", "最小系统", "peripheral validation",
                      "board init", "boot", "startup", "外设", "新板", "first boot",
                      "上电", "串口没输出", "启动流程"],
    },
    "sdk_trim": {
        "domain": "generate",
        "priority": 3,
        "exclude": [],
        "keywords": ["SDK trim", "裁剪", "裁", "driver prune", "sdk_trim",
                      "component pruning", "减小体积", "trim", "prune", "flash不够",
                      "精简", "缩减"],
    },
}


def classify_request(text: str, cross_domain_threshold: float | None = None) -> dict:
    """Classify a natural language request into domain + workflow.

    Args:
        text: the user's first message or request description
        cross_domain_threshold: override for cross-domain ambiguity threshold
            (default: CROSS_DOMAIN_AMBIGUITY_THRESHOLD)

    Returns:
        dict with keys:
          - domain: "review" | "generate" | "debug"
          - workflow: workflow ID from WORKFLOWS
          - routing_reason: short explanation of why this workflow was chosen
          OR
          - clarification_required: True + clarification_reason if ambiguous
    """
    if cross_domain_threshold is None:
        cross_domain_threshold = CROSS_DOMAIN_AMBIGUITY_THRESHOLD
    text_lower = text.lower()
    scores: dict[str, int] = {}
    matched_kw: dict[str, list[str]] = {}

    def _kw_match(kw: str, text: str) -> tuple[bool, int]:
        """Match keyword against text. Returns (matched, weight).

        Multi-word keywords and non-ASCII keywords get weight 3 (phrase match).
        ASCII single words get weight 1.
        """
        kw_lower = kw.lower()
        is_phrase = " " in kw_lower or not kw_lower.isascii()
        if len(kw_lower) <= 3 and kw_lower.isascii():
            if re.search(r'\b' + re.escape(kw_lower) + r'\b', text):
                return True, 1
            return False, 0
        if kw_lower in text:
            return True, 3 if is_phrase else 1
        return False, 0

    for wf_id, spec in ROUTE_KEYWORDS.items():
        score = 0
        terms = []
        # Check exclude: if user text matches any exclude keyword, skip this route
        excluded = False
        for ex in spec.get("exclude", []):
            if ex.lower() in text_lower:
                excluded = True
                break
        if excluded:
            continue

        for kw in spec["keywords"]:
            hit, weight = _kw_match(kw, text_lower)
            if hit:
                score += weight
                terms.append(kw)
        if score > 0:
            # Apply priority multiplier: priority 1 gets 3x, priority 2 gets 2x, priority 3 gets 1x
            priority = spec.get("priority", 3)
            score *= (4 - priority)
            scores[wf_id] = score
            matched_kw[wf_id] = terms

    if not scores:
        return {
            "clarification_required": True,
            "clarification_reason": "No keyword matched. Ask user to clarify: review, generate, or debug?",
        }

    best_wf = max(scores, key=scores.get)
    best_score = scores[best_wf]

    # Check for ties (ambiguous)
    tied = [wf for wf, s in scores.items() if s == best_score]
    if len(tied) > 1:
        # If tied workflows share the same domain, pick the more specific one
        domains = {wf: ROUTE_KEYWORDS[wf]["domain"] for wf in tied}
        unique_domains = set(domains.values())
        if len(unique_domains) > 1:
            return {
                "clarification_required": True,
                "clarification_reason": (
                    f"Ambiguous: matched {', '.join(tied)} with equal score {best_score}. "
                    f"Ask user which is the primary deliverable."
                ),
            }

    # Check for cross-domain ambiguity: if multiple domains matched and
    # the best score isn't dominant, clarify
    matched_domains = {ROUTE_KEYWORDS[wf]["domain"] for wf in scores}
    if len(matched_domains) > 1:
        # Find the highest-scoring competitor from a different domain
        cross_competitors = [
            (wf, s) for wf, s in scores.items()
            if ROUTE_KEYWORDS[wf]["domain"] != ROUTE_KEYWORDS[best_wf]["domain"]
        ]
        if cross_competitors:
            top_competitor_score = max(s for _, s in cross_competitors)
            # Only clarify if competitor score exceeds threshold of best score
            if top_competitor_score >= best_score * cross_domain_threshold:
                competitors = [
                    f"{wf}({ROUTE_KEYWORDS[wf]['domain']},score={s})"
                    for wf, s in cross_competitors if s == top_competitor_score
                ]
                return {
                    "clarification_required": True,
                    "clarification_reason": (
                        f"Cross-domain ambiguity: {best_wf}({ROUTE_KEYWORDS[best_wf]['domain']},"
                        f"score={best_score}) vs {', '.join(competitors)}. "
                        f"Ask user which is the primary deliverable."
                    ),
                }

    return {
        "domain": ROUTE_KEYWORDS[best_wf]["domain"],
        "workflow": best_wf,
        "routing_reason": f"Matched keywords: {', '.join(matched_kw[best_wf])}",
    }


# ── 症状路由表 ──

from symptom_routes import load_symptom_routes

# ── 平台推断关键词 ──

PLATFORM_KEYWORDS = {
    "esp32": ["esp32", "esp-idf", "idf", "esp_", "heap_caps", "esp_log", "gpio_config",
              "nvs_", "esp_ota", "esp_wifi", "esp_deep_sleep", "esp_task_wdt",
              "guru meditation", "esp_flash"],
    "stm32": ["stm32", "hal_", "cubemx", "cmsis", "stm32xx"],
    "jl": ["jl", "ac79", "jieli", "thread_fork", "os_sem_pend", "os_q_create"],
    "bk": ["bk", "beken", "bk7258", "rtos_create_thread", "rtos_push_to_queue",
           "BEKEN_WAIT_FOREVER", "bk_ota"],
}

RTOS_KEYWORDS = {
    "freertos": ["freertos", "freertosv", "freertos_", "vTaskDelay", "xTaskCreate", "xTaskGetCurrentTaskHandle",
                "xQueue", "xSemaphore", "configASSERT", "portMUX_TYPE", "xEventGroup", "heap_caps", "xTaskDelayUntil"],
    "zephyr": ["zephyr", "k_thread", "k_sem", "k_mutex", "k_msgq", "k_timer",
               "k_work", "k_msleep", "k_malloc", "k_free", "kernel oops",
               "zephyr_fatal", "devicetree", "prj.conf", "mcuboot", "west build"],
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


def infer_rtos(text: str) -> tuple[str, float, list[str]]:
    """Infer RTOS from text."""
    text_lower = text.lower()
    scores = {}
    matched_terms = {}

    for rtos_name, keywords in RTOS_KEYWORDS.items():
        score = 0
        terms = []
        for kw in keywords:
            if kw.lower() in text_lower:
                score += 1
                terms.append(kw)
        if score > 0:
            scores[rtos_name] = score
            matched_terms[rtos_name] = terms

    if not scores:
        return "freertos", 0.0, []

    best_rtos = max(scores, key=scores.get)
    best_score = scores[best_rtos]

    if best_score >= 3:
        confidence = 0.9
    elif best_score >= 2:
        confidence = 0.7
    else:
        confidence = 0.5

    return best_rtos, confidence, matched_terms.get(best_rtos, [])


def match_symptoms(text: str) -> list[dict]:
    """匹配自然语言文本到症状路由。

    Args:
        text: 用户问题描述或日志内容

    Returns:
        匹配的症状列表，按置信度排序
    """
    text_lower = text.lower()
    matches = []

    for symptom in load_symptom_routes():
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


def build_symptom_plan(text: str, platform: str, rtos: str, budget: str = "compact",
                       probe_detail: str = "compact", allow_weak_route: bool = False) -> dict:
    """Build a symptom-driven load plan with platform and RTOS inference."""
    matches = match_symptoms(text)

    inferred_platform, platform_confidence, matched_platform_terms = infer_platform(text)
    inferred_rtos, rtos_confidence, matched_rtos_terms = infer_rtos(text)

    if platform == "esp32" and inferred_platform != "esp32" and platform_confidence > 0.5:
        platform = inferred_platform
        platform_source = "inferred"
    else:
        platform_source = "explicit"

    if rtos == "freertos" and inferred_rtos != "freertos" and rtos_confidence > 0.5:
        rtos = inferred_rtos
        rtos_source = "inferred"
    else:
        rtos_source = "explicit"

    if not matches:
        return {
            "symptom_text": text,
            "routing_decision": "ask_more",
            "matched_symptoms": [],
            "likely_constraints": [],
            "top_hypotheses": [],
            "verify_steps": [],
            "missing_facts": ["Need concrete symptom text, logs, or failing command output"],
            "diagnostic_probes": {},
            "checker_targets": [],
            "log_signals": [],
            "stop_conditions": [],
            "error": "No matching symptoms found",
            "inferred_platform": inferred_platform,
            "platform_source": platform_source,
            "platform_confidence": platform_confidence,
            "matched_platform_terms": matched_platform_terms,
            "inferred_rtos": inferred_rtos,
            "rtos_source": rtos_source,
            "rtos_confidence": rtos_confidence,
            "matched_rtos_terms": matched_rtos_terms,
        }

    top_matches = matches[:3]
    overall_confidence = top_matches[0].get("match_type", "medium")

    if overall_confidence == "weak" and not allow_weak_route:
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
            "inferred_rtos": inferred_rtos,
            "rtos_source": rtos_source,
            "rtos_confidence": rtos_confidence,
            "matched_rtos_terms": matched_rtos_terms,
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
            "missing_facts": ["Weak symptom match; need more evidence"] + missing_facts[:2],
            "diagnostic_probes": {},
            "checker_targets": [],
            "log_signals": [],
            "stop_conditions": [],
        }

    all_constraints = []
    for m in top_matches:
        for c in m["constraints"]:
            if c not in all_constraints:
                all_constraints.append(c)

    top_hypotheses = []
    for m in top_matches:
        for hint in m["root_cause_hints"][:2]:
            if hint not in top_hypotheses:
                top_hypotheses.append(hint)
    top_hypotheses = top_hypotheses[:5]

    verify_steps = []
    for m in top_matches:
        for step in m.get("verify_steps", []):
            if step not in verify_steps:
                verify_steps.append(step)

    missing_facts = []
    for m in top_matches:
        for fact in m.get("missing_facts", []):
            if fact not in missing_facts:
                missing_facts.append(fact)
    missing_facts = missing_facts[:3]

    diagnostic_probes = {}
    for m in top_matches:
        probes = m.get("diagnostic_probes", {})
        for key, values in probes.items():
            if key not in diagnostic_probes:
                diagnostic_probes[key] = []
            for v in values:
                if v not in diagnostic_probes[key]:
                    diagnostic_probes[key].append(v)

    if probe_detail == "compact":
        for key in diagnostic_probes:
            diagnostic_probes[key] = diagnostic_probes[key][:2]

    checker_targets = []
    for m in top_matches:
        for ct in m.get("checker_targets", []):
            if ct not in checker_targets:
                checker_targets.append(ct)

    log_signals = []
    for m in top_matches:
        for ls in m.get("log_signals", []):
            if ls not in log_signals:
                log_signals.append(ls)

    stop_conditions = []
    for m in top_matches:
        for sc in m.get("stop_conditions", []):
            if sc not in stop_conditions:
                stop_conditions.append(sc)

    workflow = _infer_workflow(top_matches[0]["id"], tuple(match["id"] for match in top_matches))
    routing_decision = "diagnose" if overall_confidence in ("strong", "medium") else "ask_more"

    plan = build_load_plan(workflow, platform, rtos, all_constraints, budget)

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

    plan["inferred_platform"] = inferred_platform
    plan["platform_source"] = platform_source
    plan["platform_confidence"] = platform_confidence
    plan["matched_platform_terms"] = matched_platform_terms
    plan["inferred_rtos"] = inferred_rtos
    plan["rtos_source"] = rtos_source
    plan["rtos_confidence"] = rtos_confidence
    plan["matched_rtos_terms"] = matched_rtos_terms

    plan["match_confidence"] = overall_confidence
    plan["diagnostic_probes"] = diagnostic_probes
    plan["checker_targets"] = checker_targets
    plan["log_signals"] = log_signals
    plan["stop_conditions"] = stop_conditions

    hw_challenges = []
    for m in top_matches:
        for hc in m.get("hardware_challenge", []):
            if hc not in hw_challenges:
                hw_challenges.append(hc)
    if hw_challenges:
        plan["hardware_challenges"] = hw_challenges[:5]

    dnp = []
    for m in top_matches:
        if m.get("do_not_patch_until"):
            dnp.append(m["do_not_patch_until"])
    if dnp:
        plan["do_not_patch_until"] = dnp

    return plan


def _infer_workflow(symptom_id: str, related_ids: tuple[str, ...] = ()) -> str:
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
        "UNCLEAR_TOPOLOGY": "code_review",
    }
    # A crash-class symptom must take precedence even when a queue-full line
    # scored higher.  Queue pressure can be the cause, but the first workflow
    # must preserve crash evidence before ordinary review work starts.
    if {"WDT_RESET", "HARDFAULT", "STACK_OVERFLOW"}.intersection(related_ids):
        return "crash_debug"
    return mapping.get(symptom_id, "code_review")


# ── Workflow 定义 ──

WORKFLOWS = {
    "code_review": {
        "file": "workflows/l2_code_review.md",
        "constraint_shards": ["review", "memory"],
        "prompts": ["prompts/lvgl_thread_safety.txt", "prompts/memory_ownership.txt", "prompts/cjson_safe_parse.txt"],
        "description": "代码审查",
    },
    "project_review": {
        "file": "workflows/l2_project_review.md",
        "constraint_shards": ["review", "platform"],
        "prompts": ["prompts/module_contract_topology.txt", "prompts/timeout_lifecycle_observability.txt",
                     "prompts/hotpath_critical_budget.txt", "prompts/backpressure_recovery_config.txt",
                     "prompts/runtime_efficiency_contracts.txt"],
        "description": "项目审查",
    },
    "crash_debug": {
        "file": "workflows/debug_crash.md",
        "constraint_shards": ["review", "rtos", "platform"],
        "prompts": ["prompts/crash_log_decode.txt"],
        "description": "崩溃调试",
    },
    "memory_analysis": {
        "file": "workflows/l2_memory_analysis.md",
        "constraint_shards": ["memory", "rtos"],
        "prompts": ["prompts/memory_ownership.txt", "prompts/memory_alloc_optimize.txt"],
        "description": "内存分析",
    },
    "sdk_trim": {
        "file": "workflows/l3_sdk_trim.md",
        "constraint_shards": ["platform"],
        "prompts": ["prompts/sdk_trim_prune.txt"],
        "description": "SDK 裁剪",
    },
    "new_module": {
        "file": "workflows/l3_new_module.md",
        "constraint_shards": ["rtos", "review"],
        "prompts": ["prompts/module_contract_topology.txt", "prompts/timeout_lifecycle_observability.txt",
                     "prompts/hotpath_critical_budget.txt", "prompts/backpressure_recovery_config.txt",
                     "prompts/runtime_efficiency_contracts.txt"],
        "description": "新模块",
    },
    "bring_up": {
        "file": "workflows/l3_bring_up.md",
        "constraint_shards": ["platform", "rtos"],
        "prompts": ["prompts/boot_wdt_lifecycle.txt"],
        "description": "板级 Bring-up",
    },
    "lvgl_page": {
        "file": "workflows/l3_lvgl_page.md",
        "quick_file": "workflows/l3_lvgl_page_quick.md",
        "quick_refs": [],
        "quick_constraint_mode": "embedded",
        "quick_platform_optional": True,
        "constraint_shards": ["review", "media", "voice"],
        "prompts": ["prompts/lvgl_thread_safety.txt"],
        "description": "LVGL 页面生成",
    },
    "hw_sw_debug": {
        "file": "workflows/hw_sw_cocodebug.md",
        "constraint_shards": ["platform", "review"],
        "prompts": [],
        "description": "软硬联调",
    },
    "app_manifest": {
        "file": "workflows/l3_lvgl_page.md",
        "quick_file": "workflows/l3_lvgl_page_quick.md",
        "quick_refs": [],
        "quick_constraint_mode": "embedded",
        "quick_platform_optional": True,
        "constraint_shards": ["review"],
        "prompts": ["prompts/lvgl_thread_safety.txt"],
        "description": "多页应用脚手架（manifest 子路径）",
    },
}

# ── 约束分片映射 ──

CONSTRAINT_SHARDS = {
    "review": "references/constraint_review.md",
    "memory": "references/constraint_memory.md",
    "rtos": "references/constraint_rtos.md",
    "platform": "references/constraint_platform.md",
    "media": "references/constraint_media.md",
    "voice": "references/constraint_voice.md",
    "ota": "references/constraint_ota.md",
    "recover": "references/constraint_recover.md",
    "bluetooth": "references/constraint_bluetooth_protocol.md",
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
    "C23": "platform", "C42": "platform", "C45": "platform", "C46": "bluetooth",
    "C25": "media", "C26": "media", "C27": "media",
    "C9": "ota", "C22": "ota", "C24": "ota",
    "C37": "recover", "C38": "recover", "C39": "recover",
    "C40": "recover", "C41": "recover",
    "C10": "voice", "C11": "review", "C12": "review", "C13": "review",
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

RTOS_DOCS = {
    "freertos": {
        "primary": True,
        "doc": "platforms/freertos.md",
        "sdk_map": "platforms/freertos_sdk_map.yaml",
        "quick_doc": "platforms/freertos_quick.md",
    },
    "zephyr": {
        "primary": True,
        "doc": "platforms/zephyr.md",
        "sdk_map": "platforms/zephyr_sdk_map.yaml",
        "quick_doc": "platforms/zephyr_quick.md",
    },
}

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
        "rtos": "freertos",
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
        "platform": "esp32",
        "rtos": "zephyr",
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
        "rtos": "freertos",
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
        "rtos": "freertos",
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
        "rtos": "freertos",
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


def build_load_plan(workflow: str, platform: str, rtos: str, constraints: list[str] | None = None,
                   budget: str = "compact") -> dict:
    """Build load plan.

    Args:
        workflow: workflow ID
        platform: hardware platform ID
        rtos: RTOS ID
        constraints: optional constraint IDs to narrow scope
        budget: "compact" (default), "standard", or "full"
    """
    wf = WORKFLOWS.get(workflow)
    if not wf:
        return {"error": f"Unknown workflow: {workflow}"}

    plat = PLATFORM_DOCS.get(platform)
    if not plat:
        return {"error": f"Unknown platform: {platform}"}

    rtos_entry = RTOS_DOCS.get(rtos)
    if not rtos_entry:
        return {"error": f"Unknown rtos: {rtos}"}

    constraints = constraints or []

    required_files: list[str] = []
    reasons: dict[str, str] = {}
    upgrade_hints: list[str] = []
    quality_risks: list[str] = []
    micro_constraints_loaded: list[str] = []
    fallback_shards: list[str] = []
    uncovered_constraints: list[str] = []
    constraint_shards_loaded: list[str] = []
    constraint_doc_mode = "shards"

    def add_required(path: str, reason: str, required_exists: bool = True) -> None:
        if not path or path in required_files:
            return
        if required_exists and not (ROOT / path).is_file():
            return
        required_files.append(path)
        reasons[path] = reason

    def add_constraint_shards(shards: set[str]) -> None:
        nonlocal constraint_shards_loaded
        for shard_name in sorted(shards):
            shard_file = CONSTRAINT_SHARDS.get(shard_name)
            if shard_file and shard_file not in required_files:
                required_files.append(shard_file)
                reasons[shard_file] = f"Constraint shard: {shard_name}"
        constraint_shards_loaded = sorted(shards)

    if budget == "compact":
        qi = "references/constraint_quick_index.md"
        add_required(qi, "C1-C46 quick constraint index")

        workflow_file = wf.get("quick_file", wf["file"])
        workflow_reason = "Workflow quick reference" if workflow_file != wf["file"] else "Workflow"
        add_required(workflow_file, f"{workflow_reason}: {wf['description']}")
        for quick_ref in wf.get("quick_refs", []):
            add_required(quick_ref, f"Workflow quick companion: {workflow}")

        core_quick = "references/core_rules_quick.md"
        add_required(core_quick, "Core rules quick reference")

        sdk_quick = "references/sdk_abstraction_quick.md"
        add_required(sdk_quick, "SDK abstraction quick reference")

        plat_quick = f"platforms/{platform}_quick.md"
        if (ROOT / plat_quick).is_file():
            add_required(plat_quick, f"Platform quick doc: {platform}")
        elif wf.get("quick_platform_optional"):
            quality_risks.append(f"compact {workflow} omits full {platform} platform doc; use standard for platform API details")
        else:
            add_required(plat["doc"], f"Platform doc: {platform} (quick doc missing)")

        rtos_quick = rtos_entry.get("quick_doc")
        if rtos_quick and (ROOT / rtos_quick).is_file():
            add_required(rtos_quick, f"RTOS quick doc: {rtos}")
        else:
            add_required(rtos_entry["doc"], f"RTOS doc: {rtos} (quick doc missing)")

        constraint_doc_mode = "shards"
        if constraints:
            shards = set()
            constraint_doc_mode = "micro"
            for c in constraints:
                c_upper = c.upper()
                micro_file = MICRO_SHARDS.get(c_upper)
                if micro_file and (ROOT / micro_file).is_file():
                    if micro_file not in required_files:
                        required_files.append(micro_file)
                        reasons[micro_file] = f"Micro constraint: {c_upper}"
                    micro_constraints_loaded.append(c_upper)
                    continue

                shard = CONSTRAINT_TO_SHARD.get(c_upper)
                if shard:
                    shards.add(shard)
                    fallback_shards.append(shard)
                else:
                    uncovered_constraints.append(c_upper)
            if shards:
                add_constraint_shards(shards)
            if fallback_shards:
                constraint_doc_mode = "mixed"
        elif wf.get("quick_constraint_mode") == "embedded":
            constraint_doc_mode = "quick_embedded"
            quality_risks.append(f"compact {workflow} uses embedded quick constraints; use standard for full constraint shards")
        else:
            add_constraint_shards(set(wf["constraint_shards"]))

        upgrade_hints = [
            "Use standard budget for platform/RTOS API details",
            "Use full budget for cross-shard or architecture-wide review",
        ]
        if workflow == "lvgl_page":
            upgrade_hints.insert(0, "Use standard budget for LVGL renderer, platform decoder, or media details")
        if not quality_risks:
            quality_risks = ["compact budget omits detailed platform/RTOS docs"]

    elif budget == "standard":
        qi = "references/constraint_quick_index.md"
        add_required(qi, "C1-C46 quick constraint index")
        add_required(wf["file"], f"Workflow: {wf['description']}")
        add_required("references/core_rules.md", "Core rules")
        add_required("references/sdk_abstraction.yaml", "SDK abstraction map")

        add_required(plat["doc"], f"Platform doc: {platform}")
        add_required(plat["sdk_map"], f"Platform SDK map: {platform}", required_exists=False)
        add_required(rtos_entry["doc"], f"RTOS doc: {rtos}")
        add_required(rtos_entry["sdk_map"], f"RTOS SDK map: {rtos}", required_exists=False)

        shards = set(wf["constraint_shards"])
        for c in constraints:
            shard = CONSTRAINT_TO_SHARD.get(c.upper())
            if shard:
                shards.add(shard)
        add_constraint_shards(shards)

        upgrade_hints = ["Use full budget for cross-shard or architecture-wide review"]
        quality_risks = []

    elif budget == "full":
        qi = "references/constraint_quick_index.md"
        add_required(qi, "C1-C46 quick constraint index")
        add_required(wf["file"], f"Workflow: {wf['description']}")
        add_required("references/core_rules.md", "Core rules")
        add_required("references/sdk_abstraction.yaml", "SDK abstraction map")

        add_required(plat["doc"], f"Platform doc: {platform}")
        add_required(plat["sdk_map"], f"Platform SDK map: {platform}", required_exists=False)
        add_required(rtos_entry["doc"], f"RTOS doc: {rtos}")
        add_required(rtos_entry["sdk_map"], f"RTOS SDK map: {rtos}", required_exists=False)

        shards = set(wf["constraint_shards"])
        for c in constraints:
            shard = CONSTRAINT_TO_SHARD.get(c.upper())
            if shard:
                shards.add(shard)
        add_constraint_shards(shards)

        for f, r in [
            ("references/skill_structure.md", "Skill structure"),
            ("references/platform_diff_matrix.md", "Platform diff matrix"),
            ("references/constraint_graph.md", "Constraint graph"),
        ]:
            add_required(f, r, required_exists=False)

        upgrade_hints = []
        quality_risks = []

    else:
        return {"error": f"Unknown budget: {budget}"}

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

    # ── Select prompts ──
    selected_prompts = []
    for prompt in wf.get("prompts", []):
        if (ROOT / prompt).is_file():
            selected_prompts.append(prompt)

    # ── Enforce compact hard limit (8k tokens) ──
    COMPACT_HARD_LIMIT = 8000
    budget_warning = None
    if budget == "compact" and total_tokens > COMPACT_HARD_LIMIT:
        budget_warning = f"compact plan is {total_tokens} tokens (limit: {COMPACT_HARD_LIMIT}); removing non-essential files"
        # Remove non-essential files until under limit
        essential_prefixes = ("workflows/", "references/core_rules", "references/constraint_quick_index")
        while total_tokens > COMPACT_HARD_LIMIT and len(files_with_reason) > 3:
            # Find least essential file
            for i in range(len(files_with_reason) - 1, -1, -1):
                f = files_with_reason[i]
                if not any(f["path"].startswith(p) for p in essential_prefixes):
                    total_tokens -= f["estimated_tokens"]
                    files_with_reason.pop(i)
                    break
            else:
                break  # All remaining are essential
    elif budget == "standard" and total_tokens > 30000:
        budget_warning = f"standard plan is {total_tokens} tokens; consider full when over 30k"

    return {
        "workflow": workflow,
        "workflow_description": wf["description"],
        "platform": platform,
        "platform_primary": plat["primary"],
        "rtos": rtos,
        "rtos_primary": rtos_entry["primary"],
        "budget_mode": budget,
        "required_files": files_with_reason,
        "selected_prompts": selected_prompts,
        "forbidden_by_default": FORBIDDEN_BY_DEFAULT,
        "estimated_tokens": total_tokens,
        "budget_warning": budget_warning,
        "upgrade_hint": upgrade_hints,
        "quality_risk": quality_risks,
        "constraint_doc_mode": constraint_doc_mode,
        "micro_constraints_loaded": micro_constraints_loaded,
        "fallback_shards": fallback_shards,
        "uncovered_constraints": uncovered_constraints,
        "constraint_shards_loaded": constraint_shards_loaded,
    }


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

    for wf_id in WORKFLOWS:
        for budget in ["compact", "standard", "full"]:
            plan = build_load_plan(wf_id, "esp32", "freertos", budget=budget)
            check(f"{wf_id}+{budget}: no error", "error" not in plan)
            check(f"{wf_id}+{budget}: has required_files", len(plan.get("required_files", [])) > 0)
            check(f"{wf_id}+{budget}: has estimated_tokens", plan.get("estimated_tokens", 0) > 0)
            check(f"{wf_id}+{budget}: has budget_mode", plan.get("budget_mode") == budget)

    plan_esp32 = build_load_plan("code_review", "esp32", "freertos")
    plan_zephyr = build_load_plan("code_review", "esp32", "zephyr")
    check("esp32 platform doc", any("platforms/esp32" in f["path"] for f in plan_esp32["required_files"]))
    check("zephyr rtos doc", any("zephyr" in f["path"] for f in plan_zephyr["required_files"]))

    plan_c3 = build_load_plan("code_review", "esp32", "freertos", ["C3"])
    check("C3 adds micro-shard", any("micro_C03" in f["path"] for f in plan_c3["required_files"]))

    plan_c46 = build_load_plan("code_review", "esp32", "freertos", ["C46"])
    check("C46 maps to bluetooth shard", any("constraint_bluetooth" in f["path"] for f in plan_c46["required_files"]))
    check("C46 is covered", "C46" not in plan_c46.get("uncovered_constraints", []))

    plan = build_load_plan("crash_debug", "esp32", "freertos")
    check("forbidden_by_default present", len(plan.get("forbidden_by_default", [])) > 0)
    check("constraint_detail forbidden", "references/constraint_detail.md" in plan.get("forbidden_by_default", []))

    plan_bad = build_load_plan("unknown_workflow", "esp32", "freertos")
    check("unknown workflow returns error", "error" in plan_bad)

    plan_bad_plat = build_load_plan("code_review", "unknown_platform", "freertos")
    check("unknown platform returns error", "error" in plan_bad_plat)

    plan_bad_rtos = build_load_plan("code_review", "esp32", "unknown_rtos")
    check("unknown rtos returns error", "error" in plan_bad_rtos)

    plan_json = json.dumps(build_load_plan("code_review", "esp32", "freertos"), ensure_ascii=False)
    check("JSON output valid", len(plan_json) > 100)

    queue_wdt = build_symptom_plan(
        "queue full xQueueSend failed; task watchdog timeout", "esp32", "freertos",
        allow_weak_route=True,
    )
    check("queue pressure + WDT prioritizes crash workflow", queue_wdt.get("workflow") == "crash_debug")

    # app_manifest should behave like lvgl_page in compact mode
    plan_manifest = build_load_plan("app_manifest", "esp32", "freertos", budget="compact")
    plan_lvgl = build_load_plan("lvgl_page", "esp32", "freertos", budget="compact")
    check("manifest+compact: no error", "error" not in plan_manifest)
    check("manifest+compact: uses quick workflow", any("quick" in f["path"] for f in plan_manifest["required_files"]))
    check("manifest+compact: no media shard", not any("constraint_media" in f["path"] for f in plan_manifest["required_files"]))
    check("manifest+compact: no voice shard", not any("constraint_voice" in f["path"] for f in plan_manifest["required_files"]))
    check("manifest+compact: same file count as lvgl_page",
          len(plan_manifest.get("required_files", [])) == len(plan_lvgl.get("required_files", [])))

    plan_lvgl_compact = build_load_plan("lvgl_page", "jl", "freertos", budget="compact")
    lvgl_paths = {f["path"] for f in plan_lvgl_compact.get("required_files", [])}
    check("lvgl compact uses quick workflow", "workflows/l3_lvgl_page_quick.md" in lvgl_paths)
    check("lvgl compact has no bundled generator reference", "references/lvgl_design_codegen_quick.md" not in lvgl_paths)
    check("lvgl compact skips full jl platform doc", "platforms/jl.md" not in lvgl_paths)
    check("lvgl compact skips full review/media shards", {"references/constraint_review.md", "references/constraint_media.md"}.isdisjoint(lvgl_paths))
    check("lvgl compact uses embedded constraints", plan_lvgl_compact.get("constraint_doc_mode") == "quick_embedded")
    check("lvgl compact stays under 8k estimated tokens", plan_lvgl_compact.get("estimated_tokens", 0) < 8000)

    for case_id, case in QUALITY_CASES.items():
        plan = build_load_plan(case["workflow"], case["platform"], case.get("rtos", "freertos"),
                               case.get("constraints", []), "compact")
        check(f"case {case_id}: no error", "error" not in plan)
        check(f"case {case_id}: has required_files", len(plan.get("required_files", [])) > 0)
        check(f"case {case_id}: budget_mode is compact", plan.get("budget_mode") == "compact")
        for f in plan.get("required_files", []):
            if f["path"] in FORBIDDEN_BY_DEFAULT:
                check(f"case {case_id}: no forbidden file {f['path']}", False)
                break
        else:
            check(f"case {case_id}: no forbidden files", True)

    # ── Snapshot fixtures: pin expected file sets for key combos ──
    SNAPSHOT_FIXTURES = [
        ("lvgl_page", "jl", "freertos", ["compact"]),
        ("memory_analysis", "esp32", "freertos", ["compact", "standard"]),
        ("code_review", "esp32", "freertos", ["compact", "standard"]),
        ("sdk_trim", "bk", "zephyr", ["compact"]),
        ("crash_debug", "bk", "freertos", ["compact"]),
    ]
    snapshots: dict[str, list[str]] = {}
    for wf, plat, rtos, budgets in SNAPSHOT_FIXTURES:
        for budget in budgets:
            key = f"{wf}+{plat}+{rtos}+{budget}"
            plan = build_load_plan(wf, plat, rtos, budget=budget)
            check(f"snapshot {key}: no error", "error" not in plan)
            paths = [f["path"] for f in plan.get("required_files", [])]
            snapshots[key] = paths
            check(f"snapshot {key}: has required_files", len(paths) > 0)

    # ── Assertion: required files must exist on disk ──
    for key, paths in snapshots.items():
        for p in paths:
            check(f"{key}: required file exists: {p}", (ROOT / p).is_file())

    # ── Assertion: forbidden files must not appear in required ──
    for key, paths in snapshots.items():
        forbidden_leaked = [p for p in paths if p in FORBIDDEN_BY_DEFAULT]
        check(f"{key}: no forbidden leaked", len(forbidden_leaked) == 0)

    # ── Assertion: platform and RTOS docs must not be mixed ──
    PLATFORM_ONLY = {"platforms/esp32", "platforms/stm32", "platforms/jl", "platforms/bk"}
    RTOS_ONLY = {"platforms/freertos", "platforms/zephyr"}
    for key, paths in snapshots.items():
        # Both can be present, but a platform doc should not also be an RTOS doc.
        mixed = [p for p in paths
                 if any(po in p for po in PLATFORM_ONLY) and any(ro in p for ro in RTOS_ONLY)]
        check(f"{key}: no platform/RTOS doc mixed", len(mixed) == 0)

    # ── Assertion: each workflow loads at least one workflow doc and one constraint doc ──
    for key, paths in snapshots.items():
        has_workflow_doc = any("workflows/" in p for p in paths)
        has_constraint = any("constraint_" in p or "core_rules" in p for p in paths)
        check(f"{key}: has workflow doc", has_workflow_doc)
        check(f"{key}: has constraint doc", has_constraint)

    # ── classify_request tests ──
    CLASSIFY_CASES = [
        # (request, expected_workflow_or_None, expect_clarification)
        ("Review this ESP32 cJSON code", "code_review", False),
        ("帮我审查这个代码", "code_review", False),
        ("Analyze heap fragmentation", "memory_analysis", False),
        ("内存泄漏问题", "memory_analysis", False),
        ("Project review before release", "project_review", False),
        ("GPIO conflict between SPI and I2C", "hw_sw_debug", False),
        ("ESP32 crash: Guru Meditation Error", "crash_debug", False),
        ("设备死机看门狗重启", "crash_debug", False),
        ("Generate an LVGL page from design", "lvgl_page", False),
        ("根据设计截图生成 LVGL 界面", "lvgl_page", False),
        ("Generate multi-page app with manifest", "app_manifest", False),
        ("用 manifest 生成多页应用", "app_manifest", False),
        ("Create a new sensor module", "new_module", False),
        ("新建一个 MQTT 模块", "new_module", False),
        ("Board bring-up for STM32", "bring_up", False),
        ("新板子验证外设", "bring_up", False),
        ("Trim unused SDK drivers", "sdk_trim", False),
        ("裁剪 SDK 只保留 WiFi", "sdk_trim", False),
        # Priority/exclude: crash keywords override generate routes
        ("UI 卡死重启", "crash_debug", False),
        ("页面死机了", "crash_debug", False),
        ("task 内存泄漏", "memory_analysis", False),
        ("OTA 代码审查", "code_review", False),
        # Clarification cases
        ("help", None, True),
        ("帮我看看这个问题", None, True),
        ("LVGL page crashes with HardFault, need both", "crash_debug", False),
    ]
    for request, expected_wf, expect_clar in CLASSIFY_CASES:
        result = classify_request(request)
        is_clar = result.get("clarification_required", False)
        actual_wf = result.get("workflow") if not is_clar else None
        if expect_clar:
            check(f"classify: '{request[:30]}...' → clarification", is_clar)
        else:
            check(f"classify: '{request[:30]}...' → {expected_wf}", actual_wf == expected_wf and not is_clar)

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Context Router: build a minimal load plan")
    parser.add_argument("--workflow", "-w",
                        choices=list(WORKFLOWS.keys()),
                        help="Workflow ID")
    parser.add_argument("--platform", "-p",
                        choices=list(PLATFORM_DOCS.keys()),
                        default="esp32",
                        help="Platform ID")
    parser.add_argument("--rtos", "-r",
                        choices=list(RTOS_DOCS.keys()),
                        default="freertos",
                        help="RTOS ID")
    parser.add_argument("--constraints", "-c", nargs="*",
                        help="Constraint IDs, for example C2 C3")
    parser.add_argument("--budget", "-b",
                        choices=["compact", "standard", "full"],
                        default="compact",
                        help="Load budget: compact / standard / full")
    parser.add_argument("--case",
                        choices=list(QUALITY_CASES.keys()),
                        help="Quality case ID with predefined workflow/platform/constraints")
    parser.add_argument("--classify",
                        help="Classify a natural language request into domain + workflow")
    parser.add_argument("--symptom-text",
                        help="Symptom text or log excerpt to route")
    parser.add_argument("--symptom-file",
                        help="Path to a symptom or log text file")
    parser.add_argument("--probe-detail",
                        choices=["compact", "full"],
                        default="compact",
                        help="Diagnostic probe detail: compact / full")
    parser.add_argument("--allow-weak-route",
                        action="store_true",
                        help="Allow weak symptom routes instead of returning missing_facts")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON")
    parser.add_argument("--self-test", action="store_true",
                        help="Run self-test")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.classify:
        result = classify_request(args.classify)
        if args.json:
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            if result.get("clarification_required"):
                print(f"Clarification needed: {result['clarification_reason']}")
            else:
                print(f"Domain: {result['domain']}")
                print(f"Workflow: {result['workflow']}")
                print(f"Reason: {result['routing_reason']}")
        return 0

    if args.symptom_text or args.symptom_file:
        symptom_text = args.symptom_text
        if args.symptom_file:
            sf = Path(args.symptom_file)
            if not sf.is_file():
                parser.error(f"Symptom file not found: {sf}")
            symptom_text = sf.read_text(encoding="utf-8", errors="ignore")
        if not symptom_text:
            parser.error("No symptom text provided")

        plan = build_symptom_plan(symptom_text, args.platform, args.rtos, args.budget,
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
            print(f"RTOS: {plan.get('inferred_rtos', 'unknown')} ({plan.get('rtos_source', 'unknown')})")
            print(f"Likely constraints: {', '.join(plan.get('likely_constraints', []))}")
            if plan.get('top_hypotheses'):
                print(f"Top hypotheses: {', '.join(plan.get('top_hypotheses', []))}")
            if plan.get('diagnostic_probes'):
                print("Diagnostic probes:")
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
            print(f"Budget: {plan.get('budget_mode')} | Tokens: ~{plan.get('estimated_tokens')}")
        return 0

    if args.case:
        case = QUALITY_CASES[args.case]
        workflow = case["workflow"]
        platform = case["platform"]
        rtos = case.get("rtos", "freertos")
        constraints = case.get("constraints", [])
        budget = args.budget
    elif args.workflow:
        workflow = args.workflow
        platform = args.platform
        rtos = args.rtos
        constraints = args.constraints
        budget = args.budget
    else:
        parser.error("--workflow, --case, or --symptom-text is required")

    plan = build_load_plan(workflow, platform, rtos, constraints, budget)

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

        print(f"Context Router: {plan['workflow_description']} @ {plan['platform']} + {plan['rtos']}")
        print(f"Budget mode: {plan['budget_mode']}")
        print(f"Estimated tokens: ~{plan['estimated_tokens']}")
        if plan.get("budget_warning"):
            print(f"Warning: {plan['budget_warning']}")
        print(f"Required files ({len(plan['required_files'])}):")
        for f in plan["required_files"]:
            print(f"  {f['path']} - {f['reason']} (~{f['estimated_tokens']} tokens)")
        print(f"Forbidden by default:")
        for f in plan["forbidden_by_default"]:
            print(f"  {f}")
        if plan.get("constraint_shards_loaded"):
            print(f"Constraint shards: {', '.join(plan['constraint_shards_loaded'])}")
        if plan.get("upgrade_hint"):
            print("Upgrade hints:")
            for h in plan["upgrade_hint"]:
                print(f"  - {h}")
        if plan.get("quality_risk"):
            print("Quality risks:")
            for r in plan["quality_risk"]:
                print(f"  - {r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
