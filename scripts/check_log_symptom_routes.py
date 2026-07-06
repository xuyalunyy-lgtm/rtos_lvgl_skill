#!/usr/bin/env python3
"""Validate log symptom route definitions used by the triage engine."""
from __future__ import annotations

import argparse
import codecs
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ROUTES_FILE = ROOT / "references" / "log_symptom_routes.json"
TOOLS_DIR = ROOT / "tools"
LOGS_DIR = TOOLS_DIR / "fixtures" / "logs"

VALID_CATEGORIES = {"software", "hardware", "architecture", "mixed"}
VALID_SEVERITIES = {"P0", "P1", "P2", "P3", "P4", "P5"}
VALID_MATCH_LEVELS = {"error", "raw_boot", "all"}

REQUIRED_FIELDS = {"id", "name", "patterns", "category", "severity", "constraints"}
OPTIONAL_FIELDS = {
    "recommended_commands",
    "natural_patterns",
    "weak_patterns",
    "checker_targets",
    "architecture_flags",
    "diagnostic_probes",
    "do_not_patch_until",
    "hardware_challenge",
    "log_signals",
    "missing_facts",
    "verify_steps",
    "architecture_refactor",
    "root_cause_hints",
    "stop_conditions",
    "match_level",
}
DIAGNOSTIC_PROBE_KEYS = {"log_confirm", "code_locate", "tool_verify"}

def _build_quality_report(symptoms: list[dict[str, Any]]) -> dict[str, Any]:
    """Build optional-field coverage / missing-field alert metrics.

    This is non-blocking metadata used to spot data quality gaps over time.
    """
    total = len(symptoms)
    if total == 0:
        return {
            "total_routes": 0,
            "coverage": [],
            "missing_field_alerts": {},
            "sparse_routes": [],
            "missing_field_alert_count": 0,
            "route_conflicts": _build_conflict_report([]),
        }

    missing_field_alerts: dict[str, int] = {field: 0 for field in OPTIONAL_FIELDS}
    presence_counts: dict[str, int] = {field: 0 for field in OPTIONAL_FIELDS}
    sparse_routes: list[tuple[str, int, list[str]]] = []

    for route in symptoms:
        route_id = route.get("id")
        route_key = route_id if isinstance(route_id, str) and route_id else "<missing_id>"
        missing_fields: list[str] = []

        for field in OPTIONAL_FIELDS:
            if field in route:
                presence_counts[field] += 1
            else:
                missing_field_alerts[field] += 1
                missing_fields.append(field)

        if missing_fields:
            sparse_routes.append((route_key, len(missing_fields), missing_fields))

    coverage = []
    for field in sorted(OPTIONAL_FIELDS):
        present = presence_counts[field]
        missing = missing_field_alerts[field]
        coverage.append({
            "field": field,
            "present": present,
            "missing": missing,
            "coverage": (present / total) * 100,
        })

    return {
        "total_routes": total,
        "coverage": coverage,
        "missing_field_alerts": dict(sorted(missing_field_alerts.items(), key=lambda item: item[0])),
        "sparse_routes": sorted(
            sparse_routes,
            key=lambda item: item[1],
            reverse=True,
        ),
        "missing_field_alert_count": sum(missing_field_alerts.values()),
        "route_conflicts": _build_conflict_report(symptoms),
    }




def _route_id(route: dict[str, Any]) -> str:
    route_id = route.get("id")
    return route_id if isinstance(route_id, str) and route_id else "<missing_id>"


def _normalized_pattern(pattern: str) -> str:
    return re.sub(r"\s+", " ", pattern.casefold()).strip()


def _literal_pattern_text(pattern: str) -> str:
    text = re.sub(r"\\[AbBdDsSwWZz]", "", pattern)
    return re.sub(r"[^0-9A-Za-z_\u0080-\uffff]+", "", text)


def _iter_string_entries(symptoms: list[dict[str, Any]], field: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for route in symptoms:
        value = route.get(field)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, str) and item.strip():
                entries.append((_route_id(route), item))
    return entries


