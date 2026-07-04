#!/usr/bin/env python3
"""Batch wrapper for log_triage.py.

Use this when a debug bundle contains multiple serial, boot, or crash logs and
the first pass should identify which file carries the strongest signal.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import tempfile
from pathlib import Path
from typing import Iterable

from log_triage import triage


LOG_SUFFIXES = {".log", ".txt", ".out"}


def expand_inputs(inputs: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for raw in inputs:
        matches = [Path(p) for p in glob.glob(raw)] or [Path(raw)]
        for path in matches:
            if path.is_dir():
                candidates = [
                    p for p in path.rglob("*")
                    if p.is_file() and p.suffix.lower() in LOG_SUFFIXES
                ]
            else:
                candidates = [path]

            for candidate in candidates:
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    files.append(candidate)

    return sorted(files, key=lambda p: str(p).lower())


def symptom_ids(result: dict) -> list[str]:
    ids: list[str] = []
    for key in ("software_suspicions", "hardware_suspicions", "architecture_refactor_candidates"):
        for item in result.get(key, []):
            sid = item.get("symptom_id")
            if sid and sid not in ids:
                ids.append(sid)
    return ids


def max_severity(result: dict) -> str:
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    severities: list[str] = []
    for key in ("software_suspicions", "hardware_suspicions", "architecture_refactor_candidates"):
        severities.extend(
            item.get("severity", "")
            for item in result.get(key, [])
            if item.get("severity")
        )
    if not severities:
        return "-"
    return min(severities, key=lambda s: order.get(s, 99))


def analyze_file(path: Path, platform: str) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {
            "file": str(path),
            "error": str(exc),
            "has_symptoms": False,
            "summary": "read_error",
            "symptom_ids": [],
            "max_severity": "-",
        }

    result = triage(text, platform)
    return {
        "file": str(path),
        "summary": result.get("summary", ""),
        "confidence": result.get("confidence", ""),
        "has_symptoms": bool(result.get("has_symptoms")),
        "symptom_ids": symptom_ids(result),
        "max_severity": max_severity(result),
        "constraints": result.get("constraints", []),
        "missing_evidence_count": len(result.get("missing_evidence", [])),
        "line_count": result.get("total_lines", 0),
    }


def should_fail(rows: list[dict], mode: str) -> bool:
    if any("error" in row for row in rows):
        return True
    if mode == "none":
        return False
    if mode == "symptoms":
        return any(row.get("has_symptoms") for row in rows)
    if mode == "p0":
        return any(row.get("max_severity") == "P0" for row in rows)
    raise ValueError(f"unknown fail mode: {mode}")


def print_table(rows: list[dict]) -> None:
    if not rows:
        print("No log files found.")
        return

    print("file | severity | summary | symptoms | constraints")
    print("---- | -------- | ------- | -------- | -----------")
    for row in rows:
        symptoms = ",".join(row.get("symptom_ids", [])) or "-"
        constraints = ",".join(row.get("constraints", [])) or "-"
        print(
            f"{row['file']} | {row.get('max_severity', '-')} | "
            f"{row.get('summary', '')} | {symptoms} | {constraints}"
        )


def run_self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        clean = root / "clean.log"
        bad = root / "bad.log"
        clean.write_text("I (100) boot: ready\nI (200) app: started\n", encoding="utf-8")
        bad.write_text("E (100) dma: cache stale data detected\n", encoding="utf-8")

        rows = [analyze_file(p, "esp32") for p in expand_inputs([str(root)])]
        ids = {sid for row in rows for sid in row.get("symptom_ids", [])}
        assert len(rows) == 2, rows
        assert "DMA_CACHE_ERROR" in ids, rows
        assert should_fail(rows, "p0")
        assert not should_fail([rows[0]], "none")

    print("log_triage_batch self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch log triage for multiple firmware logs")
    parser.add_argument("inputs", nargs="*", help="log files, directories, or glob patterns")
    parser.add_argument("--platform", default="", help="platform hint, for example esp32 or zephyr")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--fail-on",
        choices=["none", "symptoms", "p0"],
        default="none",
        help="return nonzero when matching results are found",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.inputs:
        parser.print_help()
        return 2

    files = expand_inputs(args.inputs)
    rows = [analyze_file(path, args.platform) for path in files]

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        print_table(rows)

    return 1 if should_fail(rows, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
