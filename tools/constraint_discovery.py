#!/usr/bin/env python3
"""
自动约束发现：扫描用户项目的高频违规模式，建议新增约束。

分析维度：
1. 已有 checker 未覆盖的 anti-pattern
2. 高频出现但无对应约束的代码模式
3. 平台特定的常见坑点

用法:
    python tools/constraint_discovery.py --dir ./src
    python tools/constraint_discovery.py --dir ./src --platform bk --json
    python tools/constraint_discovery.py --dir ./src --report proposal.md
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from checker_io import configure_stdout, output_json, safe_print

# ─── 已有约束覆盖的 checker 列表 ───
COVERED_CHECKERS = {
    "cjson_leak_checker": "C3",
    "isr_safety_checker": "C4",
    "lvgl_thread_checker": "C1",
    "queue_ownership_checker": "C2",
    "secret_scan_checker": "C9",
    "voice_sequence_checker": "C10",
    "logging_checker": "C14",
    "return_check_checker": "C12",
    "function_length_checker": "C11.5",
}

# ─── 待发现的 anti-pattern 规则 ───

@dataclass
class DiscoveryRule:
    """一条待发现的约束规则。"""
    rule_id: str
    name: str
    description: str
    severity: str  # P0/P1/P2
    pattern: re.Pattern
    category: str
    suggested_constraint: str
    example_fix: str
    frequency: int = 0
    files: list[str] = field(default_factory=list)


DISCOVERY_RULES: list[DiscoveryRule] = [
    # ── 栈缓冲区溢出 ──
    DiscoveryRule(
        rule_id="D1",
        name="sprintf 栈溢出风险",
        description="使用 sprintf/snprintf 时目标缓冲区大小未显式声明，或 snprintf 的 size 参数与目标不匹配",
        severity="P0",
        pattern=re.compile(
            r"\b(sprintf|snprintf)\s*\(\s*(\w+)\s*,"
        ),
        category="memory_safety",
        suggested_constraint="栈缓冲区安全",
        example_fix="改用 snprintf(buf, sizeof(buf), ...) 并检查返回值",
    ),
    DiscoveryRule(
        rule_id="D2",
        name="strcpy 无长度限制",
        description="使用 strcpy 而非 strncpy/strlcpy，存在缓冲区溢出风险",
        severity="P0",
        pattern=re.compile(
            r"\bstrcpy\s*\(\s*(\w+)\s*,"
        ),
        category="memory_safety",
        suggested_constraint="栈缓冲区安全",
        example_fix="改用 strncpy(dst, src, sizeof(dst)-1); dst[sizeof(dst)-1]='\\0';",
    ),
    # ── 竞态条件 ──
    DiscoveryRule(
        rule_id="D3",
        name="共享全局变量无保护",
        description="全局变量在多个任务/ISR 中被读写，但未使用 mutex/atomic 保护",
        severity="P1",
        pattern=re.compile(
            r"^(?:static\s+)?(?:volatile\s+)?(?:\w+\s+)+(\w+)\s*[=;].*$",
            re.MULTILINE,
        ),
        category="concurrency",
        suggested_constraint="共享变量保护",
        example_fix="用 xSemaphoreCreateMutex 保护或改用 _Atomic 类型",
    ),
    # ── 整数溢出 ──
    DiscoveryRule(
        rule_id="D4",
        name="malloc 大小计算溢出",
        description="malloc(n * size) 形式的分配，未检查乘法溢出",
        severity="P0",
        pattern=re.compile(
            r"(?:pvPort|c|m)alloc\s*\(\s*\w+\s*\*\s*\w+"
        ),
        category="memory_safety",
        suggested_constraint="整数溢出检查",
        example_fix="分配前检查 n > SIZE_MAX / size",
    ),
    # ── 资源泄漏 ──
    DiscoveryRule(
        rule_id="D5",
        name="xTaskCreate 句柄未保存",
        description="xTaskCreate 返回的句柄未保存，无法后续管理任务生命周期",
        severity="P1",
        pattern=re.compile(
            r"xTaskCreate\w*\s*\([^;]*?,\s*NULL\s*\)"
        ),
        category="resource_leak",
        suggested_constraint="任务生命周期管理",
        example_fix="保存句柄到 TaskHandle_t，退出时 vTaskDelete",
    ),
    DiscoveryRule(
        rule_id="D6",
        name="信号量/互斥锁创建后无销毁路径",
        description="xSemaphoreCreateMutex 等创建后无对应的 vSemaphoreDelete",
        severity="P1",
        pattern=re.compile(
            r"xSemaphoreCreate(?:Mutex|Binary|Counting)\s*\("
        ),
        category="resource_leak",
        suggested_constraint="同步原语生命周期",
        example_fix="在模块 deinit 中调用 vSemaphoreDelete",
    ),
    # ── 安全相关 ──
    DiscoveryRule(
        rule_id="D7",
        name="硬编码 IP 地址/URL",
        description="代码中硬编码了 IP 地址或 URL，应改为配置项",
        severity="P2",
        pattern=re.compile(
            r"""(?:https?://|wss?://)\d+\.\d+\.\d+\.\d+|(?:\d{1,3}\.){3}\d{1,3}(?!["'])"""
        ),
        category="configurable",
        suggested_constraint="配置外置",
        example_fix="改用 Kconfig 或 NVS 读取，附 config.example 占位",
    ),
    # ── FreeRTOS 特定 ──
    DiscoveryRule(
        rule_id="D8",
        name="xQueueReceive 使用 portMAX_DELAY",
        description="xQueueReceive 以 portMAX_DELAY 阻塞等待，可能导致任务永久挂起或 WDT 复位",
        severity="P1",
        pattern=re.compile(
            r"xQueueReceive\s*\([^;]*portMAX_DELAY\s*\)"
        ),
        category="freertos_specific",
        suggested_constraint="Queue 超时策略",
        example_fix="改用 pdMS_TO_TICKS(有限超时) + 循环重试",
    ),
    DiscoveryRule(
        rule_id="D9",
        name="vTaskDelay 在 ISR/回调中调用",
        description="在中断或回调上下文中调用 vTaskDelay",
        severity="P0",
        pattern=re.compile(
            r"vTaskDelay\s*\("
        ),
        category="freertos_specific",
        suggested_constraint="ISR 安全（已有 C4，需 checker 增强）",
        example_fix="从 ISR 中移除 vTaskDelay，用 xTaskNotifyFromISR 替代",
    ),
    # ── 平台特定 ──
    DiscoveryRule(
        rule_id="D10",
        name="ESP32: heap_caps_malloc 结果未检查",
        description="ESP32 的 heap_caps_malloc 在 PSRAM 分配失败时返回 NULL",
        severity="P0",
        pattern=re.compile(
            r"heap_caps_malloc\s*\([^;]*?;\s*(?!.*(?:if|assert|configASSERT).*NULL)"
        ),
        category="platform_specific",
        suggested_constraint="平台分配器返回值检查",
        example_fix="检查返回值，PSRAM 分配失败时 fallback 到 Internal SRAM",
    ),
    # ── 日志/调试 ──
    DiscoveryRule(
        rule_id="D11",
        name="TODO/FIXME/HACK 未清理",
        description="代码中残留 TODO/FIXME/HACK 注释，表明有未完成的工作",
        severity="P2",
        pattern=re.compile(
            r"//\s*(?:TODO|FIXME|HACK|XXX|TEMP)\b",
            re.IGNORECASE,
        ),
        category="code_quality",
        suggested_constraint="代码交付检查",
        example_fix="在提测/量产前清理所有 TODO/FIXME，或转为 Issue 追踪",
    ),
    # ── 内存对齐 ──
    DiscoveryRule(
        rule_id="D12",
        name="结构体未考虑对齐",
        description="包含多字节成员的结构体未使用 __attribute__((aligned)) 或 packed",
        severity="P2",
        pattern=re.compile(
            r"struct\s+\w+\s*\{[^}]*(?:uint16_t|uint32_t|int16_t|int32_t|float)[^}]*\}",
            re.DOTALL,
        ),
        category="memory_safety",
        suggested_constraint="结构体对齐",
        example_fix="DMA/网络结构体使用 __attribute__((packed)) 或手动填充",
    ),
    # ── 断言/防御 ──
    DiscoveryRule(
        rule_id="D13",
        name="函数入口无 NULL 检查",
        description="公开函数未检查指针参数是否为 NULL",
        severity="P1",
        pattern=re.compile(
            r"^(?:void|int|bool|esp_err_t|static\s+\w+)\s+(\w+)\s*\([^)]*\*\w+[^)]*\)\s*\{",
            re.MULTILINE,
        ),
        category="defensive_programming",
        suggested_constraint="防御性编程",
        example_fix="函数入口加 if (param == NULL) return ERR_INVALID_ARG;",
    ),
    # ── 编译器警告 ──
    DiscoveryRule(
        rule_id="D14",
        name="未使用变量/参数",
        description="变量或函数参数声明后未使用，可能是遗留代码或遗漏",
        severity="P2",
        pattern=re.compile(
            r"(?:void)\s*\(\s*\*\s*\w+\s*\)\s*\(\s*\)",
        ),
        category="code_quality",
        suggested_constraint="编译器警告零容忍",
        example_fix="(void)unused_var; 或删除未使用参数",
    ),
]


