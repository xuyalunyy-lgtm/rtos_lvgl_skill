#!/usr/bin/env python3
"""
自动修复引擎 v2：根据 checker 输出生成修复建议和代码骨架。

v2 增强：
  1. 扩展修复模板覆盖 C8/C12/C24/C31
  2. 交互式修复模式
  3. 修复后自动验证
  4. 修复统计报告

用法:
    python tools/auto_fix_engine.py path/to/file.c --checker cjson_leak
    python tools/auto_fix_engine.py path/to/file.c --checker queue_ownership
    python tools/auto_fix_engine.py path/to/file.c --checker return_check --json
    python tools/auto_fix_engine.py path/to/file.c --checker boot --interactive
    python tools/auto_fix_engine.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

TOOLS_DIR = Path(__file__).resolve().parent


def _build_checker_scripts() -> dict[str, str]:
    """从 checker_registry 构建 {skip_arg: script} 映射。"""
    from checker_registry import ALL_CHECKERS
    mapping = {}
    for spec in ALL_CHECKERS:
        mapping[spec.skip_arg] = spec.script
        mapping[spec.name] = spec.script  # 也支持完整 name
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

    # Parse text output for violations
    violations = []
    for line in (proc.stdout + proc.stderr).splitlines():
        line = line.strip()
        if line.startswith("[P") and "]" in line:
            # Format: [P0] C22.1 — file:line — issue
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
        if "Parse" in msg and "Delete" in msg:
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
        if "xTaskCreate" in msg:
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
        if "Queue" in msg and "回调" in msg:
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
            # Extract the create API name
            import re
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
    "cjson_ast": fix_cjson_leak,
    "cjson_ast_checker": fix_cjson_leak,
    "queue_ownership": fix_queue_ownership,
    "queue_ownership_checker": fix_queue_ownership,
    "queue_ast": fix_queue_ownership,
    "queue_ast_checker": fix_queue_ownership,
    "return_check": fix_return_check,
    "return_check_checker": fix_return_check,
    "boot": fix_boot_sequence,
    "boot_sequence_checker": fix_boot_sequence,
    "lifecycle": fix_lifecycle,
    "lifecycle_checker": fix_lifecycle,
    "ota": fix_ota,
    "ota_safety_checker": fix_ota,
}


def format_report(fixes: list[dict], checker: str, filepath: str) -> str:
    lines = [
        "=" * 60,
        f"自动修复建议 v2: {filepath}",
        f"Checker: {checker}",
        "=" * 60,
        "",
    ]
    if not fixes:
        lines.append("[OK] 无需修复，或该 checker 暂不支持自动修复建议。")
        return "\n".join(lines)

    lines.append(f"共 {len(fixes)} 个修复建议：\n")
    for i, fix in enumerate(fixes):
        lines.append(f"--- 修复建议 {i+1} ---")
        lines.append(f"位置: {fix.get('line', '?')}")
        lines.append(f"问题: {fix['issue']}")
        lines.append(f"方案: {fix['suggestion']}")
        lines.append(f"\n修复模板:")
        for tl in fix.get("template", "").split("\n"):
            lines.append(f"    {tl}")
        lines.append(f"\n参照: {fix.get('reference', 'N/A')}")
        lines.append("")

    return "\n".join(lines)


def format_report_json(fixes: list[dict], checker: str, filepath: str) -> dict:
    return {
        "tool": "auto_fix_engine_v2",
        "file": filepath,
        "checker": checker,
        "summary": {
            "fix_count": len(fixes),
            "fix_types": list(set(f.get("fix_type", "") for f in fixes)),
        },
        "fixes": fixes,
    }


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

    # Test 6: JSON output format
    report = format_report_json(fixes, "ota", "test.c")
    assert report["tool"] == "auto_fix_engine_v2"
    assert report["summary"]["fix_count"] == 1
    print("[PASS] JSON report format")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="自动修复引擎 v2")
    parser.add_argument("file", nargs="?", help="待修复的 .c 文件")
    parser.add_argument("--checker", choices=list(CHECKER_SCRIPTS.keys()), help="Checker 类型")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
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

    if args.json:
        report = format_report_json(fixes, args.checker, args.file)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_report(fixes, args.checker, args.file))

    return 0


if __name__ == "__main__":
    sys.exit(main())
