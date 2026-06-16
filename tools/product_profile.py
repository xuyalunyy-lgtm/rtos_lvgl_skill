#!/usr/bin/env python3
"""
多产品线适配：加载芯片平台 product profile，输出约束上下文。

用法:
    python tools/product_profile.py esp32
    python tools/product_profile.py bk --features
    python tools/product_profile.py jl --stack wss_tls
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from checker_io import configure_stdout, output_json, safe_print

PROFILES_DIR = Path(__file__).resolve().parent.parent / "product_profiles"

AVAILABLE_PLATFORMS = ["esp32", "stm32", "jl", "bk"]


def load_profile(platform: str) -> dict:
    path = PROFILES_DIR / f"{platform}.json"
    if not path.exists():
        raise FileNotFoundError(f"产品 profile 不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def format_profile_text(profile: dict) -> str:
    lines = [
        "=" * 60,
        f"产品线: {profile['name']}",
        f"平台: {profile['platform']}",
        f"描述: {profile['description']}",
        "=" * 60,
        "",
        "必须检查约束:",
        f"  {', '.join(profile['required_constraints'])}",
        "",
        "可选约束（按产品决定）:",
        f"  {', '.join(profile['optional_constraints'])}",
        "",
        "任务优先级风格: " + profile['task_priority_style'],
        "严格度: " + profile['strictness'],
        "",
        "常见坑点:",
    ]
    for pitfall in profile.get("common_pitfalls", []):
        lines.append(f"  ⚠  {pitfall}")

    lines.append("")
    lines.append("功能特性:")
    for feat, enabled in profile.get("features", {}).items():
        status = "✅" if enabled else "❌"
        lines.append(f"  {status} {feat}")

    stacks = profile.get("stack_recommendations", {})
    if stacks:
        lines.append("")
        lines.append("栈大小建议 (bytes):")
        for task, sizes in stacks.items():
            lines.append(f"  {task}: 最小 {sizes['min_bytes']}, 推荐 {sizes['recommended_bytes']}")

    return "\n".join(lines)


def format_profile_json(profile: dict) -> dict:
    return {
        "profile": profile["name"],
        "platform": profile["platform"],
        "required_constraints": profile["required_constraints"],
        "optional_constraints": profile["optional_constraints"],
        "excluded_constraints": profile.get("excluded_constraints", []),
        "task_priority_style": profile["task_priority_style"],
        "strictness": profile["strictness"],
        "features": profile.get("features", {}),
        "stack_recommendations": profile.get("stack_recommendations", {}),
        "common_pitfalls": profile.get("common_pitfalls", []),
    }


def format_stack_text(profile: dict, task: str) -> str:
    stacks = profile.get("stack_recommendations", {})
    if task not in stacks:
        return f"未知任务: {task}（可用: {', '.join(stacks.keys())}）"
    s = stacks[task]
    return f"{profile['platform']} / {task}: 最小 {s['min_bytes']} bytes, 推荐 {s['recommended_bytes']} bytes"


def list_profiles_text() -> str:
    lines = ["可用产品线:"]
    for p in sorted(PROFILES_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            lines.append(f"  {data['platform']:8s}  {data['name']}")
        except Exception:
            lines.append(f"  {p.stem:8s}  (解析失败)")
    return "\n".join(lines)


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="多产品线适配 — 加载芯片平台 profile")
    parser.add_argument("platform", nargs="?", help=f"平台名: {', '.join(AVAILABLE_PLATFORMS)}")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--features", action="store_true", help="仅输出功能特性")
    parser.add_argument("--stack", help="查询指定任务的栈大小建议")
    parser.add_argument("--list", action="store_true", help="列出所有可用产品线")
    args = parser.parse_args()

    if args.list:
        print(list_profiles_text())
        return 0

    if not args.platform:
        parser.print_help()
        return 1

    try:
        profile = load_profile(args.platform)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        print(list_profiles_text())
        return 1

    if args.json:
        output_json(format_profile_json(profile))
    elif args.features:
        for feat, enabled in profile.get("features", {}).items():
            print(f"{feat}: {'yes' if enabled else 'no'}")
    elif args.stack:
        print(format_stack_text(profile, args.stack))
    else:
        safe_print(format_profile_text(profile))
    return 0


if __name__ == "__main__":
    sys.exit(main())