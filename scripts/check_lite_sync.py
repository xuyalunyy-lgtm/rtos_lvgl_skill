#!/usr/bin/env python3
"""
Lite version sync check script.

Check whether freertos-skill-lite is missing critical workflows, platforms, prompts,
or has unsynchronized version numbers / CHANGELOG.

Usage:
    python scripts/check_lite_sync.py
    python scripts/check_lite_sync.py --fix  # auto-fix fixable issues
"""

from __future__ import annotations

import argparse
import re
import sys
import subprocess
import json
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


def check_lite_runtime_docs() -> list[dict]:
    """Ensure Lite structure docs do not advertise unavailable runtime commands."""
    issues = []
    skill_structure = LITE_DIR / "references" / "skill_structure.md"
    if not skill_structure.exists():
        return issues

    text = skill_structure.read_text(encoding="utf-8")
    forbidden = (
        "python tools/",
        "python scripts/",
        ".\\scripts\\",
        "run_review.py",
        "skill_iterate.py",
        "check_skill_metadata.py",
    )
    for pattern in forbidden:
        if pattern in text:
            issues.append({
                "type": "lite_runtime_doc_leak",
                "file": "references/skill_structure.md",
                "detail": f"Lite doc advertises unavailable command/token: {pattern}",
                "fix": "copy",
            })
            break
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
        try:
            rel = src.relative_to(FULL_DIR / "references")
        except ValueError:
            pass
        else:
            text = sync_lite.patch_lite_reference(text, rel)
    return text


def fix_issues(issues: list[dict], verbose: bool = False) -> int:
    """Auto-fix fixable issues"""
    fixed = 0
    for issue in issues:
        if issue["fix"] == "copy":
            src = FULL_DIR / issue["file"]
            dst = LITE_DIR / issue["file"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(expected_lite_text(src), encoding="utf-8", newline="\n")
            if verbose:
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
            if verbose:
                print(f"  ✓ Updated lite version to {full_version}")
            fixed += 1
    return fixed


def run_architecture_sync_check() -> bool:
    """Run architecture sync consistency check and return whether it passes."""
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "check_architecture_sync.py"),
        "--json",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
        )
    except OSError as e:
        print(f"  Architecture sync check execution failed: {e}")
        return False

    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)

    if result.returncode != 0:
        return False

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        print("  Architecture sync check output is not valid JSON", file=sys.stderr)
        return False

    return bool(payload.get("pass", False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Lite version sync checker")
    parser.add_argument("--fix", action="store_true", help="Auto-fix sync issues")
    args = parser.parse_args()

    if not LITE_DIR.exists():
        print(f"[check_lite_sync] Lite directory not found (optional): {LITE_DIR}")
        return 0

    print("[check_lite_sync] Start Lite synchronization check")

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
    all_issues.extend(check_lite_runtime_docs())

    auto_fixable = sum(1 for item in all_issues if item["fix"] in {"copy", "update_version"})
    manual_only = len(all_issues) - auto_fixable

    if not all_issues:
        if args.fix:
            print("=== No auto-fixable items ===")
            arch_ok = run_architecture_sync_check()
            print(f"[SUMMARY] lite_sync=PASS")
            print(f"[SUMMARY] architecture_check={('PASS' if arch_ok else 'FAIL')}")
            print(f"[SUMMARY] final={('PASS' if arch_ok else 'FAIL')}")
            return 0 if arch_ok else 1

        print("Lite sync check passed")
        return 0

    print(f"[SUMMARY] lite_sync={len(all_issues)} issues (auto={auto_fixable}, manual={manual_only})")

    if args.fix:
        fixed = fix_issues(all_issues)
        remaining = len(all_issues) - fixed
        print(f"[SUMMARY] lite_sync_auto_fix={fixed}/{len(all_issues)}")
        print(f"[SUMMARY] manual_pending={remaining}")

        arch_ok = run_architecture_sync_check()
        print(f"[SUMMARY] architecture_check={('PASS' if arch_ok else 'FAIL')}")

        final_ok = (remaining == 0 and arch_ok)
        print(f"[SUMMARY] final={('PASS' if final_ok else 'FAIL')}")
        return 0 if final_ok else 1

    print(f"[SUMMARY] final=FAIL (run with --fix to auto-fix auto items)")
    return 1

if __name__ == "__main__":
    sys.exit(main())

