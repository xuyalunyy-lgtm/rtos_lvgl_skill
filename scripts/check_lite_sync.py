#!/usr/bin/env python3
"""
Lite 版本同步检查脚本。

检查 freertos-skill-lite 是否漏掉关键 workflow、platform、prompt，
或者版本号/CHANGELOG 没同步。

用法:
    python scripts/check_lite_sync.py
    python scripts/check_lite_sync.py --fix  # 自动修复可修复的问题
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import sync_lite

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Root directory
ROOT = Path(__file__).parent.parent
FULL_DIR = ROOT
LITE_DIR = ROOT / "freertos-skill-lite"

# Files that MUST exist in lite
REQUIRED_PROMPTS = [
    "lvgl_thread_safety.txt",
    "memory_ownership.txt",
    "cjson_safe_parse.txt",
    "audio_dma_pingpong.txt",
    "test_mode_macro.txt",
    "sdk_trim_prune.txt",
    "memory_alloc_optimize.txt",
    "boot_wdt_lifecycle.txt",
    "secrets_kconfig.txt",
    "voice_asr_uplink.txt",
    "coding_style.txt",
    "error_handling.txt",
    "state_machine_patterns.txt",
    "logging_debug.txt",
    "inter_task_communication.txt",
    "timer_management.txt",
    "multi_core_ipc.txt",
    "peripheral_driver_safety.txt",
    "flash_nvs_safety.txt",
    "network_resilience.txt",
    "low_power_management.txt",
    "lcd_display_driver.txt",
    "peripheral_shutdown_safety.txt",
    "av_pipeline_sync.txt",
    "av_codec_format.txt",
    "av_clock_jitter.txt",
    "av_dma_buffer_lifecycle.txt",
]

REQUIRED_WORKFLOWS = [
    "l2_code_review_lite.md",
    "l3_sdk_trim.md",
    "l3_new_module.md",
    "debug_crash.md",
    "self_iterate.md",
]

REQUIRED_PLATFORMS = [
    "esp32.md",
    "stm32.md",
    "jl.md",
    "bk.md",
]

REQUIRED_REFERENCES = [
    "core_rules.md",
    "constraint_detail.md",
    "constraint_index.md",
    "constraint_graph.md",
    "skill_structure.md",
    "iteration_log.md",
    "lite_manual_checklist.md",
]

REQUIRED_AGENTS = [
    "openai.yaml",
]


def get_version(file_path: Path) -> str | None:
    """Extract version from SKILL.md frontmatter"""
    try:
        text = file_path.read_text(encoding="utf-8")
        m = re.search(r"^version:\s*(\S+)", text, re.MULTILINE)
        if m:
            return m.group(1)
        m = re.search(
            r"^metadata:\s*\n(?:[ \t]+[^\n]*\n)*?[ \t]+version:\s*(\S+)",
            text,
            re.MULTILINE,
        )
        return m.group(1) if m else None
    except OSError:
        return None


def check_prompts() -> list[dict]:
    """Check if all required prompts exist in lite"""
    issues = []
    for prompt in REQUIRED_PROMPTS:
        full_path = FULL_DIR / "prompts" / prompt
        lite_path = LITE_DIR / "prompts" / prompt

        if full_path.exists() and not lite_path.exists():
            issues.append({
                "type": "missing_prompt",
                "file": f"prompts/{prompt}",
                "fix": "copy",
            })
    return issues


def check_workflows() -> list[dict]:
    """Check if all required workflows exist in lite"""
    issues = []
    for wf in REQUIRED_WORKFLOWS:
        lite_path = LITE_DIR / "workflows" / wf
        if not lite_path.exists():
            issues.append({
                "type": "missing_workflow",
                "file": f"workflows/{wf}",
                "fix": "manual",
            })
    return issues


def check_platforms() -> list[dict]:
    """Check if all required platforms exist in lite"""
    issues = []
    for plat in REQUIRED_PLATFORMS:
        lite_path = LITE_DIR / "platforms" / plat
        if not lite_path.exists():
            issues.append({
                "type": "missing_platform",
                "file": f"platforms/{plat}",
                "fix": "copy",
            })
    return issues


def check_references() -> list[dict]:
    """Check if all required references exist in lite"""
    issues = []
    for ref in REQUIRED_REFERENCES:
        lite_path = LITE_DIR / "references" / ref
        if not lite_path.exists():
            issues.append({
                "type": "missing_reference",
                "file": f"references/{ref}",
                "fix": "copy",
            })
    return issues


def check_agents() -> list[dict]:
    """Check if all required agent metadata files exist in lite."""
    issues = []
    for agent_file in REQUIRED_AGENTS:
        lite_path = LITE_DIR / "agents" / agent_file
        if not lite_path.exists():
            issues.append({
                "type": "missing_agent_metadata",
                "file": f"agents/{agent_file}",
                "fix": "copy",
            })
    return issues


def check_version_sync() -> list[dict]:
    """Check if version numbers match"""
    issues = []
    full_version = get_version(FULL_DIR / "SKILL.md")
    lite_version = get_version(LITE_DIR / "SKILL.md")

    if full_version and lite_version and full_version != lite_version:
        issues.append({
            "type": "version_mismatch",
            "detail": f"Full: {full_version}, Lite: {lite_version}",
            "fix": "update_version",
        })
    return issues


def check_prompt_content_sync() -> list[dict]:
    """Check if prompt files have diverged"""
    issues = []
    for prompt in REQUIRED_PROMPTS:
        full_path = FULL_DIR / "prompts" / prompt
        lite_path = LITE_DIR / "prompts" / prompt

        if full_path.exists() and lite_path.exists():
            full_text = expected_lite_text(full_path)
            lite_text = lite_path.read_text(encoding="utf-8")

            # Compare content (ignore whitespace differences)
            if full_text.strip() != lite_text.strip():
                issues.append({
                    "type": "prompt_diverged",
                    "file": f"prompts/{prompt}",
                    "fix": "copy",
                })
    return issues


def check_workflow_content_sync() -> list[dict]:
    """Check if generated Lite workflow files have diverged."""
    issues = []
    workflows_dir = FULL_DIR / "workflows"
    for full_path in sorted(workflows_dir.glob("*.md")):
        lite_path = LITE_DIR / "workflows" / full_path.name
        if not lite_path.exists():
            continue

        try:
            full_text = expected_lite_text(full_path)
        except ValueError as e:
            issues.append({
                "type": "workflow_patch_failed",
                "file": f"workflows/{full_path.name}",
                "detail": str(e),
                "fix": "manual",
            })
            continue

        lite_text = lite_path.read_text(encoding="utf-8")
        if full_text.strip() != lite_text.strip():
            issues.append({
                "type": "workflow_diverged",
                "file": f"workflows/{full_path.name}",
                "fix": "copy",
            })
    return issues


def check_agent_content_sync() -> list[dict]:
    """Check if generated Lite agent metadata files have diverged."""
    issues = []
    for agent_file in REQUIRED_AGENTS:
        full_path = FULL_DIR / "agents" / agent_file
        lite_path = LITE_DIR / "agents" / agent_file
        if full_path.exists() and lite_path.exists():
            full_text = full_path.read_text(encoding="utf-8")
            lite_text = lite_path.read_text(encoding="utf-8")
            if full_text.strip() != lite_text.strip():
                issues.append({
                    "type": "agent_metadata_diverged",
                    "file": f"agents/{agent_file}",
                    "fix": "copy",
                })
    return issues


def expected_lite_text(src: Path) -> str:
    """Return the text expected after sync_lite.py's Lite transformations."""
    text = src.read_text(encoding="utf-8")
    if src.suffix.lower() in (".md", ".txt"):
        text = sync_lite.patch_lite_examples(text)
        try:
            rel = src.relative_to(FULL_DIR / "workflows")
        except ValueError:
            pass
        else:
            text = sync_lite.patch_lite_workflow(text, rel)
    return text


