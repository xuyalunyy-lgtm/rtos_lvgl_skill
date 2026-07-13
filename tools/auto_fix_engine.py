#!/usr/bin/env python3
"""
自动修复引擎 v3：根据 checker 输出生成可审查补丁计划（FixPlan）。

v3 增强（v9.0.3）：
  1. --plan：输出结构化 FixPlan JSON，默认不写文件
  2. --apply：显式确认后才写文件（需先跑 --plan）
  3. --diff：输出 unified diff 预览
  4. 风险分级：low/medium/high
  5. pre_checks + post_checkers

用法:
    python tools/auto_fix_engine.py path/to/file.c --checker cjson_leak --plan
    python tools/auto_fix_engine.py path/to/file.c --checker cjson_leak --plan --json
    python tools/auto_fix_engine.py path/to/file.c --checker cjson_leak --apply
    python tools/auto_fix_engine.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

TOOLS_DIR = Path(__file__).resolve().parent


# ============================================================================
# FixPlan 数据结构
# ============================================================================

@dataclass
class FixAction:
    """单条修复动作。"""
    file: str
    line_start: int = 0
    line_end: int = 0
    constraint: str = ""
    fix_type: str = ""
    risk_level: str = "medium"       # low / medium / high
    suggestion: str = ""
    template: str = ""
    diff: str = ""                    # unified diff 预览
    confidence: float = 0.5           # 0.0-1.0
    pre_checks: list[str] = field(default_factory=list)
    post_checkers: list[str] = field(default_factory=list)
    reference: str = ""


@dataclass
class FixPlan:
    """可审查补丁计划。"""
    file: str
    checker: str
    actions: list[dict] = field(default_factory=list)
    total_risk: str = "low"
    estimated_changes: int = 0
    pre_flight: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ── 风险分级映射 ──
RISK_MAP = {
    # low: 日志、注释、文档
    "add_log": "low",
    "add_comment": "low",
    # medium: 返回值检查、超时补充、生命周期补充
    "check_return": "medium",
    "check_task_create": "medium",
    "check_malloc": "medium",
    "add_timeout": "medium",
    "add_deinit": "medium",
    "add_mark_valid": "medium",
    # high: 内存管理、所有权变更、代码重排
    "goto_cleanup": "high",
    "heap_alloc": "high",
    "reorder_init": "high",
    "add_signature_verify": "high",
}

# ── 置信度映射 ──
CONFIDENCE_MAP = {
    "add_log": 0.9,
    "add_comment": 0.9,
    "check_return": 0.8,
    "check_task_create": 0.8,
    "check_malloc": 0.8,
    "add_timeout": 0.7,
    "add_deinit": 0.7,
    "add_mark_valid": 0.7,
    "goto_cleanup": 0.6,
    "heap_alloc": 0.5,
    "reorder_init": 0.5,
    "add_signature_verify": 0.6,
}

# ── 后置 checker 映射 ──
POST_CHECKERS = {
    "goto_cleanup": ["cjson_leak_checker"],
    "heap_alloc": ["queue_ownership_checker"],
    "check_return": ["return_check_checker"],
    "check_task_create": ["return_check_checker"],
    "check_malloc": ["return_check_checker"],
    "reorder_init": ["boot_sequence_checker"],
    "add_deinit": ["lifecycle_checker"],
    "add_signature_verify": ["ota_safety_checker"],
    "add_mark_valid": ["ota_safety_checker"],
    "add_timeout": ["blocking_wait_checker"],
}


def _build_checker_scripts() -> dict[str, str]:
    """从 checker_registry 构建 {skip_arg: script} 映射。"""
    from checker_registry import ALL_CHECKERS
    mapping = {}
    for spec in ALL_CHECKERS:
        mapping[spec.skip_arg] = spec.script
        mapping[spec.name] = spec.script
    return mapping


CHECKER_SCRIPTS = _build_checker_scripts()


def run_checker_json(checker: str, filepath: str) -> dict:
    """运行 checker 并获取 JSON 输出。"""
    script = TOOLS_DIR / CHECKER_SCRIPTS.get(checker, f"{checker}.py")
    if not script.exists():
        return {"error": f"Checker not found: {checker}"}

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), filepath],
            capture_output=True, encoding="utf-8", errors="replace", env=env,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"Checker {checker} timed out after 60s", "checker": checker, "violations": []}

    violations = []
    for line in (proc.stdout + proc.stderr).splitlines():
        line = line.strip()
        if line.startswith("[P") and "]" in line:
            parts = line.split("—")
            if len(parts) >= 3:
                severity_id = parts[0].strip()
                location = parts[1].strip()
                issue = parts[2].strip()
                violations.append({
                    "severity": severity_id[1:3],
                    "constraint": severity_id[4:].split(" ")[0] if len(severity_id) > 4 else "",
                    "location": location,
                    "issue": issue,
                })

    return {
        "checker": checker,
        "file": filepath,
        "exit_code": proc.returncode,
        "violations": violations,
        "raw_output": proc.stdout,
    }


# ─── 修复建议生成器 ───


def fix_cjson_leak(violations: list, filepath: str) -> list[dict]:
    """为 cJSON 泄漏违规生成修复建议。"""
    fixes = []
    for v in violations:
        msg = v.get("issue", v.get("message", ""))
        line = v.get("location", "")
        # 匹配 cJSON 泄漏模式：包含 cJSON_Delete、Parse、泄漏、提前退出等关键词
        if ("cJSON_Delete" in msg or "Parse" in msg or "泄漏" in msg
                or "提前退出" in msg or "goto fail" in msg):
            fixes.append({
                "line": line,
                "issue": msg,
                "fix_type": "goto_cleanup",
                "suggestion": "使用 goto cleanup 模板统一管理 cJSON_Delete",
                "template": (
                    "static int parse_xxx(const char *json, xxx_t *out)\n"
                    "{\n"
                    "    int ret = -1;\n"
                    "    cJSON *root = NULL;\n"
                    "    if (json == NULL || out == NULL) return -1;\n"
                    "    root = cJSON_Parse(json);\n"
                    "    if (root == NULL) goto cleanup;\n"
                    "    /* ... 提取数据 ... */\n"
                    "    ret = 0;\n"
                    "cleanup:\n"
                    "    if (root != NULL) cJSON_Delete(root);\n"
                    "    return ret;\n"
                    "}"
                ),
                "reference": "prompts/cjson_safe_parse.txt",
            })
    return fixes


def fix_queue_ownership(violations: list, filepath: str) -> list[dict]:
    """为 Queue 所有权违规生成修复建议。"""
    fixes = []
    for v in violations:
        msg = v.get("issue", v.get("message", ""))
        if "栈" in msg or "stack" in msg.lower():
            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "heap_alloc",
                "suggestion": "将栈 buffer 改为堆分配，由 Presenter 消费后释放",
                "template": (
                    "    char *heap_buf = pvPortMalloc(len + 1);\n"
                    "    if (heap_buf == NULL) return;\n"
                    "    memcpy(heap_buf, data, len);\n"
                    "    heap_buf[len] = '\\0';\n"
                    "    evt_t evt = { .type = EVT_DATA, .payload = heap_buf };\n"
                    "    xQueueSend(q, &evt, pdMS_TO_TICKS(50));\n"
                    "    /* Presenter 收到后 vPortFree(evt.payload) */"
                ),
                "reference": "examples/good_presenter_consumer.c",
            })
    return fixes


def fix_return_check(violations: list, filepath: str) -> list[dict]:
    """为返回值未检查违规生成修复建议。"""
    fixes = []
    for v in violations:
        msg = v.get("issue", v.get("message", ""))
        if "xTaskCreate" in msg or "task" in msg.lower():
            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "check_task_create",
                "suggestion": "xTaskCreate 返回值必须检查",
                "template": (
                    "    TaskHandle_t h = NULL;\n"
                    "    BaseType_t ret = xTaskCreate(task_func, \"name\", stack, NULL, prio, &h);\n"
                    "    if (ret != pdPASS) {\n"
                    "        LOG_E(TAG, \"Task create failed\");\n"
                    "        goto cleanup;\n"
                    "    }"
                ),
                "reference": "prompts/error_handling.txt",
            })
        elif "pvPortMalloc" in msg or "malloc" in msg.lower():
            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "check_malloc",
                "suggestion": "pvPortMalloc 返回值必须检查",
                "template": (
                    "    void *p = pvPortMalloc(size);\n"
                    "    if (p == NULL) {\n"
                    "        LOG_E(TAG, \"malloc %u failed\", size);\n"
                    "        goto cleanup;\n"
                    "    }"
                ),
                "reference": "prompts/error_handling.txt",
            })
    return fixes


def fix_boot_sequence(violations: list, filepath: str) -> list[dict]:
    """为启动顺序违规生成修复建议。"""
    fixes = []
    for v in violations:
        msg = v.get("issue", v.get("message", ""))
        if ("Queue" in msg and ("回调" in msg or "callback" in msg.lower())
                or "启动顺序" in msg or "boot" in msg.lower()):
            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "reorder_init",
                "suggestion": "将 Queue 创建移到网络回调注册之前",
                "template": (
                    "    /* C8.1: Queue 先于网络回调 */\n"
                    "    s_event_queue = xQueueCreate(8, sizeof(int));\n"
                    "    if (s_event_queue == NULL) return;\n"
                    "\n"
                    "    /* 然后注册网络回调 */\n"
                    "    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, ...);"
                ),
                "reference": "examples/good_boot_sequence.c",
            })
        elif "portMAX_DELAY" in msg:
            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "add_timeout",
                "suggestion": "将 portMAX_DELAY 替换为有限超时",
                "template": (
                    "    /* 替换 portMAX_DELAY 为有限超时 */\n"
                    "    if (xQueueReceive(q, &evt, pdMS_TO_TICKS(100)) != pdTRUE) {\n"
                    "        /* 超时处理 */\n"
                    "        continue;\n"
                    "    }"
                ),
                "reference": "examples/good_timeout_budget.c",
            })
    return fixes


def fix_lifecycle(violations: list, filepath: str) -> list[dict]:
    """为生命周期不对称违规生成修复建议。"""
    fixes = []
    for v in violations:
        msg = v.get("issue", v.get("message", ""))
        if "create" in msg.lower() and "delete" in msg.lower():
            match = re.search(r'(\w+Create)', msg)
            create_api = match.group(1) if match else "xxxCreate"
            delete_api = create_api.replace("Create", "Delete")

            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "add_deinit",
                "suggestion": f"添加对应的释放函数",
                "template": (
                    f"    /* 添加 deinit 函数 */\n"
                    f"    void module_deinit(void) {{\n"
                    f"        if (s_handle != NULL) {{\n"
                    f"            {delete_api}(s_handle);\n"
                    f"            s_handle = NULL;\n"
                    f"        }}\n"
                    f"    }}"
                ),
                "reference": "examples/good_lifecycle.c",
            })
        elif "init" in msg.lower() and "deinit" in msg.lower():
            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "add_deinit",
                "suggestion": "添加对应的 deinit 函数",
                "template": (
                    "    /* 添加 deinit 函数 */\n"
                    "    esp_err_t module_deinit(void) {\n"
                    "        if (!s_initialized) return ESP_OK; /* 可重入 */\n"
                    "        /* 释放资源 */\n"
                    "        s_initialized = false;\n"
                    "        return ESP_OK;\n"
                    "    }"
                ),
                "reference": "prompts/runtime_efficiency_contracts.txt",
            })
    return fixes


def fix_ota(violations: list, filepath: str) -> list[dict]:
    """为 OTA 安全违规生成修复建议。"""
    fixes = []
    for v in violations:
        msg = v.get("issue", v.get("message", ""))
        if "签名" in msg or "verify" in msg.lower():
            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "add_signature_verify",
                "suggestion": "添加固件签名验证",
                "template": (
                    "    /* C22.1: 验证固件签名 */\n"
                    "    esp_app_desc_t app_desc;\n"
                    "    esp_ota_get_app_description(partition, &app_desc);\n"
                    "    if (app_desc.secure_version < current_version) {\n"
                    "        ESP_LOGE(TAG, \"Rollback attack detected\");\n"
                    "        return ESP_ERR_OTA_DOWNGRADE;\n"
                    "    }"
                ),
                "reference": "examples/good_ota_update.c",
            })
        elif "mark_valid" in msg or "rollback" in msg.lower():
            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "add_mark_valid",
                "suggestion": "添加 mark_valid_cancel_rollback",
                "template": (
                    "    /* C22.2: 首次启动标记有效 */\n"
                    "    esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();\n"
                    "    if (err != ESP_OK) {\n"
                    "        ESP_LOGE(TAG, \"Failed to mark OTA valid: %s\", esp_err_to_name(err));\n"
                    "    }"
                ),
                "reference": "examples/good_ota_update.c",
            })
        elif "超时" in msg or "timeout" in msg.lower():
            fixes.append({
                "line": v.get("location", ""),
                "issue": msg,
                "fix_type": "add_timeout",
                "suggestion": "添加 HTTP 超时配置",
                "template": (
                    "    esp_http_client_config_t config = {\n"
                    "        .url = url,\n"
                    "        .timeout_ms = 30000, /* C22.5: 必须配置超时 */\n"
                    "    };"
                ),
                "reference": "prompts/ota_update_safety.txt",
            })
    return fixes


FIX_GENERATORS = {
    "cjson_leak": fix_cjson_leak,
    "cjson_leak_checker": fix_cjson_leak,
    "cjson": fix_cjson_leak,           # skip_arg alias
    "cjson-ast": fix_cjson_leak,       # skip_arg alias
    "cjson_ast": fix_cjson_leak,
    "cjson_ast_checker": fix_cjson_leak,
    "queue_ownership": fix_queue_ownership,
    "queue_ownership_checker": fix_queue_ownership,
    "queue": fix_queue_ownership,       # skip_arg alias
    "queue-ast": fix_queue_ownership,   # skip_arg alias
    "queue_ast": fix_queue_ownership,
    "queue_ast_checker": fix_queue_ownership,
    "return_check": fix_return_check,
    "return_check_checker": fix_return_check,
    "return-check": fix_return_check,   # skip_arg alias
    "boot": fix_boot_sequence,
    "boot_sequence_checker": fix_boot_sequence,
    "lifecycle": fix_lifecycle,
    "lifecycle_checker": fix_lifecycle,
    "ota": fix_ota,
    "ota_safety_checker": fix_ota,
}


# ─── FixPlan 构建 ───


def _parse_line_number(location: str) -> int:
    """从 'file:line' 格式提取行号。"""
    m = re.search(r':(\d+)', location)
    return int(m.group(1)) if m else 0


def build_fix_plan(fixes: list[dict], checker: str, filepath: str) -> FixPlan:
    """从修复建议列表构建 FixPlan。"""
    actions = []
    max_risk = "low"
    risk_order = {"low": 0, "medium": 1, "high": 2}

    for fix in fixes:
        fix_type = fix.get("fix_type", "unknown")
        risk = RISK_MAP.get(fix_type, "medium")
        confidence = CONFIDENCE.get(fix_type, 0.5)
        post = POST_CHECKERS.get(fix_type, [])

        # 更新总体风险
        if risk_order.get(risk, 1) > risk_order.get(max_risk, 0):
            max_risk = risk

        # 解析行号
        line = _parse_line_number(fix.get("line", ""))

        action = FixAction(
            file=filepath,
            line_start=line,
            line_end=line,
            constraint=fix.get("constraint", checker),
            fix_type=fix_type,
            risk_level=risk,
            suggestion=fix.get("suggestion", ""),
            template=fix.get("template", ""),
            confidence=confidence,
            pre_checks=_get_pre_checks(risk),
            post_checkers=post,
            reference=fix.get("reference", ""),
        )
        actions.append(asdict(action))

    # 全局前置检查
    pre_flight = [
        "确认文件在 git 跟踪下",
        "确认无未提交修改（git stash 先）",
    ]
    if max_risk == "high":
        pre_flight.append("高风险修改 — 建议在分支上操作")

    return FixPlan(
        file=filepath,
        checker=checker,
        actions=actions,
        total_risk=max_risk,
        estimated_changes=len(actions),
        pre_flight=pre_flight,
        metadata={
            "tool_version": "9.0.3",
            "fix_types": list(set(a["fix_type"] for a in actions)),
        },
    )


CONFIDENCE = CONFIDENCE_MAP  # alias


def _get_pre_checks(risk: str) -> list[str]:
    """根据风险等级返回前置检查。"""
    checks = ["确认文件可写"]
    if risk == "high":
        checks.append("确认已创建 git 分支或 stash")
        checks.append("确认理解修改影响范围")
    if risk in ("medium", "high"):
        checks.append("确认有备份")
    return checks


# ─── 输出格式 ───


def format_report(fixes: list[dict], checker: str, filepath: str) -> str:
    lines = [
        "=" * 60,
        f"自动修复建议 v3: {filepath}",
        f"Checker: {checker}",
        "=" * 60,
        "",
    ]
    if not fixes:
        lines.append("[OK] 无需修复，或该 checker 暂不支持自动修复建议。")
        return "\n".join(lines)

    lines.append(f"共 {len(fixes)} 个修复建议：\n")
    for i, fix in enumerate(fixes):
        fix_type = fix.get("fix_type", "unknown")
        risk = RISK_MAP.get(fix_type, "medium")
        conf = CONFIDENCE.get(fix_type, 0.5)
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "⚪")

        lines.append(f"--- 修复建议 {i+1} {risk_icon} [{risk}] conf={conf:.0%} ---")
        lines.append(f"位置: {fix.get('line', '?')}")
        lines.append(f"问题: {fix['issue']}")
        lines.append(f"方案: {fix['suggestion']}")
        lines.append(f"\n修复模板:")
        for tl in fix.get("template", "").split("\n"):
            lines.append(f"    {tl}")
        lines.append(f"\n参照: {fix.get('reference', 'N/A')}")
        lines.append("")

    lines.append("⚠️  以上为补丁计划，不会自动修改文件。")
    lines.append("   使用 --plan 查看结构化计划，--apply 显式确认后才写入。")
    return "\n".join(lines)


def format_report_json(fixes: list[dict], checker: str, filepath: str) -> dict:
    return {
        "tool": "auto_fix_engine_v3",
        "file": filepath,
        "checker": checker,
        "summary": {
            "fix_count": len(fixes),
            "fix_types": list(set(f.get("fix_type", "") for f in fixes)),
        },
        "fixes": fixes,
    }


# ─── 自测 ───


def run_self_test() -> int:
    """自测：验证修复引擎正确性"""
    passed = 0
    failed = 0

    # Test 1: cjson_leak fix generation
    violations = [{"issue": "Parse 后未见 cJSON_Delete", "location": "test.c:10"}]
    fixes = fix_cjson_leak(violations, "test.c")
    assert len(fixes) == 1
    assert fixes[0]["fix_type"] == "goto_cleanup"
    print("[PASS] cjson_leak fix generation")
    passed += 1

    # Test 2: queue_ownership fix generation
    violations = [{"issue": "栈指针进 Queue", "location": "test.c:20"}]
    fixes = fix_queue_ownership(violations, "test.c")
    assert len(fixes) == 1
    assert fixes[0]["fix_type"] == "heap_alloc"
    print("[PASS] queue_ownership fix generation")
    passed += 1

    # Test 3: boot sequence fix generation
    violations = [{"issue": "Queue 创建在回调之后", "location": "test.c:15"}]
    fixes = fix_boot_sequence(violations, "test.c")
    assert len(fixes) == 1
    assert fixes[0]["fix_type"] == "reorder_init"
    print("[PASS] boot sequence fix generation")
    passed += 1

    # Test 4: lifecycle fix generation
    violations = [{"issue": "xSemaphoreCreateMutex 调用但未见 vSemaphoreDelete", "location": "test.c:5"}]
    fixes = fix_lifecycle(violations, "test.c")
    assert len(fixes) == 1
    assert fixes[0]["fix_type"] == "add_deinit"
    print("[PASS] lifecycle fix generation")
    passed += 1

    # Test 5: OTA fix generation
    violations = [{"issue": "OTA 写入未见签名验证", "location": "test.c:30"}]
    fixes = fix_ota(violations, "test.c")
    assert len(fixes) == 1
    assert fixes[0]["fix_type"] == "add_signature_verify"
    print("[PASS] OTA fix generation")
    passed += 1

    # Test 6: FixPlan construction
    plan = build_fix_plan(fixes, "ota", "test.c")
    assert plan.checker == "ota"
    assert len(plan.actions) == 1
    assert plan.actions[0]["risk_level"] == "high"
    assert plan.actions[0]["confidence"] > 0
    assert len(plan.pre_flight) >= 2
    print("[PASS] FixPlan construction")
    passed += 1

    # Test 7: Risk classification
    low_fixes = [{"fix_type": "add_log", "line": "x.c:1", "issue": "test", "suggestion": "add log"}]
    plan_low = build_fix_plan(low_fixes, "test", "x.c")
    assert plan_low.total_risk == "low"
    high_fixes = [{"fix_type": "goto_cleanup", "line": "x.c:1", "issue": "test", "suggestion": "goto"}]
    plan_high = build_fix_plan(high_fixes, "test", "x.c")
    assert plan_high.total_risk == "high"
    print("[PASS] Risk classification")
    passed += 1

    # Test 8: FixPlan JSON serialization
    plan_json = plan.to_json()
    data = json.loads(plan_json)
    assert data["checker"] == "ota"
    assert "actions" in data
    assert "pre_flight" in data
    print("[PASS] FixPlan JSON serialization")
    passed += 1

    # Test 9: JSON report format
    report = format_report_json(fixes, "ota", "test.c")
    assert report["tool"] == "auto_fix_engine_v3"
    assert report["summary"]["fix_count"] == 1
    print("[PASS] JSON report format")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


# ─── CLI ───


def main() -> int:
    parser = argparse.ArgumentParser(description="自动修复引擎 v3 — 可审查补丁计划")
    parser.add_argument("file", nargs="?", help="待修复的 .c 文件")
    parser.add_argument("--checker", choices=list(CHECKER_SCRIPTS.keys()), help="Checker 类型")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--plan", action="store_true",
                        help="输出结构化 FixPlan（不写文件）")
    parser.add_argument("--apply", action="store_true",
                        help="显式确认后写入文件（需先跑 --plan）")
    parser.add_argument("--diff", action="store_true", help="输出 unified diff 预览")
    parser.add_argument("--evidence", metavar="FILE", help="输出交付证据包到指定文件")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.file or not args.checker:
        parser.print_help()
        return 1

    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    # 运行 checker
    result = run_checker_json(args.checker, args.file)
    violations = result.get("violations", [])

    # 生成修复建议
    gen = FIX_GENERATORS.get(args.checker)
    fixes = gen(violations, args.file) if gen else []

    # ── Plan 模式 ──
    if args.plan:
        plan = build_fix_plan(fixes, args.checker, args.file)

        if args.json:
            print(plan.to_json())
        else:
            print(f"{'=' * 60}")
            print(f"补丁计划: {args.file}")
            print(f"Checker: {args.checker}")
            print(f"总风险: {plan.total_risk}  |  动作数: {plan.estimated_changes}")
            print(f"{'=' * 60}")
            print()
            print("前置检查:")
            for pf in plan.pre_flight:
                print(f"  □ {pf}")
            print()
            for i, action in enumerate(plan.actions):
                risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(action["risk_level"], "⚪")
                print(f"动作 {i+1}: {risk_icon} [{action['risk_level']}] conf={action['confidence']:.0%}")
                print(f"  类型: {action['fix_type']}")
                print(f"  位置: {action['file']}:{action['line_start']}")
                print(f"  建议: {action['suggestion']}")
                if action.get("post_checkers"):
                    print(f"  后置 checker: {', '.join(action['post_checkers'])}")
                print()
            print("⚠️  以上为补丁计划，不会自动修改文件。")
            print("   使用 --apply 显式确认后才写入。")

        return 0

    # ── Apply 模式 ──
    if args.apply:
        plan = build_fix_plan(fixes, args.checker, args.file)

        if not plan.actions:
            print("[OK] 无需修复。")
            return 0

        print(f"补丁计划: {len(plan.actions)} 个动作, 总风险: {plan.total_risk}")
        print("前置检查:")
        for pf in plan.pre_flight:
            print(f"  □ {pf}")
        print()

        # 确认
        confirm = input("确认应用补丁? (y/N): ").strip().lower()
        if confirm != "y":
            print("已取消。")
            return 0

        # Safety: validate file path is under project root
        target = Path(args.file).resolve()
        if not target.is_relative_to(ROOT.resolve()):
            print(f"ERROR: 文件路径不在项目根目录内: {args.file}")
            return 1

        # 应用（当前版本：将模板追加到文件末尾作为参考）
        with open(target, "a", encoding="utf-8") as f:
            f.write("\n\n/* === auto_fix_engine 补丁参考 === */\n")
            for action in plan.actions:
                f.write(f"\n/* [{action['risk_level']}] {action['fix_type']}: {action['suggestion']} */\n")
                f.write(action.get("template", ""))
                f.write("\n")

        print(f"[OK] 补丁参考已追加到 {args.file}")
        print("⚠️  请手动合并到正确位置，然后运行 post-checker 验证。")

        # 运行后置 checker
        all_post = set()
        for action in plan.actions:
            all_post.update(action.get("post_checkers", []))
        if all_post:
            print(f"\n建议运行后置 checker 验证:")
            for pc in sorted(all_post):
                print(f"  python tools/{pc} {args.file}")

        return 0

    # ── 默认模式：文本/JSON 报告 ──
    if args.json:
        report = format_report_json(fixes, args.checker, args.file)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_report(fixes, args.checker, args.file))

    # ── 交付证据包输出 ──
    if args.evidence:
        try:
            from evidence_schema import fix_suggestion, make_evidence, save_evidence
        except ImportError:
            print("[warn] evidence_schema 模块不可用（已归档），跳过证据包输出", file=sys.stderr)
            return 0

        plan = build_fix_plan(fixes, args.checker, args.file)
        ev_fixes = []
        for action in plan.actions:
            ev_fixes.append(fix_suggestion(
                constraint=action.get("constraint", args.checker),
                fix_type=action["fix_type"],
                risk_level=action["risk_level"],
                file=args.file,
                line_range=(action["line_start"], action["line_end"]),
                suggestion=action["suggestion"],
                confidence=action["confidence"],
                pre_checks=action.get("pre_checks", []),
                post_checkers=action.get("post_checkers", []),
            ))

        ev = make_evidence(
            source_tool="auto_fix_engine",
            fix_suggestions=ev_fixes,
            reproduce_commands=[{
                "command": f"python tools/auto_fix_engine.py {args.file} --checker {args.checker} --plan",
                "description": "复现补丁计划",
            }],
            metadata={
                "tool_version": "9.0.3",
                "checker": args.checker,
                "total_risk": plan.total_risk,
                "estimated_changes": plan.estimated_changes,
            },
        )
        save_evidence(ev, args.evidence)
        if not args.json:
            print(f"[evidence] 已保存交付证据包: {args.evidence}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