@dataclass
class DiscoveryResult:
    """约束发现结果。"""
    dir: str
    total_files: int = 0
    total_violations: int = 0
    discovered_rules: list[dict] = field(default_factory=list)
    covered_by_existing: dict[str, int] = field(default_factory=dict)
    proposals: list[dict] = field(default_factory=list)


def collect_c_files(dir_path: str) -> list[Path]:
    """收集目录下所有 C 源文件。"""
    root = Path(dir_path)
    if not root.is_dir():
        return []
    files = sorted(root.rglob("*.c"))
    files.extend(sorted(root.rglob("*.h")))
    return [f for f in files if not f.name.startswith("bad_")]


def analyze_file(path: Path) -> dict[str, list[tuple[int, str]]]:
    """分析单个文件，返回每条规则的命中列表。"""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    results: dict[str, list[tuple[int, str]]] = {}
    lines = content.splitlines()

    for rule in DISCOVERY_RULES:
        matches = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 跳过注释
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            if rule.pattern.search(line):
                matches.append((i + 1, stripped[:120]))
        if matches:
            results[rule.rule_id] = matches

    return results


def generate_proposals(
    rule_hits: dict[str, int],
    file_hits: dict[str, list[str]],
) -> list[dict]:
    """根据命中频率生成约束提案。"""
    proposals = []

    # 按命中次数排序
    sorted_rules = sorted(
        [(rid, count) for rid, count in rule_hits.items() if count >= 3],
        key=lambda x: -x[1],
    )

    for rid, count in sorted_rules:
        rule = next((r for r in DISCOVERY_RULES if r.rule_id == rid), None)
        if not rule:
            continue

        proposals.append({
            "proposed_id": f"C{21 + len(proposals)}",
            "rule_id": rid,
            "name": rule.name,
            "description": rule.description,
            "severity": rule.severity,
            "category": rule.category,
            "frequency": count,
            "affected_files": len(file_hits.get(rid, [])),
            "suggested_constraint": rule.suggested_constraint,
            "example_fix": rule.example_fix,
            "priority": "高" if count >= 10 and rule.severity == "P0" else
                       "中" if count >= 5 else "低",
        })

    return proposals


