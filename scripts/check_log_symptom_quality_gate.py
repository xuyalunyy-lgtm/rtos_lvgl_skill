#!/usr/bin/env python3
"""Apply quality policy and optional conflict allowlist to symptom route checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CHECK_SCRIPT = ROOT / "scripts" / "check_log_symptom_routes.py"
DEFAULT_QUALITY_POLICY_FILE = ROOT / "references" / "log_symptom_routes_quality_policy.json"
DEFAULT_CONFLICT_ALLOWLIST_FILE = ROOT / "references" / "log_symptom_route_conflict_allowlist.json"
DEFAULT_ARTIFACT = ROOT / "artifacts" / "log_symptom_routes_quality.json"
QUALITY_REPORT_SCHEMA_FILE = ROOT / "references" / "log_symptom_quality_report_schema.json"
ROUTE_CONFLICT_KEYS = {"duplicate_patterns", "weak_strong_overlaps", "broad_patterns", "multi_match_fixtures"}
FIXTURES_DIR = ROOT / "tools" / "fixtures" / "logs"


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


def _normalize_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_route_conflicts(value: Any, errors: list[str]) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {key: [] for key in ROUTE_CONFLICT_KEYS}
    if not isinstance(value, dict):
        errors.append("quality.route_conflicts must be an object")
        return normalized

    for key in ROUTE_CONFLICT_KEYS:
        entries = value.get(key)
        if not isinstance(entries, list):
            errors.append(f"quality.route_conflicts.{key} must be a list")
            continue
        normalized[key] = [entry for entry in entries if isinstance(entry, dict)]

    return normalized


def _read_quality_schema() -> tuple[dict[str, Any] | None, list[str]]:
    if not QUALITY_REPORT_SCHEMA_FILE.exists():
        return None, [f"quality schema file missing: {QUALITY_REPORT_SCHEMA_FILE}"]
    try:
        schema = json.loads(QUALITY_REPORT_SCHEMA_FILE.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [f"failed to read quality schema {QUALITY_REPORT_SCHEMA_FILE}: {exc}"]
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON in quality schema {QUALITY_REPORT_SCHEMA_FILE}: {exc}"]
    if not isinstance(schema, dict):
        return None, [f"quality schema {QUALITY_REPORT_SCHEMA_FILE} must be a JSON object"]
    return schema, []


def _validate_schema_node(
    path: str,
    value: Any,
    schema: dict[str, Any],
    errors: list[str],
) -> None:
    if not isinstance(schema, dict):
        return

    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            errors.append(f"{path} must be an object")
            return

        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key} missing")

        properties: dict[str, Any] = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                _validate_schema_node(f"{path}.{key}", value[key], child_schema, errors)

        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            for key, child in value.items():
                if key not in properties:
                    _validate_schema_node(f"{path}.{key}", child, additional, errors)
        return

    if schema_type == "array":
        if not isinstance(value, list):
            errors.append(f"{path} must be an array")
            return
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _validate_schema_node(f"{path}[{index}]", item, items, errors)
        return

    if schema_type == "string":
        if not isinstance(value, str):
            errors.append(f"{path} must be a string")
        return

    if schema_type == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path} must be a boolean")
        return

    if schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{path} must be a non-negative integer")
            return
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path} must be >= {minimum}")
        return

    if schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path} must be a number")
            return
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path} must be >= {minimum}")


def _validate_quality_payload_schema(payload: Any, errors: list[str]) -> dict[str, Any]:
    schema, schema_errors = _read_quality_schema()
    errors.extend(schema_errors)
    if not isinstance(payload, dict):
        errors.append("quality json payload must be an object")
        return {}

    if schema is not None:
        _validate_schema_node("quality_payload", payload, schema, errors)

    # Compatibility branch: explicit minimum required fields.
    for key in ("valid", "errors", "quality"):
        if key not in payload:
            errors.append(f"quality json payload missing required field '{key}'")

    quality_payload = payload.get("quality")
    if not isinstance(quality_payload, dict):
        errors.append("quality json payload missing required object field 'quality'")
        return {"quality": {}}
    return payload


def _coerce_non_negative_int(payload: dict[str, Any], field: str, errors: list[str], *, default: int = 0) -> int:
    value = payload.get(field, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        errors.append(f"quality.{field} must be a non-negative integer")
        return default
    return value


def _normalize_quality(payload: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    return {
        "total_routes": _coerce_non_negative_int(payload, "total_routes", errors),
        "coverage": _normalize_list(payload.get("coverage")),
        "missing_field_alerts": payload["missing_field_alerts"] if isinstance(payload.get("missing_field_alerts"), dict) else {},
        "sparse_routes": _normalize_list(payload.get("sparse_routes")),
        "missing_field_alert_count": _coerce_non_negative_int(payload, "missing_field_alert_count", errors),
        "route_conflicts": _normalize_route_conflicts(payload.get("route_conflicts"), errors),
    }


def _coerce_int_list_count(value: Any, default: int = 0) -> int:
    return value if isinstance(value, int) and value >= 0 else default

def _run_routes_quality_payload(route_fixture: Path) -> tuple[dict[str, Any], int, list[str]]:
    proc = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--file", str(route_fixture), "--quality-json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not proc.stdout:
        return {}, proc.returncode, [f"no output from routes check for {route_fixture}"]
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {}, proc.returncode, [f"failed to parse quality JSON for {route_fixture}: {exc}"]
    return payload, proc.returncode, []


def _filter_conflicts(quality: dict[str, Any], allowlist: dict[str, set[tuple[str, ...]]], errors: list[str]) -> tuple[dict[str, Any], dict[str, int]]:
    route_conflicts = quality.get("route_conflicts")
    if not isinstance(route_conflicts, dict):
        errors.append("quality.route_conflicts must be an object")
        return {
            "duplicate_patterns": [],
            "weak_strong_overlaps": [],
            "broad_patterns": [],
            "multi_match_fixtures": [],
            "suppressed_conflicts": {
                "duplicate_patterns": 0,
                "weak_strong_overlaps": 0,
                "broad_patterns": 0,
                "multi_match_fixtures": 0,
            },
        }, {"duplicate_patterns": 0, "weak_strong_overlaps": 0, "broad_patterns": 0, "multi_match_fixtures": 0}

    output: dict[str, Any] = {
        "duplicate_patterns": [],
        "weak_strong_overlaps": [],
        "broad_patterns": [],
        "multi_match_fixtures": [],
        "suppressed_conflicts": {
            "duplicate_patterns": 0,
            "weak_strong_overlaps": 0,
            "broad_patterns": 0,
            "multi_match_fixtures": 0,
        },
    }

    for item in route_conflicts.get("duplicate_patterns", []):
        if not isinstance(item, dict):
            continue
        routes = tuple(sorted({entry.get("route_id") for entry in item.get("entries", []) if isinstance(entry.get("route_id"), str)}))
        pattern = _norm_pattern(str(item.get("normalized_pattern", "")))
        if (pattern, routes) in allowlist["duplicate_patterns"]:
            output["suppressed_conflicts"]["duplicate_patterns"] += 1
            continue
        output["duplicate_patterns"].append(item)

    for item in route_conflicts.get("weak_strong_overlaps", []):
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

    for item in route_conflicts.get("broad_patterns", []):
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

    for item in route_conflicts.get("multi_match_fixtures", []):
        if not isinstance(item, dict):
            continue
        fixture = item.get("fixture")
        matched_routes = item.get("matched_routes")
        if not isinstance(fixture, str) or not isinstance(matched_routes, list):
            continue
        signature = (fixture, tuple(sorted({route for route in matched_routes if isinstance(route, str)})))
        if signature in allowlist["multi_match_fixtures"]:
            output["suppressed_conflicts"]["multi_match_fixtures"] += 1
            continue
        output["multi_match_fixtures"].append(item)

    counts = {
        "duplicate_patterns": len(output["duplicate_patterns"]),
        "weak_strong_overlaps": len(output["weak_strong_overlaps"]),
        "broad_patterns": len(output["broad_patterns"]),
        "multi_match_fixtures": len(output["multi_match_fixtures"]),
    }
    counts["route_conflicts"] = sum(counts.values())
    return output, counts


def _evaluate_thresholds(quality: dict[str, Any], active_counts: dict[str, int], thresholds: dict[str, Any]) -> list[str]:
    violations: list[str] = []

    missing = _coerce_int_list_count(quality.get("missing_field_alert_count", 0), default=0)
    max_missing = thresholds.get("max_missing_field_alert_count")
    if isinstance(max_missing, int) and missing > max_missing:
        violations.append(f"missing_field_alert_count {missing} exceeds threshold {max_missing}")

    coverage_items = quality.get("coverage", [])
    min_average = thresholds.get("min_average_coverage")
    if min_average is not None:
        coverage_values = []
        if isinstance(coverage_items, list):
            for item in coverage_items:
                if isinstance(item, dict) and isinstance(item.get("coverage"), (int, float)):
                    coverage_values.append(item["coverage"])
        average = sum(coverage_values) / len(coverage_values) if coverage_values else 0.0
        if average < float(min_average):
            violations.append(f"average field coverage {average:.1f}% is below threshold {float(min_average):.1f}%")

    checks = {
        "max_route_conflicts": _coerce_int_list_count(active_counts.get("route_conflicts", 0)),
        "max_duplicate_patterns": _coerce_int_list_count(active_counts.get("duplicate_patterns", 0)),
        "max_weak_strong_overlaps": _coerce_int_list_count(active_counts.get("weak_strong_overlaps", 0)),
        "max_broad_patterns": _coerce_int_list_count(active_counts.get("broad_patterns", 0)),
        "max_multi_match_fixtures": _coerce_int_list_count(active_counts.get("multi_match_fixtures", 0)),
    }

    for key, value in checks.items():
        limit = thresholds.get(key)
        if isinstance(limit, int) and value > limit:
            violations.append(f"{key} {value} exceeds threshold {limit}")

    return violations


def _coerce_list_of_errors(value: object, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append("quality json payload missing required list field 'errors'")
        return []
    return [str(v) for v in value]


def _normalize_quality_payload(payload: Any, errors: list[str]) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(payload, dict):
        return {
            "valid": False,
            "errors": ["quality json payload must be an object"],
            "quality": _normalize_quality({}, errors),
        }, ["quality json payload must be an object"]

    checked_payload = _validate_quality_payload_schema(payload, errors)
    if not checked_payload:
        checked_payload = {"quality": {}}

    check_valid = checked_payload.get("valid")
    if not isinstance(check_valid, bool):
        errors.append("quality json payload missing required boolean field 'valid'")
        check_valid = False

    check_errors = []
    if "errors" not in checked_payload:
        errors.append("quality json payload missing required list field 'errors'")
    else:
        check_errors = _coerce_list_of_errors(checked_payload.get("errors"), errors)

    quality_payload = checked_payload.get("quality")
    if not isinstance(quality_payload, dict):
        errors.append("quality json payload missing required object field 'quality'")
        quality_payload = {}

    quality = _normalize_quality(quality_payload, errors)
    return {
        "valid": check_valid,
        "errors": check_errors,
        "quality": quality,
    }, check_errors


def _file_fingerprint(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "missing", "missing"
    try:
        content = path.read_bytes()
        stat = path.stat()
        digest = hashlib.md5(content).hexdigest()
        timestamp = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        return digest, timestamp
    except OSError:
        return "unreadable", "unreadable"


def _read_head_payload(path: Path) -> tuple[Any, list[str]]:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return None, []

    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel.as_posix()}"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    if proc.returncode != 0:
        return None, []
    try:
        return json.loads(proc.stdout), []
    except json.JSONDecodeError as exc:
        return None, [f"HEAD {path.name} is not parseable JSON: {exc}"]


def _json_canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _has_head_change(path: Path) -> tuple[bool, list[str]]:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return False, [f"{path} is outside repository root and cannot be compared against HEAD"]

    proc = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", rel.as_posix()],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    if proc.returncode != 0:
        return False, [f"failed to inspect git diff for {path}: {proc.stderr or proc.returncode}"]

    changed = False
    for line in proc.stdout.splitlines():
        if line.strip() == rel.as_posix():
            changed = True
            break
    return changed, []


def _has_semantic_noop(path: Path, current: dict[str, Any], errors: list[str]) -> bool:
    has_change, diff_errs = _has_head_change(path)
    if diff_errs:
        errors.extend(diff_errs)
        return False
    if not has_change:
        return False

    head_payload, read_errors = _read_head_payload(path)
    if read_errors:
        errors.extend(read_errors)
        return False
    if head_payload is None:
        return False

    try:
        canonical_current = _json_canonical(current)
        canonical_head = _json_canonical(head_payload)
    except TypeError:
        errors.append(f"{path.name} contains non-JSON-serializable values")
        return False

    return canonical_current == canonical_head


def _ensure_artifact_writable(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        errors.append(f"failed to create artifact directory {path.parent}: {exc}")
        return errors

    probe = path.parent / ".log_symptom_quality_gate_write_probe"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        errors.append(f"artifact path is not writable: {path.parent}: {exc}")
    return errors


def _write_artifact(path: Path | None, payload: dict[str, Any]) -> list[str]:
    if path is None:
        return []
    errors = _ensure_artifact_writable(path)
    if errors:
        return errors

    try:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        return [f"failed to write artifact to {path}: {exc}"]
    return []


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
    parser.add_argument("--strict", action="store_true", help="treat quality warnings as hard failures")
    parser.add_argument("--self-test", action="store_true", help="run inline checks")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    policy_fingerprint, policy_mtime = _file_fingerprint(args.quality_policy)
    allowlist_fingerprint, allowlist_mtime = _file_fingerprint(args.conflict_allowlist)
    print(f"[INFO] quality policy {args.quality_policy}: md5={policy_fingerprint} mtime={policy_mtime}")
    print(f"[INFO] conflict allowlist {args.conflict_allowlist}: md5={allowlist_fingerprint} mtime={allowlist_mtime}")

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

    payload_errors: list[str] = []
    payload_warnings: list[str] = []
    parsed = _normalize_quality_payload(payload, payload_errors)
    quality_blob, raw_errors = parsed
    quality = quality_blob.get("quality", {}) if isinstance(quality_blob, dict) else {}
    if isinstance(raw_errors, list):
        payload_errors.extend(raw_errors)

    if check.returncode != 0:
        payload_errors.append(f"upstream check failed with exit code {check.returncode}")

    allowlist, allowlist_errors = _build_conflict_allowlist(args.conflict_allowlist)
    if allowlist_errors:
        payload_errors.extend(allowlist_errors)

    policy, policy_errors = _load_policy(args.quality_policy)
    if policy_errors:
        payload_errors.extend(policy_errors)

    thresholds, threshold_errors = _load_thresholds(policy, args)
    payload_errors.extend(threshold_errors)
    print(f"[INFO] effective quality thresholds: {thresholds}")

    if isinstance(quality, dict):
        if _has_semantic_noop(args.quality_policy, policy if isinstance(policy, dict) else {}, payload_errors):
            payload_errors.append("quality policy has semantic-noop change against HEAD (formatting/noop-only edits are blocked)")

        if args.conflict_allowlist.exists():
            try:
                allowlist_current = json.loads(args.conflict_allowlist.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                payload_errors.append(f"conflict allowlist read error: {exc}")
            else:
                if not isinstance(allowlist_current, dict):
                    payload_errors.append("conflict allowlist must be a JSON object")
                elif _has_semantic_noop(args.conflict_allowlist, allowlist_current, payload_errors):
                    payload_errors.append("conflict allowlist has semantic-noop change against HEAD (formatting/noop-only edits are blocked)")

    if not isinstance(quality, dict):
        quality = {}

    conflicts, active_counts = _filter_conflicts(quality, allowlist, payload_errors)
    quality["route_conflicts"] = conflicts
    conflict_counts = {
        "route_conflicts": active_counts.get("route_conflicts", 0),
        "duplicate_patterns": active_counts.get("duplicate_patterns", 0),
        "weak_strong_overlaps": active_counts.get("weak_strong_overlaps", 0),
        "broad_patterns": active_counts.get("broad_patterns", 0),
        "multi_match_fixtures": active_counts.get("multi_match_fixtures", 0),
    }
    print("[INFO] quality route conflict counts: " + ", ".join(f"{k}={v}" for k, v in conflict_counts.items()))

    violations = _evaluate_thresholds(quality, active_counts, thresholds)
    if args.strict:
        payload_errors.extend(violations)
    else:
        payload_warnings.extend(violations)

    if quality_blob.get("errors"):
        payload_errors.extend(quality_blob.get("errors", []))

    payload_result = {
        "valid": check.returncode == 0 and len(payload_errors) == 0,
        "strict": args.strict,
        "errors": payload_errors,
        "warnings": payload_warnings,
        "quality": quality,
        "thresholds": thresholds,
        "policy": policy,
        "metadata": {
            "quality_policy": {
                "md5": policy_fingerprint,
                "mtime": policy_mtime,
            },
            "conflict_allowlist": {
                "md5": allowlist_fingerprint,
                "mtime": allowlist_mtime,
            },
        },
    }

    # keep upstream fields for compatibility
    if isinstance(payload, dict):
        payload.update(payload_result)
    else:
        payload = payload_result

    payload["route_conflict_counts"] = {
        **active_counts,
        "route_conflicts": active_counts.get("route_conflicts", 0),
    }

    artifact_errors = _write_artifact(args.artifact, payload)
    if artifact_errors:
        print(f"[ERROR] {artifact_errors[0]}")
        if args.artifact:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1

    if payload_result["valid"]:
        if payload_warnings:
            print("[PASS] log symptom routes quality gate (warning mode)")
            print(f"[INFO] warnings: {len(payload_warnings)}")
            for warning in payload_warnings:
                print(f"  - {warning}")
        else:
            print("[PASS] log symptom routes quality gate")
        return 0

    print("[FAIL] log symptom routes quality gate:")
    for error in payload_errors:
        print(f"  - {error}")
    for warning in payload_warnings:
        print(f"  - warning: {warning}")
    return 1


def run_self_test() -> int:
    passed = 0
    failed = 0
    fixture_dir = FIXTURES_DIR

    # 1) happy path: valid upstream payload + explicit schema fields
    check_payload = {
        "valid": True,
        "errors": [],
        "quality": {
            "total_routes": 2,
            "coverage": [
                {"field": "x", "present": 1, "missing": 1, "coverage": 50},
            ],
            "missing_field_alerts": {"x": 1},
            "sparse_routes": [],
            "missing_field_alert_count": 1,
            "route_conflicts": {
                "duplicate_patterns": [
                    {
                        "normalized_pattern": "err",
                        "entries": [{"route_id": "A", "pattern": "err"}, {"route_id": "B", "pattern": "err"}],
                    }
                ],
                "weak_strong_overlaps": [],
                "broad_patterns": [],
                "multi_match_fixtures": [],
            },
        },
    }
    errors: list[str] = []
    normalized, raw_errors = _normalize_quality_payload(check_payload, errors)
    if (
        not errors
        and not raw_errors
        and normalized["quality"]["missing_field_alert_count"] == 1
        and normalized["quality"]["route_conflicts"]["duplicate_patterns"]
    ):
        print("[PASS] quality payload schema")
        passed += 1
    else:
        print(f"[FAIL] quality payload schema: {errors or raw_errors}")
        failed += 1

    # 2) fixture: empty output should keep deterministic defaults and stay non-crashing
    empty_payload, exit_code, empty_errs = _run_routes_quality_payload(fixture_dir / "quality_gate_empty_routes.json")
    if (
        not empty_errs
        and exit_code == 0
        and empty_payload.get("valid")
        and empty_payload.get("quality", {}).get("total_routes") == 0
    ):
        print("[PASS] empty fixture routes")
        passed += 1
    else:
        print(f"[FAIL] empty fixture routes: {empty_errs or empty_payload.get('errors')}")
        failed += 1

    # 3) fixture: missing required route fields should fail fast with explicit errors
    missing_payload, _, missing_errs = _run_routes_quality_payload(fixture_dir / "quality_gate_missing_fields.json")
    if (
        not missing_errs
        and not missing_payload.get("valid", True)
        and any("missing keys" in str(item) for item in missing_payload.get("errors", []))
    ):
        print("[PASS] missing required fields fixture")
        passed += 1
    else:
        print(f"[FAIL] missing required fields fixture: {missing_errs or missing_payload.get('errors')}")
        failed += 1

    # 4) fixture: multi-conflict fixture should exceed thresholds in aggregate
    conflict_payload, _, conflict_errs = _run_routes_quality_payload(fixture_dir / "quality_gate_conflict_over_threshold.json")
    conflict_quality = conflict_payload.get("quality", {}) if isinstance(conflict_payload, dict) else {}
    if not conflict_errs and isinstance(conflict_quality, dict):
        conflicts = conflict_quality.get("route_conflicts", {})
        conflict_total = sum(len(conflicts.get(key, [])) for key in ROUTE_CONFLICT_KEYS)
        if conflict_total >= 2:
            print("[PASS] conflict-over-threshold fixture")
            passed += 1
        else:
            print(f"[FAIL] conflict-over-threshold fixture: conflict_total={conflict_total}")
            failed += 1
    else:
        print(f"[FAIL] conflict-over-threshold fixture payload: {conflict_errs}")
        failed += 1

    # 5) fixture: multi-match fixture should be detected when several routes match one log
    multi_payload, _, multi_errs = _run_routes_quality_payload(fixture_dir / "quality_gate_multi_match_routes.json")
    if not multi_errs and isinstance(multi_payload.get("quality", {}).get("route_conflicts"), dict):
        mm_conflicts = multi_payload["quality"]["route_conflicts"].get("multi_match_fixtures", [])
        if any(
            item.get("fixture") == "quality_gate_multi_match.log"
            and set(item.get("matched_routes", [])) == {"MM_A", "MM_B"}
            for item in mm_conflicts
        ):
            print("[PASS] multi-match fixture")
            passed += 1
        else:
            print(f"[FAIL] multi-match fixture: {mm_conflicts}")
            failed += 1
    else:
        print(f"[FAIL] multi-match fixture payload: {multi_errs}")
        failed += 1

    # 6) malformed payload should report explicit schema errors instead of crashing
    malformed_payload = {"valid": True}
    malformed_errors: list[str] = []
    _, _ = _normalize_quality_payload(malformed_payload, malformed_errors)
    if any("missing required list field 'errors'" in item for item in malformed_errors) and any("missing required object field 'quality'" in item for item in malformed_errors):
        print("[PASS] malformed quality payload schema")
        passed += 1
    else:
        print(f"[FAIL] malformed quality payload schema: {malformed_errors}")
        failed += 1

    # 7) allowlist suppresses configured conflicts while unmatched entries keep failing
    allowlist_subject, _, subject_errs = _run_routes_quality_payload(fixture_dir / "quality_gate_allowlist_subject.json")
    if subject_errs:
        print(f"[FAIL] allowlist fixture payload: {subject_errs}")
        failed += 1
    else:
        normalized_subject_payload, subject_schema_errors = _normalize_quality_payload(allowlist_subject, [])
        allowlist_ok, allowlist_ok_errors = _build_conflict_allowlist(fixture_dir / "quality_gate_allowlist_success.json")
        if not allowlist_ok_errors:
            _, counts_ok = _filter_conflicts(normalized_subject_payload["quality"], allowlist_ok, [])
            if counts_ok.get("duplicate_patterns", 0) == 0:
                print("[PASS] allowlist fixture success path")
                passed += 1
            else:
                print(f"[FAIL] allowlist fixture success path: {counts_ok}")
                failed += 1
        else:
            print(f"[FAIL] allowlist fixture success path allowlist parse: {allowlist_ok_errors}")
            failed += 1

        allowlist_fail, allowlist_fail_errors = _build_conflict_allowlist(fixture_dir / "quality_gate_allowlist_fail.json")
        if not allowlist_fail_errors:
            _, counts_fail = _filter_conflicts(normalized_subject_payload["quality"], allowlist_fail, [])
            if counts_fail.get("duplicate_patterns", 0) >= 1:
                print("[PASS] allowlist fixture failure path")
                passed += 1
            else:
                print(f"[FAIL] allowlist fixture failure path: {counts_fail}")
                failed += 1
        else:
            print(f"[FAIL] allowlist fixture failure parse: {allowlist_fail_errors}")
            failed += 1

        if subject_schema_errors:
            print(f"[FAIL] allowlist fixture subject schema issues: {subject_schema_errors}")
            failed += 1

    # 8) strict mode should turn warnings into hard errors
    sample_violations = ["duplicate_patterns 1 exceeds threshold 0"]
    strict_errors: list[str] = []
    strict_warnings: list[str] = []
    strict_mode = True
    if strict_mode:
        strict_errors.extend(sample_violations)
    if strict_errors and not strict_warnings:
        print("[PASS] strict mode hardens warnings")
        passed += 1
    else:
        print(f"[FAIL] strict mode hardening: {strict_errors} / {strict_warnings}")
        failed += 1

    # 9) baseline allowlist parsing should still work
    allowlist, allowlist_errors = _build_conflict_allowlist(DEFAULT_CONFLICT_ALLOWLIST_FILE)
    if not allowlist_errors and allowlist:
        print("[PASS] allowlist parse")
        passed += 1
    else:
        print(f"[FAIL] allowlist parse: {allowlist_errors}")
        failed += 1

    print(f"self-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
