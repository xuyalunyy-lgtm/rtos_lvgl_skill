#!/usr/bin/env python3
"""
同步完整版 → freertos-skill-lite（prompts/、platforms/、workflows/、references/）。
并从 SKILL.md + skill_lite_body.md 生成 freertos-skill-lite/SKILL.md。

用法（仓库根目录）:
    python scripts/sync_lite.py
    python scripts/sync_lite.py --dry-run
    python scripts/sync_lite.py --skill-only
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LITE = ROOT / "freertos-skill-lite"
SYNC_DIRS = ("agents", "prompts", "platforms", "workflows", "references")
SKILL_SRC = ROOT / "SKILL.md"
SKILL_LITE_BODY = Path(__file__).resolve().parent / "skill_lite_body.md"
SKILL_LITE_DST = LITE / "SKILL.md"

EXAMPLE_LINK_RE = re.compile(r"\[([^\]]+)\]\(\.\./examples/([^)]+)\)")

LITE_WORKFLOW_REPLACEMENTS: list[tuple[str, str, str]] = [
    (
        "l3_new_module.md",
        r"## Step 3 — 代码生成与落地（自主实施）\n\n.*?(?=## Step 6)",
        "## Step 3 — 代码生成与落地（Lite）\n\n"
        "**默认：** [core_rules.md](../references/core_rules.md) **自主实施模式** — "
        "按 scene prompt 手写骨架，直接写入用户工程。\n\n"
        "**Lite 限制：** 无 `examples/`、`tools/`、`mvp_codegen`、`run_review`；"
        "按 [lite_manual_checklist.md](../references/lite_manual_checklist.md) 完成人工审查。\n\n"
        "## Step 4 — 编译闭环（必做）\n\n"
        "按 `platforms/xxx.md` 执行编译；失败则修错重编，直至 **0 error**。\n\n"
        "## Step 5 — 人工校验（Lite）\n\n"
        "执行 [lite_manual_checklist.md](../references/lite_manual_checklist.md)，"
        "并按已加载 prompt 手工核对 C1/C2/C3/C4 等约束。\n\n",
    ),
    (
        "debug_crash.md",
        r"## Step 3 — 修复与验证（完整版）\n\n.*?(?=## Step 4)",
        "## Step 3 — 修复与验证（Lite）\n\n"
        "按 [core_rules.md](../references/core_rules.md) 自主实施模式修改源码，编译至通过。\n"
        "执行 [lite_manual_checklist.md](../references/lite_manual_checklist.md) 完成人工审查。\n\n",
    ),
    (
        "self_iterate.md",
        r"## Step 4 — 验证闭环（完整版）\n\n```bash\n.*?```\n\n.*?(?=## Step 5)",
        "## Step 4 — 验证闭环（Lite）\n\n"
        "1. 更新 [iteration_log.md](../references/iteration_log.md) 与 [CHANGELOG.md](../CHANGELOG.md)\n"
        "2. 在完整版仓库运行 `python scripts/sync_lite.py` 或 `.\\scripts\\sync_lite.ps1`\n"
        "3. 完成 [lite_manual_checklist.md](../references/lite_manual_checklist.md)（含铁律 #2 Queue 所有权项）\n\n",
    ),
    (
        "self_iterate.md",
        r"## 验证\n- \[ \] run_review --self-test\n- \[ \] run_review --validate-examples\n"
        r"(?:- \[ \] check_runtime_distribution\n)?"
        r"(?:- \[ \] check_skill_metadata\n)?"
        r"(?:- \[ \] commit_audit --self-test\n)?"
        r"(?:- \[ \] commit_audit --strict-release\n)?"
        r"- \[ \] skill_iterate --check\n"
        r"- \[ \] sync_lite\n- \[ \] CHANGELOG \+ iteration_log",
        "## 验证\n"
        "- [ ] lite_manual_checklist\n"
        "- [ ] sync_lite 已在完整版仓库完成\n"
        "- [ ] CHANGELOG + iteration_log",
    ),
    (
        "l2_code_review.md",
        r"## Step 3 — 自动化 checker（完整版）\n\n.*?(?=## Step 4)",
        "## Step 3 — 人工审查（Lite）\n\n"
        "使用 [l2_code_review_lite.md](l2_code_review_lite.md)。\n\n",
    ),
]

LITE_REFERENCE_REPLACEMENTS: list[tuple[str, str, str]] = [
    (
        "skill_structure.md",
        r"加载方式：`python tools/product_profile\.py <platform>` · `--json` · `--stack <task>`",
        "Lite 用法：按上表人工识别平台能力；需要自动 profile 时回到完整版源码仓运行工具。",
    ),
    (
        "skill_structure.md",
        r"\| 工具优先 \| `run_review\.py` 代替读 checker 源码 \|",
        "| Lite 优先 | `lite_manual_checklist.md` + `constraint_index.md` 手工核对 |",
    ),
    (
        "skill_structure.md",
        r"## 工具目录（完整版 · workflow 内调用）\n\n.*?\n---",
        "## 工具目录（Lite · 人工替代）\n\n"
        "Lite 包不携带 `tools/`、`examples/`、`scripts/`。需要自动 checker、安装或同步命令时，"
        "回到完整版源码仓执行；Lite 内按下表人工替代。\n\n"
        "| 用途 | Lite 做法 |\n"
        "|------|-----------|\n"
        "| L2 审查 | [l2_code_review_lite.md](../workflows/l2_code_review_lite.md) + [lite_manual_checklist.md](lite_manual_checklist.md) |\n"
        "| C1-C45 约束核对 | [core_rules.md](core_rules.md) + [constraint_index.md](constraint_index.md) + 对应 prompt 手工检查 |\n"
        "| 正/反例参考 | 回到完整版 `examples/README.md` 与对应 example 文件 |\n"
        "| Skill 维护同步 | 回到完整版源码仓执行同步与校验脚本 |\n\n"
        "---",
    ),
]


def patch_lite_examples(content: str) -> str:
    return EXAMPLE_LINK_RE.sub(r"完整版 `examples/\2`", content)


def patch_lite_workflow(content: str, rel: Path) -> str:
    for name, pattern, repl in LITE_WORKFLOW_REPLACEMENTS:
        if rel.name == name:
            content, n = re.subn(pattern, lambda _m: repl, content, count=1, flags=re.DOTALL)
            if not n:
                raise ValueError(f"workflow patch no match: {rel}")
    return content


def patch_lite_reference(content: str, rel: Path) -> str:
    for name, pattern, repl in LITE_REFERENCE_REPLACEMENTS:
        if rel.name == name:
            content, n = re.subn(pattern, lambda _m: repl, content, count=1, flags=re.DOTALL)
            if not n:
                raise ValueError(f"reference patch no match: {rel}")
    return content


def parse_frontmatter(skill_path: Path) -> str:
    text = skill_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{skill_path} 缺少 YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{skill_path} frontmatter 格式错误")
    return f"---{parts[1]}---\n"


def generate_lite_skill(dry_run: bool) -> list[str]:
    actions: list[str] = []
    if not SKILL_LITE_BODY.is_file():
        raise FileNotFoundError(f"缺少模板: {SKILL_LITE_BODY}")
    if not SKILL_SRC.is_file():
        raise FileNotFoundError(f"缺少: {SKILL_SRC}")

    frontmatter = parse_frontmatter(SKILL_SRC)
    body = SKILL_LITE_BODY.read_text(encoding="utf-8")
    content = frontmatter + body

    actions.append("GENERATE freertos-skill-lite/SKILL.md")
    if not dry_run:
        SKILL_LITE_DST.write_text(content, encoding="utf-8", newline="\n")
    return actions


def sync_tree(src_dir: Path, dst_dir: Path, dry_run: bool) -> list[str]:
    actions: list[str] = []
    if not src_dir.is_dir():
        raise FileNotFoundError(f"源目录不存在: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)

    for src in sorted(src_dir.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(src_dir)
        dst = dst_dir / rel

        if src.suffix.lower() in (".md", ".txt"):
            text = src.read_text(encoding="utf-8")
            patched = patch_lite_examples(text)
            if src_dir.name == "workflows":
                patched = patch_lite_workflow(patched, rel)
            if src_dir.name == "references":
                patched = patch_lite_reference(patched, rel)
            actions.append(f"PATCH+COPY {src_dir.name}/{rel}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(patched, encoding="utf-8", newline="\n")
        else:
            actions.append(f"COPY {src_dir.name}/{rel}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    stale = set(p.relative_to(dst_dir) for p in dst_dir.rglob("*") if p.is_file())
    fresh = set(p.relative_to(src_dir) for p in src_dir.rglob("*") if p.is_file())
    for rel in sorted(stale - fresh):
        actions.append(f"DELETE stale {src_dir.name}/{rel}")
        if not dry_run:
            (dst_dir / rel).unlink(missing_ok=True)

    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="同步完整版 → Lite")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将执行的操作")
    parser.add_argument("--skill-only", action="store_true", help="仅生成 Lite SKILL.md")
    args = parser.parse_args()

    if not LITE.is_dir():
        print(f"错误: Lite 目录不存在: {LITE}", file=sys.stderr)
        return 1

    total = 0

    print("\n=== SKILL.md → freertos-skill-lite/SKILL.md ===")
    try:
        for line in generate_lite_skill(args.dry_run):
            print(f"  {line}")
            total += 1
    except (FileNotFoundError, ValueError) as e:
        print(f"  错误: {e}", file=sys.stderr)
        return 1

    if not args.skill_only:
        for name in SYNC_DIRS:
            src = ROOT / name
            dst = LITE / name
            print(f"\n=== {name}/ → freertos-skill-lite/{name}/ ===")
            try:
                actions = sync_tree(src, dst, args.dry_run)
            except FileNotFoundError as e:
                print(f"  跳过: {e}")
                continue
            except ValueError as e:
                print(f"  错误: {e}", file=sys.stderr)
                return 1
            for line in actions:
                print(f"  {line}")
            total += len(actions)

    mode = "（dry-run）" if args.dry_run else ""
    print(f"\n完成{mode}，共 {total} 项。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