def format_report_text(result: DiscoveryResult) -> str:
    """格式化文本报告。"""
    lines = [
        "=" * 60,
        "自动约束发现报告",
        "=" * 60,
        f"扫描目录: {result.dir}",
        f"扫描文件: {result.total_files}",
        f"总命中: {result.total_violations}",
        "",
    ]

    # 已有约束覆盖
    if result.covered_by_existing:
        lines.append("已有约束覆盖的 checker:")
        for checker, constraint in sorted(COVERED_CHECKERS.items()):
            lines.append(f"  ✅ {checker} → {constraint}")
        lines.append("")

    # 新发现的 anti-pattern
    if result.discovered_rules:
        lines.append("─── 新发现的 anti-pattern（无对应约束）───")
        lines.append("")
        for dr in sorted(result.discovered_rules, key=lambda x: -x["frequency"]):
            icon = "🔴" if dr["severity"] == "P0" else "🟡" if dr["severity"] == "P1" else "⚪"
            lines.append(f"{icon} {dr['rule_id']}: {dr['name']}")
            lines.append(f"   频率: {dr['frequency']} 次 / {dr['affected_files']} 个文件")
            lines.append(f"   严重度: {dr['severity']}")
            lines.append(f"   分类: {dr['category']}")
            lines.append(f"   描述: {dr['description']}")
            lines.append(f"   建议约束: {dr['suggested_constraint']}")
            lines.append(f"   修复建议: {dr['example_fix']}")
            lines.append("")

    # 约束提案
    if result.proposals:
        lines.append("─── 约束新增提案 ───")
        lines.append("")
        for p in result.proposals:
            lines.append(f"[{p['priority']}] {p['proposed_id']} — {p['name']}")
            lines.append(f"  频率: {p['frequency']} 次, 严重度: {p['severity']}")
            lines.append(f"  建议: {p['suggested_constraint']}")
            lines.append("")
    else:
        lines.append("─── 未发现高频 anti-pattern（阈值 ≥3 次）───")
        lines.append("当前代码质量良好，无新增约束建议。")
        lines.append("")

    lines.append("ℹ️  本工具为启发式辅助，结果需人工审核确认。")
    return "\n".join(lines)


def format_report_json(result: DiscoveryResult) -> dict:
    """格式化 JSON 报告。"""
    return {
        "tool": "constraint_discovery",
        "dir": result.dir,
        "summary": {
            "total_files": result.total_files,
            "total_violations": result.total_violations,
            "discovered_rules": len(result.discovered_rules),
            "proposals": len(result.proposals),
        },
        "discovered_rules": result.discovered_rules,
        "proposals": result.proposals,
        "covered_checkers": COVERED_CHECKERS,
    }


