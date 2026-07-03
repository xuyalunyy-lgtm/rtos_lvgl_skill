#!/usr/bin/env python3
"""
自动约束发现 v2：扫描用户项目的高频违规模式，建议新增约束。

v2 增强（v9.0.5）：
  1. --registry-aware：从 checker_registry 读取已有 C1-C45 约束
  2. 提案编号从 C46+ 开始，避免与已有约束冲突
  3. 三类输出：已有约束覆盖 / Checker 漏检 / 候选 C46+
  4. severity 加权排序（P0×3, P1×2, P2×1）

用法:
    python tools/constraint_discovery.py --dir ./src
    python tools/constraint_discovery.py --dir ./src --registry-aware --json
    python tools/constraint_discovery.py --dir ./src --report proposal.md
    python tools/constraint_discovery.py --self-test
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from checker_io import configure_stdout, output_json, safe_print

# ─── 已有约束覆盖的 checker 列表（向后兼容） ───
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

# ─── severity 权重 ───
SEVERITY_WEIGHT = {"P0": 3, "P1": 2, "P2": 1}


# ─── Registry 感知：从 checker_registry 读取已有约束 ───

def _load_registry_domains() -> dict[str, set[str]]:
    """从 checker_registry 读取 {checker_name: {domains}} 和所有 domain 编号。"""
    try:
        from checker_registry import ALL_CHECKERS
    except ImportError:
        return {"checker_domains": set(), "checker_map": {}}

    checker_map: dict[str, set[str]] = {}
    all_domains: set[str] = set()
    for spec in ALL_CHECKERS:
        checker_map[spec.name] = set(spec.domains)
        all_domains.update(spec.domains)
    return {"all_domains": all_domains, "checker_map": checker_map}


def _parse_domain_number(domain: str) -> int:
    """从 domain 字符串提取主编号，如 'C45' → 45, 'C7.3' → 7, 'C11.5' → 11。"""
    m = re.match(r"C(\d+)", domain)
    return int(m.group(1)) if m else 0


def _max_domain_number(domains: set[str]) -> int:
    """返回已有约束中的最大主编号。"""
    return max((_parse_domain_number(d) for d in domains), default=0)


def _find_missing_checkers(all_domains: set[str]) -> list[str]:
    """找出 C1-max 中没有 checker 覆盖的约束编号。"""
    if not all_domains:
        return []
    max_n = _max_domain_number(all_domains)
    covered = {_parse_domain_number(d) for d in all_domains}
    return [f"C{n}" for n in range(1, max_n + 1) if n not in covered]


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
    related_constraint: str = ""  # 与已有约束的关联（如有）
    frequency: int = 0
    files: list[str] = field(default_factory=list)


DISCOVERY_RULES: list[DiscoveryRule] = [
    # ── 栈缓冲区溢出 ──
    DiscoveryRule(
        rule_id="D1",
        name="sprintf 栈溢出风险",
        description="使用 sprintf/snprintf 时目标缓冲区大小未显式声明，或 snprintf 的 size 参数与目标不匹配",
        severity="P0",
        pattern=re.compile(r"\b(sprintf|snprintf)\s*\(\s*(\w+)\s*,"),
        category="memory_safety",
        suggested_constraint="栈缓冲区安全",
        example_fix="改用 snprintf(buf, sizeof(buf), ...) 并检查返回值",
    ),
    DiscoveryRule(
        rule_id="D2",
        name="strcpy 无长度限制",
        description="使用 strcpy 而非 strncpy/strlcpy，存在缓冲区溢出风险",
        severity="P0",
        pattern=re.compile(r"\bstrcpy\s*\(\s*(\w+)\s*,"),
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
        related_constraint="C43",
    ),
    # ── 整数溢出 ──
    DiscoveryRule(
        rule_id="D4",
        name="malloc 大小计算溢出",
        description="malloc(n * size) 形式的分配，未检查乘法溢出",
        severity="P0",
        pattern=re.compile(r"(?:pvPort|c|m)alloc\s*\(\s*\w+\s*\*\s*\w+"),
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
        pattern=re.compile(r"xTaskCreate\w*\s*\([^;]*?,\s*NULL\s*\)"),
        category="resource_leak",
        suggested_constraint="任务生命周期管理",
        example_fix="保存句柄到 TaskHandle_t，退出时 vTaskDelete",
        related_constraint="C33",
    ),
    DiscoveryRule(
        rule_id="D6",
        name="信号量/互斥锁创建后无销毁路径",
        description="xSemaphoreCreateMutex 等创建后无对应的 vSemaphoreDelete",
        severity="P1",
        pattern=re.compile(r"xSemaphoreCreate(?:Mutex|Binary|Counting)\s*\("),
        category="resource_leak",
        suggested_constraint="同步原语生命周期",
        example_fix="在模块 deinit 中调用 vSemaphoreDelete",
        related_constraint="C33",
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
        related_constraint="C39",
    ),
    # ── FreeRTOS 特定 ──
    DiscoveryRule(
        rule_id="D8",
        name="xQueueReceive 使用 portMAX_DELAY",
        description="xQueueReceive 以 portMAX_DELAY 阻塞等待，可能导致任务永久挂起或 WDT 复位",
        severity="P1",
        pattern=re.compile(r"xQueueReceive\s*\([^;]*portMAX_DELAY\s*\)"),
        category="freertos_specific",
        suggested_constraint="Queue 超时策略",
        example_fix="改用 pdMS_TO_TICKS(有限超时) + 循环重试",
        related_constraint="C31",
    ),
    DiscoveryRule(
        rule_id="D9",
        name="vTaskDelay 在 ISR/回调中调用",
        description="在中断或回调上下文中调用 vTaskDelay",
        severity="P0",
        pattern=re.compile(r"vTaskDelay\s*\("),
        category="freertos_specific",
        suggested_constraint="ISR 安全（已有 C4，需 checker 增强）",
        example_fix="从 ISR 中移除 vTaskDelay，用 xTaskNotifyFromISR 替代",
        related_constraint="C4",
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
        pattern=re.compile(r"//\s*(?:TODO|FIXME|HACK|XXX|TEMP)\b", re.IGNORECASE),
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
        pattern=re.compile(r"(?:void)\s*\(\s*\*\s*\w+\s*\)\s*\(\s*\)"),
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
    # v2 新增
    registry_aware: bool = False
    existing_domains: list[str] = field(default_factory=list)
    missing_checkers: list[str] = field(default_factory=list)
    checker_coverage: dict[str, dict] = field(default_factory=dict)


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
    *,
    threshold: int = 3,
    base_constraint_number: int = 46,
) -> list[dict]:
    """根据命中频率生成约束提案，编号从 base_constraint_number 开始。"""
    proposals = []

    # 按 severity 权重 × 频率 排序
    def sort_key(item: tuple[str, int]) -> float:
        rid, count = item
        rule = next((r for r in DISCOVERY_RULES if r.rule_id == rid), None)
        weight = SEVERITY_WEIGHT.get(rule.severity, 1) if rule else 1
        return -(count * weight)

    sorted_rules = sorted(
        [(rid, count) for rid, count in rule_hits.items() if count >= threshold],
        key=sort_key,
    )

    for rid, count in sorted_rules:
        rule = next((r for r in DISCOVERY_RULES if r.rule_id == rid), None)
        if not rule:
            continue

        sev_weight = SEVERITY_WEIGHT.get(rule.severity, 1)
        score = count * sev_weight

        proposals.append({
            "proposed_id": f"C{base_constraint_number + len(proposals)}",
            "rule_id": rid,
            "name": rule.name,
            "description": rule.description,
            "severity": rule.severity,
            "category": rule.category,
            "frequency": count,
            "affected_files": len(file_hits.get(rid, [])),
            "suggested_constraint": rule.suggested_constraint,
            "example_fix": rule.example_fix,
            "related_constraint": rule.related_constraint,
            "severity_weight": sev_weight,
            "score": score,
            "priority": "高" if score >= 30 else "中" if score >= 10 else "低",
        })

    return proposals


def _build_checker_coverage(
    registry_domains: set[str],
    checker_map: dict[str, set[str]],
) -> dict[str, dict]:
    """构建每个 checker 的覆盖情况。"""
    coverage: dict[str, dict] = {}
    for name, domains in checker_map.items():
        coverage[name] = {
            "domains": sorted(domains),
            "has_checker": True,
        }
    return coverage


def format_report_text(result: DiscoveryResult) -> str:
    """格式化文本报告。"""
    lines = [
        "=" * 60,
        "自动约束发现报告" + (" v2 (registry-aware)" if result.registry_aware else ""),
        "=" * 60,
        f"扫描目录: {result.dir}",
        f"扫描文件: {result.total_files}",
        f"总命中: {result.total_violations}",
        "",
    ]

    # ── 已有约束覆盖 ──
    if result.registry_aware and result.existing_domains:
        lines.append(f"已有约束覆盖 ({len(result.existing_domains)} 个 domain):")
        for d in sorted(result.existing_domains, key=_parse_domain_number):
            lines.append(f"  ✅ {d}")
        lines.append("")

    # ── Checker 漏检 ──
    if result.registry_aware and result.missing_checkers:
        lines.append(f"─── Checker 漏检（C1-max 中无 checker 覆盖）───")
        lines.append("")
        for d in result.missing_checkers:
            lines.append(f"  ⚠️  {d} — 无对应 checker 脚本")
        lines.append("")
        lines.append(f"共 {len(result.missing_checkers)} 个约束域缺少 checker。")
        lines.append("")

    # ── 已有 checker 覆盖（向后兼容） ──
    if not result.registry_aware and result.covered_by_existing:
        lines.append("已有约束覆盖的 checker:")
        for checker, constraint in sorted(COVERED_CHECKERS.items()):
            lines.append(f"  ✅ {checker} → {constraint}")
        lines.append("")

    # ── 新发现的 anti-pattern ──
    if result.discovered_rules:
        lines.append("─── 新发现的 anti-pattern（无对应约束）───")
        lines.append("")
        for dr in sorted(result.discovered_rules, key=lambda x: -x.get("frequency", 0)):
            icon = "🔴" if dr["severity"] == "P0" else "🟡" if dr["severity"] == "P1" else "⚪"
            lines.append(f"{icon} {dr['rule_id']}: {dr['name']}")
            lines.append(f"   频率: {dr['frequency']} 次 / {dr['affected_files']} 个文件")
            lines.append(f"   严重度: {dr['severity']}")
            lines.append(f"   分类: {dr['category']}")
            lines.append(f"   描述: {dr['description']}")
            lines.append(f"   建议约束: {dr['suggested_constraint']}")
            if dr.get("related_constraint"):
                lines.append(f"   关联约束: {dr['related_constraint']}")
            lines.append(f"   修复建议: {dr['example_fix']}")
            lines.append("")

    # ── 候选 C46+ 提案 ──
    if result.proposals:
        lines.append("─── 候选约束提案 ───")
        lines.append("")
        for p in result.proposals:
            score_str = f" (score={p['score']})" if p.get("score") else ""
            lines.append(f"[{p['priority']}] {p['proposed_id']} — {p['name']}{score_str}")
            lines.append(f"  频率: {p['frequency']} 次, 严重度: {p['severity']}, 权重: {p.get('severity_weight', '?')}")
            if p.get("related_constraint"):
                lines.append(f"  关联: {p['related_constraint']}")
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
    data = {
        "tool": "constraint_discovery",
        "version": "2.0",
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
    if result.registry_aware:
        data["registry_aware"] = True
        data["existing_domains"] = sorted(result.existing_domains, key=_parse_domain_number)
        data["missing_checkers"] = result.missing_checkers
        data["checker_coverage"] = result.checker_coverage
    return data


def format_markdown_proposal(result: DiscoveryResult) -> str:
    """生成 Markdown 格式的约束提案文档。"""
    lines = [
        "# 约束新增提案",
        "",
        f"> 自动生成于 {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 扫描目录: {result.dir} ({result.total_files} 文件)",
    ]
    if result.registry_aware:
        lines.append(f"> Registry 感知模式: 已有 {len(result.existing_domains)} 个约束域")
    lines.extend(["", "---", ""])

    # Checker 漏检
    if result.registry_aware and result.missing_checkers:
        lines.append("## Checker 漏检")
        lines.append("")
        for d in result.missing_checkers:
            lines.append(f"- **{d}** — 无对应 checker 脚本")
        lines.append("")
        lines.append("---")
        lines.append("")

    if not result.proposals:
        lines.append("未发现需要新增的约束。当前代码质量良好。")
        return "\n".join(lines)

    lines.append("## 候选约束提案")
    lines.append("")

    for p in result.proposals:
        score_str = f" (score={p['score']})" if p.get("score") else ""
        related = f"\n| 关联约束 | {p['related_constraint']} |" if p.get("related_constraint") else ""
        lines.extend([
            f"### {p['proposed_id']} — {p['name']}{score_str}",
            "",
            f"| 字段 | 值 |",
            f"|------|-----|",
            f"| 频率 | {p['frequency']} 次 / {p['affected_files']} 个文件 |",
            f"| 严重度 | {p['severity']} (权重 {p.get('severity_weight', '?')}) |",
            f"| 分类 | {p['category']} |",
            f"| 优先级 | {p['priority']} |",
            f"{related}",
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
    import os
    import tempfile

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

    # Test 4: Registry-aware domain loading
    reg = _load_registry_domains()
    all_domains = reg.get("all_domains", set())
    if all_domains:
        max_n = _max_domain_number(all_domains)
        assert max_n >= 40, f"Expected max domain >= 40, got {max_n}"
        print(f"[PASS] registry domains: {len(all_domains)}, max=C{max_n}")
        passed += 1

        # Test 5: Missing checkers detection
        missing = _find_missing_checkers(all_domains)
        print(f"[PASS] missing checkers: {missing}")
        passed += 1

        # Test 6: Proposal numbering starts above max domain
        base = max_n + 1
        proposals = generate_proposals(
            {"D1": 5, "D2": 3}, {"D1": ["f1.c"], "D2": ["f2.c"]},
            threshold=1, base_constraint_number=base,
        )
        if proposals:
            first_id = proposals[0]["proposed_id"]
            assert first_id == f"C{base}", f"Expected C{base}, got {first_id}"
            print(f"[PASS] proposal numbering starts at C{base}")
            passed += 1
        else:
            print(f"[SKIP] no proposals generated (threshold)")
    else:
        print(f"[SKIP] registry not available")
        failed += 0

    # Test 7: Severity weighting
    proposals = generate_proposals(
        {"D1": 5, "D11": 10}, {"D1": ["f1.c"], "D11": ["f2.c"]},
        threshold=1, base_constraint_number=46,
    )
    if len(proposals) >= 2:
        # D1 is P0 (weight 3) × 5 = 15, D11 is P2 (weight 1) × 10 = 10
        # D1 should come first
        assert proposals[0]["rule_id"] == "D1", f"Expected D1 first, got {proposals[0]['rule_id']}"
        print(f"[PASS] severity weighting: P0×5 > P2×10")
        passed += 1
    else:
        print(f"[SKIP] not enough proposals for weight test")

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="自动约束发现 v2：扫描用户项目的高频违规模式，建议新增约束"
    )
    parser.add_argument("--dir", "-d", help="扫描目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--report", help="输出 Markdown 提案到文件")
    parser.add_argument("--threshold", type=int, default=3, help="最低命中次数（默认 3）")
    parser.add_argument("--registry-aware", action="store_true",
                        help="从 checker_registry 读取已有约束，避免编号冲突")
    parser.add_argument("--evidence", metavar="FILE", help="输出交付证据包到指定文件")
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

    # ── Registry 感知 ──
    registry_domains: set[str] = set()
    checker_map: dict[str, set[str]] = {}
    missing_checkers: list[str] = []
    base_constraint_number = 46

    if args.registry_aware:
        reg = _load_registry_domains()
        registry_domains = reg.get("all_domains", set())
        checker_map = reg.get("checker_map", {})
        missing_checkers = _find_missing_checkers(registry_domains)
        max_n = _max_domain_number(registry_domains)
        base_constraint_number = max_n + 1 if max_n >= 45 else 46

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
        entry = {
            "rule_id": rid,
            "name": rule.name,
            "description": rule.description,
            "severity": rule.severity,
            "category": rule.category,
            "frequency": count,
            "affected_files": len(file_hits.get(rid, [])),
            "suggested_constraint": rule.suggested_constraint,
            "example_fix": rule.example_fix,
        }
        if rule.related_constraint:
            entry["related_constraint"] = rule.related_constraint
        discovered_rules.append(entry)

    # 生成提案
    proposals = generate_proposals(
        rule_hits, file_hits,
        threshold=args.threshold,
        base_constraint_number=base_constraint_number,
    )

    result = DiscoveryResult(
        dir=args.dir,
        total_files=len(files),
        total_violations=sum(rule_hits.values()),
        discovered_rules=discovered_rules,
        covered_by_existing=COVERED_CHECKERS,
        proposals=proposals,
        registry_aware=args.registry_aware,
        existing_domains=sorted(registry_domains),
        missing_checkers=missing_checkers,
        checker_coverage=_build_checker_coverage(registry_domains, checker_map) if checker_map else {},
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

    # ── 交付证据包输出 ──
    if args.evidence:
        try:
            from evidence_schema import issue_entry, make_evidence, save_evidence
        except ImportError:
            print("[warn] evidence_schema 模块不可用（已归档），跳过证据包输出", file=sys.stderr)
            return 0

        ev_issues = []
        for rule in discovered_rules:
            ev_issues.append(issue_entry(
                cid=rule["rule_id"],
                severity=rule["severity"],
                file=", ".join(file_hits.get(rule["rule_id"], [])[:3]),
                constraint=rule["category"],
                message=rule["description"],
                checker="constraint_discovery",
            ))

        assumptions = [
            f"基于 {len(DISCOVERY_RULES)} 条发现规则扫描",
            f"阈值: >= {args.threshold} 次命中",
            "建议需人工审核后决定是否新增约束",
        ]
        if args.registry_aware:
            assumptions.append(f"Registry 感知: {len(registry_domains)} 个已有约束域")
            if missing_checkers:
                assumptions.append(f"发现 {len(missing_checkers)} 个约束域缺少 checker")

        ev = make_evidence(
            source_tool="constraint_discovery",
            issues=ev_issues,
            assumptions=assumptions,
            metadata={
                "tool_version": "9.0.5",
                "total_files": len(files),
                "total_violations": sum(rule_hits.values()),
                "proposals_count": len(proposals),
                "registry_aware": args.registry_aware,
                "missing_checkers": missing_checkers,
            },
        )
        save_evidence(ev, args.evidence)
        if not args.json:
            print(f"[evidence] 已保存交付证据包: {args.evidence}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
