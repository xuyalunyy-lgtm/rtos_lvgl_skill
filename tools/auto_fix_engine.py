#!/usr/bin/env python3
"""
自动修复引擎：根据 checker 输出生成修复建议和代码骨架。

串联 checker --json 输出 → 分析违规 → 生成针对性修复建议。

用法:
    python tools/auto_fix_engine.py path/to/file.c --checker cjson_leak
    python tools/auto_fix_engine.py path/to/file.c --checker queue_ownership
    python tools/auto_fix_engine.py path/to/file.c --checker return_check --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from checker_io import configure_stdout, output_json

TOOLS_DIR = Path(__file__).resolve().parent

CHECKER_SCRIPTS = {
    "cjson_leak": "cjson_leak_checker.py",
    "cjson_ast": "cjson_ast_checker.py",
    "queue_ownership": "queue_ownership_checker.py",
    "queue_ast": "queue_ast_checker.py",
    "return_check": "return_check_checker.py",
    "logging": "logging_checker.py",
}


def run_checker_json(checker: str, filepath: str) -> dict:
    """运行 checker 并获取 JSON 输出。"""
    script = TOOLS_DIR / CHECKER_SCRIPTS.get(checker, f"{checker}.py")
    if not script.exists():
        return {"error": f"Checker not found: {checker}"}
    proc = subprocess.run(
        [sys.executable, str(script), filepath, "--json"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": proc.stdout + proc.stderr}


# ─── 修复建议生成器 ───

def fix_cjson_leak(violations: list, filepath: str) -> list[dict]:
    """为 cJSON 泄漏违规生成修复建议。"""
    fixes = []
    for v in violations:
        msg = v.get("message", "")
        line = v.get("line", v.get("line_no", 0))
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
        elif "return" in msg.lower():
            fixes.append({
                "line": line,
                "issue": msg,
                "fix_type": "add_delete_before_return",
                "suggestion": "在 return 前添加 cJSON_Delete(root)",
                "template": "    cJSON_Delete(root);  /* 修复泄漏 */\n    return ret;",
                "reference": "prompts/cjson_safe_parse.txt",
            })
    return fixes


def fix_queue_ownership(violations: list, filepath: str) -> list[dict]:
    """为 Queue 所有权违规生成修复建议。"""
    fixes = []
    for v in violations:
        msg = v.get("message", "")
        line = v.get("line", 0)
        vtype = v.get("type", "")
        if "stack" in vtype or "栈" in msg:
            fixes.append({
                "line": line,
                "issue": msg,
                "fix_type": "heap_alloc",
                "suggestion": "将栈 buffer 改为堆分配，由 Presenter 消费后释放",
                "template": (
                    "    /* 替换栈 buffer 为堆分配 */\n"
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
        elif "cJSON" in msg or "cjson" in vtype:
            fixes.append({
                "line": line,
                "issue": msg,
                "fix_type": "extract_plain_data",
                "suggestion": "cJSON 不得进 Queue，须先提取 plain data 再 Delete",
                "template": (
                    "    cJSON *root = cJSON_Parse(json);\n"
                    "    if (root == NULL) return false;\n"
                    "    cJSON *text = cJSON_GetObjectItem(root, \"text\");\n"
                    "    char *heap_copy = strdup(text->valuestring);\n"
                    "    cJSON_Delete(root);  /* 进 Queue 前必须 Delete */\n"
                    "    evt_t evt = { .payload = heap_copy };\n"
                    "    xQueueSend(q, &evt, pdMS_TO_TICKS(50));"
                ),
                "reference": "prompts/cjson_safe_parse.txt",
            })
    return fixes


def fix_return_check(violations: list, filepath: str) -> list[dict]:
    """为返回值未检查违规生成修复建议。"""
    fixes = []
    for v in violations:
        msg = v.get("message", "")
        line = v.get("line", 0)
        if "xTaskCreate" in msg:
            fixes.append({
                "line": line,
                "issue": msg,
                "fix_type": "check_task_create",
                "suggestion": "xTaskCreate 返回值必须检查",
                "template": (
                    "    TaskHandle_t h = NULL;\n"
                    "    BaseType_t ret = xTaskCreate(task_func, \"name\", stack, NULL, prio, &h);\n"
                    "    configASSERT(ret == pdPASS);  /* C12.1 */"
                ),
                "reference": "prompts/error_handling.txt",
            })
        elif "pvPortMalloc" in msg or "malloc" in msg.lower():
            fixes.append({
                "line": line,
                "issue": msg,
                "fix_type": "check_malloc",
                "suggestion": "pvPortMalloc 返回值必须检查",
                "template": (
                    "    void *p = pvPortMalloc(size);\n"
                    "    if (p == NULL) {\n"
                    "        LOG_E(TAG, \"malloc %u failed\", size);\n"
                    "        goto cleanup;  /* 或 return error */\n"
                    "    }"
                ),
                "reference": "prompts/error_handling.txt",
            })
        elif "xQueueSend" in msg:
            fixes.append({
                "line": line,
                "issue": msg,
                "fix_type": "check_queue_send",
                "suggestion": "xQueueSend 失败时必须释放 payload",
                "template": (
                    "    if (xQueueSend(q, &evt, pdMS_TO_TICKS(50)) != pdTRUE) {\n"
                    "        vPortFree(evt.payload);  /* Queue 满，Model 释放 */\n"
                    "        LOG_W(TAG, \"Queue full, dropped\");\n"
                    "    }"
                ),
                "reference": "prompts/memory_ownership.txt",
            })
    return fixes


FIX_GENERATORS = {
    "cjson_leak": fix_cjson_leak,
    "cjson_ast": fix_cjson_leak,
    "queue_ownership": fix_queue_ownership,
    "queue_ast": fix_queue_ownership,
    "return_check": fix_return_check,
}


def format_report(fixes: list[dict], checker: str, filepath: str) -> str:
    lines = [
        "=" * 60,
        f"自动修复建议: {filepath}",
        f"Checker: {checker}",
        "=" * 60,
        "",
    ]
    if not fixes:
        lines.append("✅ 无需修复，或该 checker 暂不支持自动修复建议。")
        return "\n".join(lines)

    lines.append(f"共 {len(fixes)} 个修复建议：\n")
    for i, fix in enumerate(fixes):
        lines.append(f"--- 修复建议 {i+1} ---")
        lines.append(f"行号: L{fix.get('line', '?')}")
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
        "tool": "auto_fix_engine",
        "file": filepath,
        "checker": checker,
        "summary": {"fix_count": len(fixes)},
        "fixes": fixes,
    }


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="自动修复引擎")
    parser.add_argument("file", help="待修复的 .c 文件")
    parser.add_argument(
        "--checker", required=True,
        choices=list(CHECKER_SCRIPTS.keys()),
        help="Checker 类型",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 1

    # 运行 checker 获取 JSON
    result = run_checker_json(args.checker, args.file)
    if "error" in result:
        print(f"Checker 错误: {result['error']}", file=sys.stderr)
        return 1

    violations = result.get("violations", [])
    if not violations:
        violations = result.get("errors", [])  # 兼容不同 checker 格式

    # 生成修复建议
    gen = FIX_GENERATORS.get(args.checker)
    fixes = gen(violations, args.file) if gen else []

    if args.json:
        output_json(format_report_json(fixes, args.checker, args.file))
    else:
        print(format_report(fixes, args.checker, args.file))
    return 0


if __name__ == "__main__":
    sys.exit(main())