def fix_issues(issues: list[dict]) -> int:
    """Auto-fix fixable issues"""
    fixed = 0
    for issue in issues:
        if issue["fix"] == "copy":
            src = FULL_DIR / issue["file"]
            dst = LITE_DIR / issue["file"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(expected_lite_text(src), encoding="utf-8", newline="\n")
            print(f"  ✓ Copied {issue['file']}")
            fixed += 1
        elif issue["fix"] == "update_version":
            # Update lite version to match full
            full_version = get_version(FULL_DIR / "SKILL.md")
            lite_skill = LITE_DIR / "SKILL.md"
            text = lite_skill.read_text(encoding="utf-8")
            if re.search(r"^version:\s*\S+", text, re.MULTILINE):
                text = re.sub(
                    r"^version:\s*\S+",
                    f"metadata:\n  version: {full_version}",
                    text,
                    count=1,
                    flags=re.MULTILINE,
                )
            elif re.search(r"^metadata:\s*\n(?:[ \t]+[^\n]*\n)*?[ \t]+version:\s*\S+", text, re.MULTILINE):
                text = re.sub(
                    r"(^metadata:\s*\n(?:[ \t]+[^\n]*\n)*?[ \t]+version:\s*)\S+",
                    rf"\g<1>{full_version}",
                    text,
                    count=1,
                    flags=re.MULTILINE,
                )
            lite_skill.write_text(text, encoding="utf-8", newline="\n")
            print(f"  ✓ Updated lite version to {full_version}")
            fixed += 1
    return fixed


def main() -> int:
    parser = argparse.ArgumentParser(description="Lite 版本同步检查")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题")
    args = parser.parse_args()

    if not LITE_DIR.exists():
        print(f"[check_lite_sync] Lite 目录不存在: {LITE_DIR}")
        return 1

    print("[check_lite_sync] 检查 Lite 版本同步状态...\n")

    all_issues = []
    all_issues.extend(check_prompts())
    all_issues.extend(check_workflows())
    all_issues.extend(check_platforms())
    all_issues.extend(check_references())
    all_issues.extend(check_agents())
    all_issues.extend(check_version_sync())
    all_issues.extend(check_prompt_content_sync())
    all_issues.extend(check_workflow_content_sync())
    all_issues.extend(check_agent_content_sync())

    if not all_issues:
        print("✅ Lite 版本与完整版完全同步")
        return 0

    # Group by type
    by_type: dict[str, list[dict]] = {}
    for issue in all_issues:
        t = issue["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(issue)

    print(f"发现 {len(all_issues)} 个同步问题:\n")

    for issue_type, issues in by_type.items():
        print(f"=== {issue_type} ({len(issues)} 处) ===")
        for issue in issues:
            if "file" in issue:
                print(f"  - {issue['file']}")
            if "detail" in issue:
                print(f"  - {issue['detail']}")
        print()

    if args.fix:
        print("=== 自动修复 ===")
        fixed = fix_issues(all_issues)
        print(f"\n已修复 {fixed}/{len(all_issues)} 个问题")
        remaining = len(all_issues) - fixed
        if remaining > 0:
            print(f"剩余 {remaining} 个问题需手动处理")
    else:
        print("提示: 使用 --fix 自动修复可修复的问题")

    return 1


if __name__ == "__main__":
    sys.exit(main())
