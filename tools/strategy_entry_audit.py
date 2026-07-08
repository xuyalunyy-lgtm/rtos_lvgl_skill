#!/usr/bin/env python3
"""Audit strategy->execution mapping table coverage in prompt docs.

Usage:
  python tools/strategy_entry_audit.py --prompt prompts/lcd_display_driver.txt
  python tools/strategy_entry_audit.py --self-test
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPT = ROOT / "prompts" / "lcd_display_driver.txt"
SECTION_RE_TEMPLATE = r"^###\s*{section}\b"
MISSING_MARKERS = (
    "missing",
    "待补充",
    "待补齐",
    "待落地",
    "待实现",
    "待完成",
    "待处理",
    "todo",
    "tbd",
)
PY_FILE_RE = re.compile(r"[A-Za-z0-9_./\\-]+\\.py", re.IGNORECASE)


@dataclass(frozen=True)
class TableRow:
    strategy_id: str
    execution_entry: str
    line_no: int


def _section_bounds(lines: list[str], section_id: str) -> tuple[int, int]:
    section_re = re.compile(SECTION_RE_TEMPLATE.format(section=re.escape(section_id)), re.MULTILINE)
    start = -1
    end = len(lines)
    for idx, line in enumerate(lines):
        if section_re.match(line.strip()):
            start = idx
            break
    if start < 0:
        return -1, -1

    for idx in range(start + 1, len(lines)):
        if re.match(r"^###\s+", lines[idx].strip()):
            end = idx
            break

    return start, end


def _split_markdown_row(line: str) -> list[str] | None:
    text = line.strip()
    if not text.startswith("|") or not text.endswith("|"):
        return None
    return [cell.strip() for cell in text[1:-1].split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return all(bool(re.fullmatch(r"-+|:-+:?|:-+|:-+:", c.strip().strip("|"))) for c in cells)


def _parse_rows(lines: list[str], section_id: str) -> list[TableRow]:
    start, end = _section_bounds(lines, section_id)
    if start < 0:
        return []

    rows: list[TableRow] = []
    header_seen = False

    for i in range(start + 1, end):
        line = lines[i].strip()
        if not line:
            continue

        cells = _split_markdown_row(line)
        if cells is None:
            continue
        if len(cells) < 4:
            continue

        if header_seen:
            strategy_id = cells[0].strip()
            if not re.fullmatch(r"S19\.\d+", strategy_id):
                continue
            rows.append(TableRow(strategy_id, cells[2].strip(), i + 1))
            continue

        if _is_separator_row(cells):
            header_seen = True

    return rows


def _contains_missing(entry: str) -> bool:
    lowered = entry.lower()
    return any(marker in lowered for marker in MISSING_MARKERS)


def _script_candidates(entry: str) -> set[Path]:
    candidates: set[Path] = set()
    for match in PY_FILE_RE.finditer(entry):
        token = match.group(0).strip("`\"'()[]{}<>")
        if token.endswith(".py"):
            candidates.add(Path(token))
    return candidates


def _validate_entry(entry: str, row: TableRow, root: Path) -> list[str]:
    issues: list[str] = []

    if not entry or not entry.strip():
        issues.append(f"L{row.line_no} {row.strategy_id}: execution entry empty")
        return issues

    if _contains_missing(entry):
        issues.append(f"L{row.line_no} {row.strategy_id}: execution entry contains placeholder/MISSING")

    candidates = _script_candidates(entry)
    if not candidates:
        return issues

    for candidate in candidates:
        candidate_norm = candidate
        if candidate_norm.is_absolute():
            target = candidate_norm
        else:
            target = root / candidate_norm
        if not target.exists():
            issues.append(f"L{row.line_no} {row.strategy_id}: referenced script not found: {candidate_norm}")
            continue
        if not target.is_file():
            issues.append(f"L{row.line_no} {row.strategy_id}: referenced script not file: {candidate_norm}")

    return issues


def _run_audit(prompt: Path, section: str) -> tuple[int, list[str]]:
    if not prompt.is_file():
        return 1, [f"prompt file not found: {prompt}"]

    lines = prompt.read_text(encoding="utf-8").splitlines()
    rows = _parse_rows(lines, section)
    if not rows:
        return 1, [f"strategy mapping section {section} has no S19.x rows"]

    issues: list[str] = []
    for row in rows:
        issues.extend(_validate_entry(row.execution_entry, row, ROOT))

    return (1, issues) if issues else (0, [])


def _run_self_test() -> int:
    good = """# test\n\n### 19.2 strategy mapping\n\n| 策略ID | 策略 | 执行入口 | 证据 / fixture |\n|---|---|---|---|\n| S19.1 | A | `python scripts/check_log_symptom_quality_gate.py --self-test` | - |\n| S19.2 | B | `python scripts/skill_iterate.py --check` | - |\n"""
    bad = """# test\n\n### 19.2 strategy mapping\n\n| 策略ID | 策略 | 执行入口 | 证据 / fixture |\n|---|---|---|---|\n| S19.1 | A | MISSING | - |\n"""

    with tempfile.TemporaryDirectory() as td:
        good_path = Path(td) / "good.md"
        good_path.write_text(good, encoding="utf-8")
        rc, issues = _run_audit(good_path, "19.2")
        if rc != 0:
            print(f"[FAIL] self-test good sample failed ({len(issues)} issues)")
            for item in issues:
                print(f"  - {item}")
            return 1

        bad_path = Path(td) / "bad.md"
        bad_path.write_text(bad, encoding="utf-8")
        rc, issues = _run_audit(bad_path, "19.2")
        if rc == 0:
            print("[FAIL] self-test bad sample unexpectedly passed")
            return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="audit strategy->execution mapping rows")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--section", default="19.2")
    parser.add_argument("--self-test", action="store_true", help="run builtin self-test fixtures")
    args = parser.parse_args(argv)

    if args.self_test:
        if _run_self_test() == 0:
            print("[PASS] strategy_entry_audit self-test")
            return 0
        return 1

    rc, issues = _run_audit(args.prompt, args.section)
    if rc != 0:
        print("[FAIL] strategy_entry_audit failed")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("[PASS] strategy_entry_audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
