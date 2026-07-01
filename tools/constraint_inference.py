#!/usr/bin/env python3
"""
约束推理引擎 v1 — 从知识图谱自动推理约束影响。

功能：
  1. 输入变更文件列表，输出需检查的约束域
  2. 检测约束冲突（如 C21 低功耗 vs C25 实时音视频）
  3. 推荐修复链（基于依赖图拓扑排序）

用法:
    python tools/constraint_inference.py --changed "app_audio.c:queue_depth"
    python tools/constraint_inference.py --changed-files src/audio.c src/network.c
    python tools/constraint_inference.py --constraints C21 C25
    python tools/constraint_inference.py --graph
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

# 冲突关系：A ↔ B（同时满足需要权衡）
CONFLICTS = [
    ("C8.6", "C8.2", "init 需同步时间 vs TLS 前须 SNTP"),
    ("C1.6", "C1.5", "LVGL 锁序 vs SDK 锁序"),
    ("C7.5", "C7", "WSS 栈 ≥4096 vs RAM 受限"),
    ("C4.5", "C15.1", "音频优先级 > LVGL vs 相邻差 ≥2"),
    ("C14.1", "C4.3", "需要日志 vs ISR 禁日志"),
    ("C5.1", "C6", "测试宏 vs 量产关闭"),
    ("C9.1", "C9", "密钥不入库 vs 调试便利"),
    ("C17.1", "C17", "跨核须 IPC vs 延迟需求"),
    ("C11.5", "C12.4", "函数 ≤80 行 vs goto cleanup"),
    ("C16.1", "C16", "timer 回调禁阻塞 vs 业务逻辑"),
    ("C21.4", "C20.5", "睡眠前关 WiFi vs 网络须降级"),
    ("C21.3", "C4.5", "Tickless Idle vs 音频优先级"),
    ("C25.1", "C23.3", "audio clock master vs 显示帧率"),
    ("C25.3", "C7.13", "有界 video queue vs 固定块池"),
    ("C26.1", "C25.4", "格式一致 vs 热路径禁分配"),
    ("C27.2", "C25.3", "jitter buffer 水位 vs 低延迟"),
    ("C28.1", "C7.10", "DMA-capable vs 外部 RAM 优先"),
    ("C31.1", "C31.4", "有限 timeout vs daemon 永久等待"),
    ("C32.5", "C34.2", "现场 dump vs 热路径禁日志"),
    ("C34.2", "C7.13", "hot path 禁分配 vs 固定块池"),
    ("C35.1", "C40.1", "关键路径预算 vs 复现命令简洁"),
    ("C43.1", "C34.1", "锁预算 vs 热路径实时性"),
    ("C44.1", "C4", "关中断预算 vs ISR 实时性"),
    ("C22.2", "C38.2", "OTA mark_valid vs 故障恢复"),
    ("C22.5", "C35.1", "OTA 超时重试 vs 启动预算"),
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

# 文件路径 → 约束域映射（关键词匹配）
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


def infer_from_file_changes(changed_files: list[str]) -> dict:
    """从文件变更推断受影响的约束域"""
    affected = set()
    for file_path in changed_files:
        lower = file_path.lower()
        for keyword, constraints in FILE_TO_CONSTRAINTS.items():
            if keyword in lower:
                affected.update(constraints)

    return {
        "affected_constraints": sorted(affected),
        "direct": sorted(affected),
    }


def infer_from_constraints(constraints: list[str]) -> dict:
    """从约束域推断联动和冲突"""
    affected = set(constraints)
    conflicts_found = []
    fix_chain = []

    # 扩展联动
    for c in constraints:
        c_id = c.replace("C", "").split(".")[0]
        c_key = f"C{c_id}"
        if c_key in LINKAGES:
            affected.update(LINKAGES[c_key])
        if c_key in DEPENDENCIES:
            affected.update(DEPENDENCIES[c_key])

    # 检测冲突
    for c in constraints:
        for conflict_a, conflict_b, desc in CONFLICTS:
            ca = conflict_a.split(".")[0]
            cb = conflict_b.split(".")[0]
            if c == ca or c == cb:
                other = cb if c == ca else ca
                if other in affected:
                    conflicts_found.append({
                        "constraint_a": conflict_a,
                        "constraint_b": conflict_b,
                        "description": desc,
                    })

    # 生成修复链（拓扑排序）
    visited = set()
    chain = []

    def topo_sort(c):
        if c in visited:
            return
        visited.add(c)
        c_id = c.replace("C", "").split(".")[0]
        c_key = f"C{c_id}"
        if c_key in DEPENDENCIES:
            for dep in DEPENDENCIES[c_key]:
                topo_sort(dep)
        chain.append(c)

    for c in constraints:
        c_id = c.replace("C", "").split(".")[0]
        topo_sort(f"C{c_id}")

    return {
        "affected_constraints": sorted(affected),
        "conflicts": conflicts_found,
        "fix_chain": chain,
    }


def generate_mermaid_graph(constraints: list[str]) -> str:
    """生成受影响约束的 Mermaid 图"""
    affected = set()
    for c in constraints:
        c_id = c.replace("C", "").split(".")[0]
        c_key = f"C{c_id}"
        affected.add(c_key)
        if c_key in LINKAGES:
            affected.update(LINKAGES[c_key])
        if c_key in DEPENDENCIES:
            affected.update(DEPENDENCIES[c_key])

    lines = ["graph TD"]
    for c in sorted(affected):
        label = c.replace("C", "C")
        lines.append(f"    {c}[ {c}]")

    for src, targets in DEPENDENCIES.items():
        if src in affected:
            for dst in targets:
                if dst in affected:
                    lines.append(f"    {src} --> {dst}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="约束推理引擎 v1")
    parser.add_argument("--changed", nargs="*", help="变更描述 (file:change)")
    parser.add_argument("--changed-files", nargs="*", help="变更文件路径")
    parser.add_argument("--constraints", nargs="*", help="约束域 ID (如 C21 C25)")
    parser.add_argument("--graph", action="store_true", help="输出 Mermaid 图")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.constraints:
        result = infer_from_constraints(args.constraints)
    elif args.changed_files:
        result = infer_from_file_changes(args.changed_files)
    elif args.changed:
        # Extract file names from "file:change" format
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
        print("=== 约束推理结果 ===\n")

        print(f"受影响约束域: {', '.join(result['affected_constraints'])}")
        print(f"总数: {len(result['affected_constraints'])}")

        if "conflicts" in result and result["conflicts"]:
            print(f"\n冲突检测 ({len(result['conflicts'])} 个):")
            for c in result["conflicts"]:
                print(f"  [!] {c['constraint_a']} <-> {c['constraint_b']} - {c['description']}")

        if "fix_chain" in result and result["fix_chain"]:
            print(f"\n推荐修复链:")
            print(f"  {' -> '.join(result['fix_chain'])}")

        if "direct" in result:
            print(f"\n直接匹配: {', '.join(result['direct'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
