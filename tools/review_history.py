#!/usr/bin/env python3
"""Persist and compare machine-readable ``run_review`` reports locally."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

def append(report: dict, directory: str | Path) -> dict:
    """Store a report and annotate it with its issue-count trend."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in sorted(root.glob("*.json")):
        try:
            entries.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    previous = entries[-1] if entries else None
    total = report.get("total_issues", 0)
    old = previous.get("total_issues", 0) if previous else None
    trend = "baseline" if old is None else "improved" if total < old else "regressed" if total > old else "unchanged"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = root / f"review_{stamp}.json"
    report["history"] = {
        "trend": trend,
        "previous_total_issues": old,
        "current_total_issues": total,
        "record": str(destination),
    }
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report["history"]
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--dir", default="artifacts/review_history")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    print(json.dumps(append(report, args.dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
