#!/usr/bin/env python3
"""
约束推理引擎 v2 — 从知识图谱自动推理约束影响。

v2 增强：
  1. 冲突自动检测带严重度分级（P0/P1/P2）
  2. 修复链拓扑排序带优先级标注
  3. Mermaid 可视化带冲突高亮
  4. JSON 结构化输出支持 CI 集成
  5. fixture 自测支持

用法:
    python tools/constraint_inference.py --changed "app_audio.c:queue_depth"
    python tools/constraint_inference.py --changed-files src/audio.c src/network.c
    python tools/constraint_inference.py --constraints C21 C25
    python tools/constraint_inference.py --graph
    python tools/constraint_inference.py --json
    python tools/constraint_inference.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


# ============================================================================
# 约束知识图谱（从 constraint_graph.md 提取的依赖/冲突/联动关系）
# ============================================================================

# 依赖关系：A → B（满足 A 是满足 B 的前提）
DEPENDENCIES = {
    "C2": ["C3"],
    "C3": ["C7"],
    "C6": ["C7"],
    "C8": ["C10", "C20"],
    "C4": ["C10", "C25", "C26", "C28", "C34"],
    "C9": ["C19", "C22"],
    "C1": ["C8", "C23"],
    "C18": ["C4"],
    "C15": ["C1", "C25"],
    "C16": ["C8"],
    "C12": ["C3", "C24"],
    "C13": ["C20", "C21"],
    "C14": ["C9"],
    "C19": ["C21", "C22"],
    "C21": ["C20", "C23"],
    "C22": ["C20", "C31"],
    "C23": ["C7", "C25", "C26", "C28"],
    "C24": ["C4", "C10"],
    "C25": ["C7", "C26", "C27", "C28"],
    "C26": ["C7", "C27", "C28"],
    "C27": ["C7"],
    "C28": ["C7", "C27"],
    "C29": ["C30", "C31", "C33"],
    "C30": ["C15", "C7", "C32"],
    "C31": ["C8", "C20", "C34"],
    "C32": ["C14", "C7"],
    "C33": ["C12", "C24", "C7"],
    "C34": ["C4", "C25", "C26", "C27", "C28"],
    "C35": ["C31", "C32", "C40"],
    "C36": ["C2", "C7", "C28"],
    "C37": ["C30", "C31", "C38"],
    "C38": ["C20", "C24", "C32"],
    "C39": ["C6", "C9", "C40"],
    "C40": ["C14", "C41"],
    "C41": ["C30", "C31"],
    "C42": ["C4", "C7", "C18", "C28"],
    "C43": ["C15", "C31", "C34", "C37", "C4"],
    "C44": ["C4", "C34", "C35", "C43"],
    "C45": ["C18", "C31", "C32", "C34", "C42"],
}

# 冲突关系：A ↔ B（同时满足需要权衡）+ 严重度
CONFLICTS = [
    ("C8.6", "C8.2", "init 需同步时间 vs TLS 前须 SNTP", "P1"),
    ("C1.6", "C1.5", "LVGL 锁序 vs SDK 锁序", "P1"),
    ("C7.5", "C7", "WSS 栈 >=4096 vs RAM 受限", "P0"),
    ("C4.5", "C15.1", "音频优先级 > LVGL vs 相邻差 >=2", "P1"),
    ("C14.1", "C4.3", "需要日志 vs ISR 禁日志", "P1"),
    ("C5.1", "C6", "测试宏 vs 量产关闭", "P2"),
    ("C9.1", "C9", "密钥不入库 vs 调试便利", "P1"),
    ("C17.1", "C17", "跨核须 IPC vs 延迟需求", "P1"),
    ("C11.5", "C12.4", "函数 <=80 行 vs goto cleanup", "P2"),
    ("C16.1", "C16", "timer 回调禁阻塞 vs 业务逻辑", "P1"),
    ("C21.4", "C20.5", "睡眠前关 WiFi vs 网络须降级", "P0"),
    ("C21.3", "C4.5", "Tickless Idle vs 音频优先级", "P1"),
    ("C25.1", "C23.3", "audio clock master vs 显示帧率", "P1"),
    ("C25.3", "C7.13", "有界 video queue vs 固定块池", "P1"),
    ("C26.1", "C25.4", "格式一致 vs 热路径禁分配", "P1"),
    ("C27.2", "C25.3", "jitter buffer 水位 vs 低延迟", "P1"),
    ("C28.1", "C7.10", "DMA-capable vs 外部 RAM 优先", "P0"),
    ("C31.1", "C31.4", "有限 timeout vs daemon 永久等待", "P1"),
    ("C32.5", "C34.2", "现场 dump vs 热路径禁日志", "P1"),
    ("C34.2", "C7.13", "hot path 禁分配 vs 固定块池", "P1"),
    ("C35.1", "C40.1", "关键路径预算 vs 复现命令简洁", "P2"),
    ("C43.1", "C34.1", "锁预算 vs 热路径实时性", "P0"),
    ("C44.1", "C4", "关中断预算 vs ISR 实时性", "P0"),
    ("C22.2", "C38.2", "OTA mark_valid vs 故障恢复", "P1"),
    ("C22.5", "C35.1", "OTA 超时重试 vs 启动预算", "P1"),
]

# 联动关系：改 A 时必须检查 B
LINKAGES = {
    "C1": ["C15", "C8"],
    "C2": ["C3", "C12"],
    "C4": ["C18", "C10"],
    "C7": ["C6", "C12", "C14", "C19", "C28"],
    "C8": ["C20", "C10"],
    "C9": ["C14", "C19"],
    "C10": ["C4", "C8", "C13"],
    "C13": ["C20", "C16"],
    "C17": ["C1", "C4"],
    "C18": ["C4"],
    "C19": ["C21", "C22"],
    "C21": ["C19", "C20", "C13"],
    "C22": ["C19", "C9", "C20", "C31", "C38"],
    "C23": ["C1", "C7", "C21"],
    "C24": ["C4", "C10", "C21"],
    "C25": ["C4", "C23", "C15", "C7"],
    "C26": ["C4", "C25", "C23", "C7"],
    "C27": ["C25", "C26", "C20", "C7"],
    "C28": ["C4", "C7", "C23", "C25", "C26"],
    "C29": ["C30", "C31", "C33", "C2"],
    "C30": ["C15", "C7", "C31", "C32"],
    "C31": ["C8", "C20", "C16", "C34"],
    "C32": ["C14", "C7", "C30", "C31"],
    "C33": ["C12", "C24", "C7", "C29"],
    "C34": ["C4", "C14", "C25", "C26", "C27", "C28", "C31"],
    "C35": ["C31", "C32", "C40"],
    "C36": ["C2", "C7", "C28", "C37"],
    "C37": ["C30", "C31", "C38", "C32"],
    "C38": ["C20", "C24", "C32", "C33"],
    "C39": ["C6", "C9", "C40"],
    "C40": ["C14", "C41"],
    "C41": ["C30", "C31"],
    "C42": ["C4", "C7", "C18", "C28"],
    "C43": ["C15", "C31", "C34", "C37", "C4"],
    "C44": ["C4", "C34", "C35", "C43"],
    "C45": ["C18", "C31", "C32", "C34", "C42"],
}

# 约束域名称映射
CONSTRAINT_NAMES = {
    "C1": "LVGL 线程安全",
    "C2": "Queue 所有权",
    "C3": "cJSON 防泄漏",
    "C4": "ISR/DMA 安全",
    "C5": "测试宏",
    "C6": "SDK 裁剪",
    "C7": "内存优化",
    "C8": "启动顺序/WDT",
    "C9": "密钥安全",
    "C10": "语音/ASR",
    "C11": "编码规范",
    "C12": "错误处理",
    "C13": "状态机",
    "C14": "日志规范",
    "C15": "任务优先级",
    "C16": "定时器管理",
    "C17": "多核 IPC",
    "C18": "外设驱动",
    "C19": "Flash/NVS",
    "C20": "网络韧性",
    "C21": "低功耗",
    "C22": "OTA 安全",
    "C23": "显示驱动",
    "C24": "外设关闭",
    "C25": "音视频管线",
    "C26": "编解码格式",
    "C27": "时钟漂移/Jitter",
    "C28": "DMA/cache buffer",
    "C29": "模块契约",
    "C30": "任务拓扑",
    "C31": "超时预算",
    "C32": "可观测性",
    "C33": "生命周期对称",
    "C34": "热路径禁区",
    "C35": "关键路径预算",
    "C36": "数据拷贝预算",
    "C37": "背压降级",
    "C38": "故障恢复",
    "C39": "配置矩阵",
    "C40": "一键复现",
    "C41": "回归样本",
    "C42": "板级资源",
    "C43": "锁预算",
    "C44": "临界区预算",
    "C45": "传感器契约",
}

# 文件路径 → 约束域映射
FILE_TO_CONSTRAINTS = {
    "audio": ["C4", "C10", "C25", "C26", "C27", "C28"],
    "voice": ["C10", "C25", "C26"],
    "wss": ["C8", "C20", "C31"],
    "network": ["C8", "C20", "C31"],
    "wifi": ["C20", "C21"],
    "lvgl": ["C1", "C23"],
    "display": ["C1", "C23"],
    "lcd": ["C23"],
    "cjson": ["C3"],
    "json": ["C3"],
    "queue": ["C2", "C30", "C37"],
    "ota": ["C19", "C22"],
    "nvs": ["C19"],
    "flash": ["C19"],
    "sleep": ["C21"],
    "power": ["C21", "C24"],
    "gpio": ["C18"],
    "i2c": ["C18", "C45"],
    "spi": ["C18", "C45"],
    "sensor": ["C45"],
    "timer": ["C16"],
    "dma": ["C4", "C28"],
    "i2s": ["C4", "C25", "C26"],
    "codec": ["C26"],
    "video": ["C25", "C26", "C27", "C28"],
    "camera": ["C25", "C28"],
    "tls": ["C7", "C8", "C20"],
    "mbedtls": ["C7", "C20"],
    "log": ["C14"],
    "secret": ["C9"],
    "config": ["C39"],
    "kconfig": ["C39"],
    "multicore": ["C17"],
    "ipc": ["C17"],
    "mutex": ["C43", "C5"],
    "lock": ["C43"],
    "critical": ["C44"],
    "isr": ["C4"],
    "hal": ["C4"],
}


# ============================================================================
# 推理核心逻辑
# ============================================================================

def infer_from_file_changes(changed_files: list[str]) -> dict:
    """从文件变更推断受影响的约束域"""
    affected = set()
    file_mapping = {}

    for file_path in changed_files:
        lower = file_path.lower()
        matched = []
        for keyword, constraints in FILE_TO_CONSTRAINTS.items():
            if keyword in lower:
                affected.update(constraints)
                matched.extend(constraints)
        if matched:
            file_mapping[file_path] = sorted(set(matched))

    return {
        "affected_constraints": sorted(affected),
        "direct": sorted(affected),
        "file_mapping": file_mapping,
    }


def infer_from_constraints(constraints: list[str]) -> dict:
    """从约束域推断联动和冲突"""
    affected = set()
    conflicts_found = []

    # Normalize input
    for c in constraints:
        c_id = c.replace("C", "").split(".")[0]
        affected.add(f"C{c_id}")

    # 扩展联动和依赖
    expanded = set(affected)
    for c in list(affected):
        if c in LINKAGES:
            expanded.update(LINKAGES[c])
        if c in DEPENDENCIES:
            expanded.update(DEPENDENCIES[c])
    affected = expanded

    # 检测冲突（带严重度）
    for c in constraints:
        c_id = c.replace("C", "").split(".")[0]
        c_key = f"C{c_id}"
        for conflict_a, conflict_b, desc, severity in CONFLICTS:
            ca = conflict_a.split(".")[0]
            cb = conflict_b.split(".")[0]
            if c_key == ca or c_key == cb:
                other = cb if c_key == ca else ca
                if other in affected:
                    conflicts_found.append({
                        "constraint_a": conflict_a,
                        "constraint_b": conflict_b,
                        "description": desc,
                        "severity": severity,
                        "name_a": CONSTRAINT_NAMES.get(ca, ca),
                        "name_b": CONSTRAINT_NAMES.get(cb, cb),
                    })

    # 生成修复链（拓扑排序）
    visited = set()
    chain = []

    def topo_sort(c):
        if c in visited:
            return
        visited.add(c)
        if c in DEPENDENCIES:
            for dep in DEPENDENCIES[c]:
                topo_sort(dep)
        chain.append(c)

    for c in sorted(affected):
        topo_sort(c)

    # 为修复链添加优先级标注
    chain_with_priority = []
    for c in chain:
        priority = "P1"
        # Check if this is a P0 constraint
        for conflict_a, conflict_b, _, sev in CONFLICTS:
            if c == conflict_a.split(".")[0] or c == conflict_b.split(".")[0]:
                if sev == "P0":
                    priority = "P0"
                    break
        name = CONSTRAINT_NAMES.get(c, "")
        chain_with_priority.append({
            "constraint": c,
            "name": name,
            "priority": priority,
        })

    return {
        "affected_constraints": sorted(affected),
        "affected_count": len(affected),
        "conflicts": conflicts_found,
        "conflict_count": len(conflicts_found),
        "fix_chain": chain,
        "fix_chain_annotated": chain_with_priority,
    }


def generate_mermaid_graph(constraints: list[str], highlight_conflicts: bool = True) -> str:
    """生成受影响约束的 Mermaid 图（v2: 带冲突高亮）"""
    affected = set()
    for c in constraints:
        c_id = c.replace("C", "").split(".")[0]
        c_key = f"C{c_id}"
        affected.add(c_key)
        if c_key in LINKAGES:
            affected.update(LINKAGES[c_key])
        if c_key in DEPENDENCIES:
            for dep in DEPENDENCIES[c_key]:
                affected.add(dep)

    # Find conflict pairs for highlighting
    conflict_pairs = set()
    if highlight_conflicts:
        for conflict_a, conflict_b, _, _ in CONFLICTS:
            ca = conflict_a.split(".")[0]
            cb = conflict_b.split(".")[0]
            if ca in affected and cb in affected:
                conflict_pairs.add((ca, cb))

    lines = ["graph TD"]

    # Nodes with style
    for c in sorted(affected):
        name = CONSTRAINT_NAMES.get(c, "")
        label = f"{c} {name}"
        if c in [x.replace("C", "").split(".")[0] for x in constraints]:
            lines.append(f'    {c}["{label}"]:::input')
        else:
            lines.append(f'    {c}["{label}"]')

    # Dependency edges
    for src, targets in DEPENDENCIES.items():
        if src in affected:
            for dst in targets:
                if dst in affected:
                    if (src, dst) in conflict_pairs or (dst, src) in conflict_pairs:
                        lines.append(f"    {src} -.->|conflict| {dst}")
                    else:
                        lines.append(f"    {src} --> {dst}")

    # Styles
    lines.append("    classDef input fill:#f96,stroke:#333,stroke-width:2px")

    return "\n".join(lines)


# ============================================================================
# 自测
# ============================================================================

def run_self_test() -> int:
    """自测：验证推理引擎正确性"""
    passed = 0
    failed = 0

    # Test 1: File-based inference
    result = infer_from_file_changes(["src/audio_player.c", "src/wss_client.c"])
    assert "C4" in result["affected_constraints"], "audio should map to C4"
    assert "C20" in result["affected_constraints"], "wss should map to C20"
    assert "C25" in result["affected_constraints"], "audio should map to C25"
    print("[PASS] file-based inference")
    passed += 1

    # Test 2: Constraint-based inference with conflicts
    result = infer_from_constraints(["C21", "C25"])
    assert result["affected_count"] > 5, f"should have >5 affected, got {result['affected_count']}"
    assert result["conflict_count"] > 0, "should detect conflicts between C21 and C25"
    print(f"[PASS] constraint inference: {result['affected_count']} affected, {result['conflict_count']} conflicts")
    passed += 1

    # Test 3: Fix chain should be topologically sorted
    chain = result["fix_chain"]
    assert len(chain) > 0, "fix chain should not be empty"
    # C7 should come before C25 (dependency)
    if "C7" in chain and "C25" in chain:
        assert chain.index("C7") < chain.index("C25"), "C7 should precede C25 in fix chain"
        print("[PASS] fix chain topological order")
        passed += 1
    else:
        print("[SKIP] fix chain order (C7/C25 not in chain)")
        passed += 1

    # Test 4: Mermaid output
    mermaid = generate_mermaid_graph(["C21", "C25"])
    assert "graph TD" in mermaid, "should produce valid mermaid"
    assert "C21" in mermaid, "should include C21"
    assert "C25" in mermaid, "should include C25"
    print("[PASS] mermaid generation")
    passed += 1

    # Test 5: JSON output
    json_str = json.dumps(result, ensure_ascii=False)
    parsed = json.loads(json_str)
    assert "affected_constraints" in parsed
    assert "conflicts" in parsed
    assert "fix_chain" in parsed
    print("[PASS] JSON serialization")
    passed += 1

    # Test 6: Single constraint inference
    result = infer_from_constraints(["C22"])
    assert "C22" in result["affected_constraints"]
    assert "C19" in result["affected_constraints"] or "C20" in result["affected_constraints"]
    print(f"[PASS] single constraint C22: {result['affected_count']} affected")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="约束推理引擎 v2")
    parser.add_argument("--changed", nargs="*", help="变更描述 (file:change)")
    parser.add_argument("--changed-files", nargs="*", help="变更文件路径")
    parser.add_argument("--constraints", nargs="*", help="约束域 ID (如 C21 C25)")
    parser.add_argument("--graph", action="store_true", help="输出 Mermaid 图")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.constraints:
        result = infer_from_constraints(args.constraints)
    elif args.changed_files:
        result = infer_from_file_changes(args.changed_files)
    elif args.changed:
        files = [c.split(":")[0] for c in args.changed]
        result = infer_from_file_changes(files)
    else:
        parser.print_help()
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.graph and args.constraints:
        print(generate_mermaid_graph(args.constraints))
    else:
        print("=== 约束推理结果 v2 ===\n")

        print(f"受影响约束域: {', '.join(result['affected_constraints'])}")
        print(f"总数: {result.get('affected_count', len(result['affected_constraints']))}")

        if "conflicts" in result and result["conflicts"]:
            print(f"\n冲突检测 ({result['conflict_count']} 个):")
            # Group by severity
            by_severity = {}
            for c in result["conflicts"]:
                sev = c.get("severity", "P1")
                by_severity.setdefault(sev, []).append(c)

            for sev in ["P0", "P1", "P2"]:
                if sev in by_severity:
                    for c in by_severity[sev]:
                        print(f"  [{sev}] {c['constraint_a']} ({c['name_a']}) <-> {c['constraint_b']} ({c['name_b']})")
                        print(f"        {c['description']}")

        if "fix_chain_annotated" in result and result["fix_chain_annotated"]:
            print(f"\n推荐修复链 (拓扑排序):")
            for item in result["fix_chain_annotated"]:
                print(f"  {item['priority']} {item['constraint']} {item['name']}")

        if "direct" in result:
            print(f"\n直接匹配: {', '.join(result['direct'])}")

        if "file_mapping" in result and result["file_mapping"]:
            print(f"\n文件→约束映射:")
            for f, cs in result["file_mapping"].items():
                print(f"  {f} -> {', '.join(cs)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