def _match_route_against_text(route: dict[str, Any], text: str) -> bool:
    match_level = route.get("match_level", "error")
    patterns = route.get("patterns", [])
    if not isinstance(patterns, list):
        return False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        level_match = re.search(r"^([DIWEF])\s*\(", line)
        level = level_match.group(1) if level_match else ""
        is_raw = bool(re.search(r"^(ets_|rst:|boot:|ROM:|pc=|lr=|EXC_RETURN)", line))

        if match_level == "error" and level not in ("E", "F"):
            continue
        if match_level == "raw_boot" and not is_raw and level not in ("I", "W", "E", "F"):
            continue

        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                continue
            try:
                if re.search(pattern, line, re.IGNORECASE):
                    return True
            except re.error:
                continue
    return False


def _build_fixture_multi_match_report(symptoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not LOGS_DIR.exists():
        return []

    reports: list[dict[str, Any]] = []
    for log_file in sorted(LOGS_DIR.glob("*.log")):
        try:
            text = log_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matched = sorted({
            _route_id(route)
            for route in symptoms
            if _match_route_against_text(route, text)
        })
        if len(matched) > 1:
            reports.append({"fixture": log_file.name, "matched_routes": matched})
    return reports


def _build_conflict_report(symptoms: list[dict[str, Any]]) -> dict[str, Any]:
    pattern_map: dict[str, list[dict[str, str]]] = {}
    for route_id, pattern in _iter_string_entries(symptoms, "patterns"):
        key = _normalized_pattern(pattern)
        pattern_map.setdefault(key, []).append({"route_id": route_id, "pattern": pattern})

    duplicate_patterns = [
        {"normalized_pattern": key, "entries": entries}
        for key, entries in sorted(pattern_map.items())
        if len({entry["route_id"] for entry in entries}) > 1 or len(entries) > 1
    ]

    strong_patterns = {
        _normalized_pattern(pattern): {"route_id": route_id, "pattern": pattern}
        for route_id, pattern in _iter_string_entries(symptoms, "patterns")
    }
    weak_strong_overlaps = []
    for route_id, weak_pattern in _iter_string_entries(symptoms, "weak_patterns"):
        key = _normalized_pattern(weak_pattern)
        strong = strong_patterns.get(key)
        if strong:
            weak_strong_overlaps.append({
                "weak_route_id": route_id,
                "strong_route_id": strong["route_id"],
                "pattern": weak_pattern,
            })

    broad_tokens = {"error", "fail", "failed", "failure", "timeout", "exception", "panic"}
    broad_patterns = []
    for route_id, pattern in _iter_string_entries(symptoms, "patterns"):
        literal = _literal_pattern_text(pattern).casefold()
        if len(literal) < 3 or literal in broad_tokens:
            broad_patterns.append({
                "route_id": route_id,
                "pattern": pattern,
                "reason": "short_or_generic_literal",
            })

    return {
        "duplicate_patterns": duplicate_patterns,
        "weak_strong_overlaps": weak_strong_overlaps,
        "broad_patterns": broad_patterns,
        "multi_match_fixtures": _build_fixture_multi_match_report(symptoms),
    }


def _print_quality_report(payload: dict[str, Any]) -> None:
    symptoms = payload.get("symptoms")
    if not isinstance(symptoms, list):
        return

    typed_symptoms = [r for r in symptoms if isinstance(r, dict)]
    report = _build_quality_report(typed_symptoms)

    if report["total_routes"] == 0:
        print("[WARN] route metadata quality: no symptom entries found")
        return

    print("[INFO] route metadata quality report")
    print(f"  total routes: {report['total_routes']}")
    print(f"  optional-field missing alerts: {report['missing_field_alert_count']}")
    print("  field coverage:")
    for item in report["coverage"]:
        print(
            "    - {field}: present={present}/{total} missing={missing} coverage={coverage:.1f}%".format(
                total=report["total_routes"],
                **item,
            )
        )

    top_sparse_routes = [
        item for item in report["sparse_routes"] if item[1] > 0
    ]
    if top_sparse_routes:
        print("  routes with missing optional fields (top 5 by count):")
        for route_id, missing_count, _missing_fields in top_sparse_routes[:5]:
            print(f"    - {route_id}: missing {missing_count} optional fields")

    conflicts = report["route_conflicts"]
    conflict_count = sum(len(conflicts[key]) for key in conflicts)
    print(f"  route conflict hints: {conflict_count}")
    if conflict_count:
        print("  conflict hint summary:")
        for key in sorted(conflicts):
            print(f"    - {key}: {len(conflicts[key])}")
        for item in conflicts["duplicate_patterns"][:3]:
            routes = sorted({entry["route_id"] for entry in item["entries"]})
            print(f"    - duplicate pattern {item['normalized_pattern']!r}: {routes}")
        for item in conflicts["multi_match_fixtures"][:3]:
            print(f"    - fixture {item['fixture']}: {item['matched_routes']}")


def _list_checker_modules() -> set[str]:
    return {
        file.stem
        for file in TOOLS_DIR.glob("*_checker.py")
        if file.name != "__init__.py"
    }


def _has_suspicious_text(value: str) -> bool:
    return "\uFFFD" in value or "??" in value


def _validate_required_keys(route: dict[str, object], route_id: str, errors: list[str]) -> None:
    missing = sorted(REQUIRED_FIELDS - route.keys())
    if missing:
        errors.append(f"{route_id}: missing keys: {', '.join(missing)}")

    unknown = sorted(set(route.keys()) - (REQUIRED_FIELDS | OPTIONAL_FIELDS))
    if unknown:
        errors.append(f"{route_id}: unknown keys: {', '.join(unknown)}")


def _validate_str_list(route_id: str, field: str, value: object, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{route_id}: {field} must be a list")
        return
    if not value:
        errors.append(f"{route_id}: {field} must not be empty")
        return
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{route_id}: {field} entries must be non-empty strings")
            break
        if _has_suspicious_text(item):
            errors.append(f"{route_id}: {field} contains suspicious text markers")
            break


def _validate_checker_targets(route_id: str, value: object, checker_modules: set[str], errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{route_id}: checker_targets must be a list")
        return
    if not value:
        return
    for checker in value:
        if not isinstance(checker, str) or not checker.strip():
            errors.append(f"{route_id}: checker_targets entries must be non-empty strings")
            continue
        if checker not in checker_modules:
            errors.append(f"{route_id}: unknown checker target: {checker}")


def _validate_diagnostic_probes(route_id: str, value: object, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{route_id}: diagnostic_probes must be an object")
        return

    missing = DIAGNOSTIC_PROBE_KEYS - set(value.keys())
    if missing:
        errors.append(f"{route_id}: diagnostic_probes missing keys: {', '.join(sorted(missing))}")

    for key in DIAGNOSTIC_PROBE_KEYS:
        if key not in value:
            continue
        section = value.get(key)
        if not isinstance(section, list) or not section:
            errors.append(f"{route_id}: diagnostic_probes.{key} must be a non-empty list")
            continue
        for item in section:
            if not isinstance(item, str) or not item.strip():
                errors.append(f"{route_id}: diagnostic_probes.{key} entries must be non-empty strings")
                break
            if _has_suspicious_text(item):
                errors.append(f"{route_id}: diagnostic_probes.{key} contains suspicious text markers")
                break


def _validate_fields(route: dict[str, object], checker_modules: set[str], errors: list[str]) -> None:
    route_id = route.get("id", "<missing>")
    if not isinstance(route_id, str) or not route_id:
        errors.append(f"{route_id}: id must be a non-empty string")
        return

    if not re.fullmatch(r"[A-Z0-9_]+", route_id):
        errors.append(f"{route_id}: id must match [A-Z0-9_]+")

    _validate_required_keys(route, route_id, errors)

    category = route.get("category")
    if category not in VALID_CATEGORIES:
        errors.append(f"{route_id}: invalid category: {category!r}")

    severity = route.get("severity")
    if severity not in VALID_SEVERITIES:
        errors.append(f"{route_id}: invalid severity: {severity!r}")

    patterns = route.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        errors.append(f"{route_id}: patterns must be a non-empty list")
    else:
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                errors.append(f"{route_id}: each pattern must be a non-empty string")
                continue
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                errors.append(f"{route_id}: invalid regex pattern {pattern!r}: {exc}")

    constraints = route.get("constraints")
    if not isinstance(constraints, list) or not constraints:
        errors.append(f"{route_id}: constraints must be a non-empty list")
    else:
        for item in constraints:
            if not isinstance(item, str):
                errors.append(f"{route_id}: constraints entries must be strings")
                continue
            if not re.fullmatch(r"C\d+", item):
                errors.append(f"{route_id}: invalid constraint format: {item!r}")

    for field in ("id", "name", "category", "severity", "match_level", "do_not_patch_until"):
        if field in route:
            value = route.get(field)
            if not isinstance(value, str) or not value.strip():
                if field == "do_not_patch_until":
                    # allowed empty string as an explicit placeholder
                    continue
                errors.append(f"{route_id}: {field} must be a non-empty string")
                continue
            if _has_suspicious_text(value):
                errors.append(f"{route_id}: {field} contains suspicious text markers")

    if "match_level" in route:
        match_level = route.get("match_level")
        if match_level not in VALID_MATCH_LEVELS:
            errors.append(f"{route_id}: invalid match_level: {match_level!r}")

    for field in ("natural_patterns", "weak_patterns", "checker_targets", "architecture_flags", "hardware_challenge", "log_signals", "missing_facts", "verify_steps", "architecture_refactor", "root_cause_hints", "stop_conditions"):
        if field in route:
            if field == "checker_targets":
                _validate_checker_targets(route_id, route.get(field), checker_modules, errors)
            elif field in ("natural_patterns", "weak_patterns", "architecture_flags", "hardware_challenge", "log_signals", "missing_facts", "verify_steps", "architecture_refactor", "root_cause_hints", "stop_conditions"):
                _validate_str_list(route_id, field, route.get(field), errors)
            else:
                _validate_str_list(route_id, "recommended_commands", route.get(field), errors)

    # recommended_commands is useful if provided by future additions
    if "recommended_commands" in route:
        _validate_str_list(route_id, "recommended_commands", route.get("recommended_commands"), errors)

    if "diagnostic_probes" in route:
        _validate_diagnostic_probes(route_id, route.get("diagnostic_probes"), errors)

    for key, value in route.items():
        if isinstance(value, str) and key in REQUIRED_FIELDS:
            if _has_suspicious_text(value):
                errors.append(f"{route_id}: {key} contains suspicious text markers")


def validate_routes(data: dict[str, object]) -> list[str]:
    errors: list[str] = []
    checker_modules = _list_checker_modules()
    if not isinstance(data, dict) or not isinstance(data.get("symptoms"), list):
        return ["routes file must have a top-level {'symptoms': [...]}"]

    seen_ids: set[str] = set()
    for route in data["symptoms"]:
        if not isinstance(route, dict):
            errors.append("each symptom entry must be an object")
            continue

        _validate_fields(route, checker_modules, errors)

        route_id = route.get("id")
        if isinstance(route_id, str):
            if route_id in seen_ids:
                errors.append(f"{route_id}: duplicate id")
            seen_ids.add(route_id)

    return errors


def run_self_test() -> int:
    cases: list[tuple[dict[str, object], bool]] = [
        ({
            "symptoms": [{
                "id": "GOOD_ROUTE",
                "name": "Good route",
                "patterns": ["error", "warn"],
                "natural_patterns": ["error", "warning"],
                "weak_patterns": ["odd"],
                "category": "software",
                "severity": "P1",
                "constraints": ["C1"],
                "checker_targets": ["isr_safety_checker"],
                "diagnostic_probes": {
                    "log_confirm": ["case log line"],
                    "code_locate": ["grep -rn 'watchdog' src/"],
                    "tool_verify": ["python tools/run_review.py --self-test"],
                },
            }]
        }, True),
        ({
            "symptoms": [{
                "id": "BAD$$ID",
                "name": "Bad ID",
                "patterns": ["ok"],
                "category": "software",
                "severity": "P1",
                "constraints": ["C1"],
            }]
        }, False),
        ({
            "symptoms": [
                {"id": "ROUTE_A", "name": "A", "patterns": ["("], "category": "software", "severity": "P1", "constraints": ["C1"]},
                {"id": "ROUTE_A", "name": "A", "patterns": ["ok"], "category": "hardware", "severity": "P2", "constraints": ["C2"]},
            ]
        }, False),
        ({
            "symptoms": [{
                "id": "MISSING_LIST",
                "name": "Missing list",
                "category": "software",
                "severity": "P1",
                "constraints": ["C1"],
            }]
        }, False),
        ({
            "symptoms": [{
                "id": "HAS_REPLACEMENT",
                "name": "Bad ?? marker",
                "patterns": ["ok"],
                "category": "software",
                "severity": "P2",
                "constraints": ["C1"],
            }]
        }, False),
        ({
            "symptoms": [{
                "id": "BAD_CHECKER",
                "name": "Bad checker",
                "patterns": ["ok"],
                "category": "software",
                "severity": "P1",
                "constraints": ["C1"],
                "checker_targets": ["__not_exists__"],
            }]
        }, False),
        ({
            "symptoms": [{
                "id": "BAD_PROBES",
                "name": "Bad probes",
                "patterns": ["ok"],
                "category": "software",
                "severity": "P1",
                "constraints": ["C1"],
                "diagnostic_probes": {
                    "log_confirm": ["line"],
                    "tool_verify": ["cmd"],
                },
            }]
        }, False),
    ]

    passed = 0
    failed = 0
    for idx, (fixture, expected_pass) in enumerate(cases, start=1):
        errors = validate_routes(fixture)
        ok = len(errors) == 0
        if ok == expected_pass:
            print(f"[PASS] case-{idx}")
            passed += 1
        else:
            failed += 1
            print(f"[FAIL] case-{idx}: {errors}")

    quality_case = {
        "symptoms": [{
            "id": "QUALITY_ROUTE",
            "name": "Quality route",
            "patterns": ["quality_error"],
            "category": "software",
            "severity": "P2",
            "constraints": ["C1"],
            "checker_targets": [],
        }]
    }
    quality = _build_quality_report([quality_case["symptoms"][0]])
    if quality["total_routes"] == 1 and quality["missing_field_alerts"]["checker_targets"] == 0:
        print("[PASS] quality-report coverage")
        passed += 1
    else:
        print(f"[FAIL] quality-report coverage: {quality}")
        failed += 1

    conflict_case = {
        "symptoms": [
            {"id": "A", "patterns": ["same_error"]},
            {"id": "B", "patterns": ["same_error"]},
        ]
    }
    conflicts = _build_conflict_report(conflict_case["symptoms"])
    if conflicts["duplicate_patterns"]:
        print("[PASS] conflict duplicate-pattern report")
        passed += 1
    else:
        print(f"[FAIL] conflict duplicate-pattern report: {conflicts}")
        failed += 1

    print(f"self-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Check log symptom routes metadata quality")
    parser.add_argument("--file", type=Path, default=ROUTES_FILE)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--quality-json", action="store_true", help="print machine-readable quality and conflict report")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    path = args.file.resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        print(f"[ERROR] failed to read routes file: {exc}")
        return 2

    if raw.startswith(codecs.BOM_UTF8):
        print("[ERROR] routes file has UTF-8 BOM; re-save without BOM")
        return 2

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[ERROR] routes file is not valid JSON: {exc}")
        return 2

    errors = validate_routes(payload)
    symptoms = payload.get("symptoms", [])
    typed_symptoms = [r for r in symptoms if isinstance(r, dict)] if isinstance(symptoms, list) else []
    quality_report = _build_quality_report(typed_symptoms)

    if args.quality_json:
        print(json.dumps({
            "valid": not errors,
            "errors": errors,
            "quality": quality_report,
        }, indent=2, ensure_ascii=False))
        return 0 if not errors else 1

    if errors:
        print("[FAIL] log symptom routes validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"[PASS] log symptom routes valid: {len(payload.get('symptoms', []))} entries")
    _print_quality_report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
