#!/usr/bin/env python3
"""Apply quality policy and optional conflict allowlist to symptom route checks."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CHECK_SCRIPT = ROOT / "scripts" / "check_log_symptom_routes.py"
DEFAULT_QUALITY_POLICY_FILE = ROOT / "references" / "log_symptom_routes_quality_policy.json"
DEFAULT_CONFLICT_ALLOWLIST_FILE = ROOT / "references" / "log_symptom_route_conflict_allowlist.json"
DEFAULT_ARTIFACT = ROOT / "artifacts" / "log_symptom_routes_quality.json"


def _read_json(path: Path | None, *, allow_missing: bool = False) -> tuple[Any, list[str]]:
    if path is None:
        return {}, []
    if not path.exists():
        if allow_missing:
            return {}, []
        return None, [f"missing file: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except OSError as exc:
        return None, [f"failed to read {path}: {exc}"]
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON in {path}: {exc}"]


def _norm_pattern(pattern: str) -> str:
    return " ".join(pattern.casefold().split())


def _build_conflict_allowlist(path: Path) -> tuple[dict[str, set[tuple[str, ...]]], list[str]]:
    allowlist: dict[str, set[tuple[str, ...]]] = {
        "duplicate_patterns": set(),
        "weak_strong_overlaps": set(),
        "broad_patterns": set(),
        "multi_match_fixtures": set(),
    }

    data, errors = _read_json(path, allow_missing=True)
    if errors:
        return allowlist, errors
    if not isinstance(data, dict):
        return allowlist, [f"{path} must be a JSON object"]

    for entry in data.get("duplicate_patterns", []):
        if not isinstance(entry, dict):
            continue
        pattern = entry.get("normalized_pattern") or entry.get("pattern")
        ids = entry.get("route_ids")
        if not isinstance(pattern, str) or not pattern or not isinstance(ids, list):
            continue
        clean_ids = sorted({str(v).strip() for v in ids if isinstance(v, str) and str(v).strip()})
        if len(clean_ids) >= 2:
            allowlist["duplicate_patterns"].add((_norm_pattern(pattern), tuple(clean_ids)))

    for entry in data.get("weak_strong_overlaps", []):
        if not isinstance(entry, dict):
            continue
        weak_route_id = entry.get("weak_route_id")
        strong_route_id = entry.get("strong_route_id")
        if not isinstance(weak_route_id, str) or not weak_route_id:
            continue
        if not isinstance(strong_route_id, str) or not strong_route_id:
            continue
        signature: list[str] = [weak_route_id, strong_route_id]
        pattern = entry.get("pattern")
        if isinstance(pattern, str) and pattern:
            signature.append(_norm_pattern(pattern))
        allowlist["weak_strong_overlaps"].add(tuple(signature))

    for entry in data.get("broad_patterns", []):
        if not isinstance(entry, dict):
            continue
        route_id = entry.get("route_id")
        pattern = entry.get("pattern")
        if not isinstance(route_id, str) or not route_id:
            continue
        if not isinstance(pattern, str) or not pattern:
            continue
        allowlist["broad_patterns"].add((route_id, _norm_pattern(pattern)))

    for entry in data.get("multi_match_fixtures", []):
        if not isinstance(entry, dict):
            continue
        fixture = entry.get("fixture")
        raw_routes = entry.get("route_ids") or entry.get("matched_routes") or entry.get("routes")
        if not isinstance(fixture, str) or not fixture:
            continue
        if not isinstance(raw_routes, list):
            continue
        routes = sorted({str(v).strip() for v in raw_routes if isinstance(v, str) and str(v).strip()})
        if len(routes) >= 2:
            allowlist["multi_match_fixtures"].add((fixture, tuple(routes)))

    return allowlist, []


def _load_policy(path: Path) -> tuple[dict[str, Any], list[str]]:
    data, errors = _read_json(path, allow_missing=True)
    if errors:
        return {}, errors
    if not isinstance(data, dict):
        return {}, [f"{path} must be a JSON object"]
    return data, []


def _load_thresholds(policy: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    thresholds: dict[str, Any] = {
        "max_missing_field_alert_count": None,
        "min_average_coverage": None,
        "max_route_conflicts": None,
        "max_duplicate_patterns": None,
        "max_weak_strong_overlaps": None,
        "max_broad_patterns": None,
        "max_multi_match_fixtures": None,
    }
    errors: list[str] = []

    for key, value in policy.items():
        if key not in thresholds:
            continue
        thresholds[key] = value

    cli_map = {
        "max_missing_field_alert_count": args.max_missing_field_alerts,
        "min_average_coverage": args.min_average_coverage,
        "max_route_conflicts": args.max_route_conflicts,
        "max_duplicate_patterns": args.max_duplicate_patterns,
        "max_weak_strong_overlaps": args.max_weak_strong_overlaps,
        "max_broad_patterns": args.max_broad_patterns,
        "max_multi_match_fixtures": args.max_multi_match_fixtures,
    }

    for key, value in cli_map.items():
        if value is None:
            continue
        if key == "min_average_coverage":
            if not isinstance(value, (int, float)):
                errors.append(f"{key} must be numeric")
                continue
        elif not isinstance(value, int) or value < 0:
            errors.append(f"{key} must be a non-negative integer")
            continue
        thresholds[key] = value

    return thresholds, errors


def _normalized_routes(routes: list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(routes)))


def _filter_conflicts(quality: dict[str, Any], allowlist: dict[str, set[tuple[str, ...]]]) -> tuple[dict[str, Any], dict[str, int]]:
    conflicts = quality.get("route_conflicts", {}) if isinstance(quality, dict) else {}
    output: dict[str, Any] = {
        "duplicate_patterns": [],
        "weak_strong_overlaps": [],
        "broad_patterns": [],
        "multi_match_fixtures": [],
        "suppressed_conflicts": {"duplicate_patterns": 0, "weak_strong_overlaps": 0, "broad_patterns": 0, "multi_match_fixtures": 0},
    }

    for item in conflicts.get("duplicate_patterns", []):
        if not isinstance(item, dict):
            continue
        routes = _normalized_routes([entry.get("route_id") for entry in item.get("entries", []) if isinstance(entry.get("route_id"), str)])
        pattern = _norm_pattern(str(item.get("normalized_pattern", "")))
        signature = (pattern, routes)
        if signature in allowlist["duplicate_patterns"]:
            output["suppressed_conflicts"]["duplicate_patterns"] += 1
            continue
        output["duplicate_patterns"].append(item)

    for item in conflicts.get("weak_strong_overlaps", []):
        if not isinstance(item, dict):
            continue
        weak_route_id = item.get("weak_route_id")
        strong_route_id = item.get("strong_route_id")
        pattern = _norm_pattern(str(item.get("pattern", "")))
        if not isinstance(weak_route_id, str) or not isinstance(strong_route_id, str):
            continue

        signature = (weak_route_id, strong_route_id, pattern)
        generic_signature = (weak_route_id, strong_route_id)
        if signature in allowlist["weak_strong_overlaps"] or generic_signature in allowlist["weak_strong_overlaps"]:
            output["suppressed_conflicts"]["weak_strong_overlaps"] += 1
            continue
        output["weak_strong_overlaps"].append(item)

    for item in conflicts.get("broad_patterns", []):
        if not isinstance(item, dict):
            continue
        route_id = item.get("route_id")
        pattern = _norm_pattern(str(item.get("pattern", "")))
        if not isinstance(route_id, str):
            continue
        if (route_id, pattern) in allowlist["broad_patterns"]:
            output["suppressed_conflicts"]["broad_patterns"] += 1
            continue
        output["broad_patterns"].append(item)

    for item in conflicts.get("multi_match_fixtures", []):
        if not isinstance(item, dict):
            continue
        fixture = item.get("fixture")
        matched_routes = item.get("matched_routes")
        if not isinstance(fixture, str) or not isinstance(matched_routes, list):
            continue
        signature = (fixture, _normalized_routes([route for route in matched_routes if isinstance(route, str)]))
        if signature in allowlist["multi_match_fixtures"]:
            output["suppressed_conflicts"]["multi_match_fixtures"] += 1
            continue
        output["multi_match_fixtures"].append(item)

    return output, {
        "route_conflicts": {
            "duplicate_patterns": len(output["duplicate_patterns"]),
            "weak_strong_overlaps": len(output["weak_strong_overlaps"]),
            "broad_patterns": len(output["broad_patterns"]),
            "multi_match_fixtures": len(output["multi_match_fixtures"]),
        }
    }


def _evaluate_thresholds(quality: dict[str, Any], active_counts: dict[str, int], thresholds: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    missing = quality.get("missing_field_alert_count")
    if isinstance(thresholds.get("max_missing_field_alert_count"), int) and isinstance(missing, int) and missing > thresholds["max_missing_field_alert_count"]:
        violations.append(f"missing_field_alert_count {missing} exceeds threshold {thresholds['max_missing_field_alert_count']}")

    coverage_items = quality.get("coverage", [])
    min_average = thresholds.get("min_average_coverage")
    if min_average is not None:
        coverage_values = [item.get("coverage", 0.0) for item in coverage_items if isinstance(item, dict)]
        average = sum(coverage_values) / len(coverage_values) if coverage_values else 0.0
        if average < float(min_average):
            violations.append(f"average field coverage {average:.1f}% is below threshold {float(min_average):.1f}%")

    checks = {
        "max_route_conflicts": sum(active_counts.values()),
        "max_duplicate_patterns": active_counts["duplicate_patterns"],
        "max_weak_strong_overlaps": active_counts["weak_strong_overlaps"],
        "max_broad_patterns": active_counts["broad_patterns"],
        "max_multi_match_fixtures": active_counts["multi_match_fixtures"],
    }

    for key, value in checks.items():
        limit = thresholds.get(key)
        if isinstance(limit, int) and value > limit:
            violations.append(f"{key} {value} exceeds threshold {limit}")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate log symptom route quality report")
    parser.add_argument("--quality-policy", type=Path, default=DEFAULT_QUALITY_POLICY_FILE)
    parser.add_argument("--conflict-allowlist", type=Path, default=DEFAULT_CONFLICT_ALLOWLIST_FILE)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--max-missing-field-alerts", type=int, dest="max_missing_field_alerts")
    parser.add_argument("--min-average-coverage", type=float)
    parser.add_argument("--max-route-conflicts", type=int)
    parser.add_argument("--max-duplicate-patterns", type=int)
    parser.add_argument("--max-weak-strong-overlaps", type=int)
    parser.add_argument("--max-broad-patterns", type=int)
    parser.add_argument("--max-multi-match-fixtures", type=int)
    args = parser.parse_args()

    check = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--quality-json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if not check.stdout:
        print(f"[ERROR] no output from {CHECK_SCRIPT}")
        return 1

    try:
        payload = json.loads(check.stdout)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] failed to parse quality JSON: {exc}")
        return 1

    quality = payload.get("quality", {}) if isinstance(payload, dict) else {}
    check_errors = payload.get("errors", []) if isinstance(payload, dict) else []
    if not isinstance(check_errors, list):
        check_errors = [str(check_errors)]

    allowlist, allowlist_errors = _build_conflict_allowlist(args.conflict_allowlist)
    policy, policy_errors = _load_policy(args.quality_policy)

    thresholds, threshold_errors = _load_thresholds(policy, args)

    conflicts, active_counts = _filter_conflicts(quality, allowlist)
    quality["route_conflicts"] = conflicts
    all_errors = list(map(str, [*check_errors, *allowlist_errors, *policy_errors, *threshold_errors]))

    if isinstance(quality, dict):
        all_errors.extend(_evaluate_thresholds(quality, {
            "duplicate_patterns": active_counts["route_conflicts"]["duplicate_patterns"],
            "weak_strong_overlaps": active_counts["route_conflicts"]["weak_strong_overlaps"],
            "broad_patterns": active_counts["route_conflicts"]["broad_patterns"],
            "multi_match_fixtures": active_counts["route_conflicts"]["multi_match_fixtures"],
        }, thresholds))

    result = {
        "valid": check.returncode == 0 and not all_errors,
        "errors": all_errors,
        "quality": quality,
        "thresholds": thresholds,
        "policy": policy,
    }

    payload["errors"] = all_errors
    payload["valid"] = result["valid"]
    payload["quality"]["route_conflicts"] = conflicts

    if args.artifact:
        try:
            args.artifact.parent.mkdir(parents=True, exist_ok=True)
            args.artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            print(f"[ERROR] failed to write artifact to {args.artifact}: {exc}")
            return 1

    if result["valid"]:
        print("[PASS] log symptom routes quality gate")
        return 0

    print("[FAIL] log symptom routes quality gate:")
    for error in all_errors:
        print(f"  - {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())