def format_markdown_proposal(result: DiscoveryResult) -> str:
    """生成 Markdown 格式的约束提案文档。"""
    lines = [
        "# 约束新增提案",
        "",
        f"> 自动生成于 {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 扫描目录: {result.dir} ({result.total_files} 文件)",
        "",
        "---",
        "",
    ]

    if not result.proposals:
        lines.append("未发现需要新增的约束。当前代码质量良好。")
        return "\n".join(lines)

    lines.append("## 提案列表")
    lines.append("")

    for p in result.proposals:
        lines.extend([
            f"### {p['proposed_id']} — {p['name']}",
            "",
            f"| 字段 | 值 |",
            f"|------|-----|",
            f"| 频率 | {p['frequency']} 次 / {p['affected_files']} 个文件 |",
            f"| 严重度 | {p['severity']} |",
            f"| 分类 | {p['category']} |",
            f"| 优先级 | {p['priority']} |",
            "",
            f"**描述:** {p['description']}",
            "",
            f"**建议约束:** {p['suggested_constraint']}",
            "",
            f"**修复建议:** {p['example_fix']}",
            "",
            "---",
            "",
        ])

    return "\n".join(lines)


def run_self_test() -> int:
    """自测：验证约束发现规则"""
    import tempfile
    import os

    passed = 0
    failed = 0

    # Test 1: Create a temp file with known anti-patterns
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False, encoding='utf-8') as f:
        f.write("""
#include <stdio.h>
#include <string.h>

void bad_function(void) {
    char buf[64];
    sprintf(buf, "hello world %d", 42);  // D1: sprintf risk

    char *p = malloc(100);
    // D4: malloc without free check
    memcpy(p, "data", 4);

    // D10: hardcoded IP
    connect("192.168.1.100", 8080);
}
""")
        tmpfile = f.name

    try:
        results = analyze_file(Path(tmpfile))
        total_hits = sum(len(v) for v in results.values())
        assert total_hits > 0, f"Should find violations, got {total_hits}"
        print(f"[PASS] discovery found {total_hits} violations in test file")
        passed += 1
    except Exception as e:
        print(f"[FAIL] discovery test: {e}")
        failed += 1
    finally:
        os.unlink(tmpfile)

    # Test 2: Check rules are defined
    assert len(DISCOVERY_RULES) >= 10, f"Should have >=10 rules, got {len(DISCOVERY_RULES)}"
    print(f"[PASS] {len(DISCOVERY_RULES)} discovery rules defined")
    passed += 1

    # Test 3: Check covered checkers
    assert len(COVERED_CHECKERS) >= 5, f"Should have >=5 covered checkers"
    print(f"[PASS] {len(COVERED_CHECKERS)} covered checkers")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="自动约束发现：扫描用户项目的高频违规模式，建议新增约束"
    )
    parser.add_argument("--dir", "-d", help="扫描目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--report", help="输出 Markdown 提案到文件")
    parser.add_argument("--threshold", type=int, default=3, help="最低命中次数（默认 3）")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.dir:
        parser.print_help()
        return 1

    files = collect_c_files(args.dir)
    if not files:
        print(f"未找到 .c/.h 文件: {args.dir}", file=sys.stderr)
        return 1

    # 扫描所有文件
    rule_hits: dict[str, int] = Counter()
    file_hits: dict[str, list[str]] = {}
    discovered_rules = []

    for f in files:
        results = analyze_file(f)
        for rid, matches in results.items():
            rule_hits[rid] += len(matches)
            file_hits.setdefault(rid, []).append(str(f))

    # 生成发现结果
    for rid, count in rule_hits.items():
        rule = next((r for r in DISCOVERY_RULES if r.rule_id == rid), None)
        if not rule:
            continue
        discovered_rules.append({
            "rule_id": rid,
            "name": rule.name,
            "description": rule.description,
            "severity": rule.severity,
            "category": rule.category,
            "frequency": count,
            "affected_files": len(file_hits.get(rid, [])),
            "suggested_constraint": rule.suggested_constraint,
            "example_fix": rule.example_fix,
        })

    # 生成提案
    proposals = generate_proposals(rule_hits, file_hits)

    result = DiscoveryResult(
        dir=args.dir,
        total_files=len(files),
        total_violations=sum(rule_hits.values()),
        discovered_rules=discovered_rules,
        covered_by_existing=COVERED_CHECKERS,
        proposals=proposals,
    )

    if args.json:
        output_json(format_report_json(result))
    else:
        safe_print(format_report_text(result))

    # 输出 Markdown 提案
    if args.report:
        md = format_markdown_proposal(result)
        Path(args.report).write_text(md, encoding="utf-8")
        print(f"\n提案已写入: {args.report}")

    return 0


if __name__ == "__main__":
    sys.exit(main())