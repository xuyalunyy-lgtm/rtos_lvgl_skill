"""Transactional, monotonic guard for visual refinement artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from mcp.lvgl_compare import score_evidence

ALLOWED_OPERATIONS = {
    "set_bbox", "set_style", "set_layout", "set_asset", "set_font",
    "set_text", "set_template_param", "set_state_asset_override",
}
REQUIRED_GATES = {
    "native_render", "compile", "nodes_nonempty", "not_blank", "assets",
    "fonts", "memory", "flows", "no_capability_gap", "no_design_cheat",
}
FINAL_MIN_SCORE = 9000
FINAL_MIN_GLOBAL_SSIM = 0.90
FINAL_MIN_CRITICAL_REGION_SSIM = 0.90
FINAL_MIN_PIXEL_SIMILARITY = 0.90


def validate_refine_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    operations = plan.get("operations")
    if not isinstance(operations, list) or not operations:
        return ["refine plan requires non-empty operations"]
    for index, op in enumerate(operations):
        if not isinstance(op, dict) or op.get("type") not in ALLOWED_OPERATIONS:
            errors.append(f"operations[{index}] is not an allowed override operation")
            continue
        if not isinstance(op.get("page"), str) or not isinstance(op.get("state"), str):
            errors.append(f"operations[{index}] requires page and state")
        if op["type"] not in {"set_template_param", "set_state_asset_override"} and not isinstance(op.get("node"), str):
            errors.append(f"operations[{index}] requires node")
    return errors


def evaluate_refinement_run(
    output_dir: str | Path,
    baseline_evidence: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Promote only strict improvements and atomically preserve the best.

    Evidence is supplied by a native harness/CI. This module deliberately does
    not render, invoke a model, or modify user files.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    accepted_dir = root / "accepted"
    final_dir = root / "final"
    accepted_dir.mkdir(exist_ok=True)
    final_dir.mkdir(exist_ok=True)
    accepted = _normalise_evidence(baseline_evidence)
    if not accepted["hard_gates_pass"]:
        result = _result("baseline_invalid", accepted, None, "baseline_hard_gate_failed")
        _atomic_json(root / "refine_summary.json", result)
        return result
    _atomic_json(accepted_dir / "evidence.json", accepted)
    _atomic_json(accepted_dir / "ui_override.json", baseline_evidence.get("override", {"operations": []}))
    history = [{"iteration": 0, "decision": "accepted_baseline", "score": accepted["total_score"]}]

    for number, candidate in enumerate(candidates, 1):
        iteration = root / f"iteration_{number:03d}"
        iteration.mkdir(exist_ok=True)
        plan = candidate.get("override", {"operations": []})
        plan_errors = validate_refine_plan(plan)
        evaluated = _normalise_evidence(candidate)
        _atomic_json(iteration / "evidence.json", evaluated)
        _atomic_json(iteration / "ui_override.json", plan)
        if plan_errors:
            return _circuit_break(root, accepted, evaluated, number, "invalid_override", plan_errors, history)
        if not evaluated["hard_gates_pass"]:
            return _circuit_break(root, accepted, evaluated, number, "candidate_hard_gate_failed", [], history)
        regressed = [
            key for key, value in evaluated["critical_regions"].items()
            if key in accepted["critical_regions"] and value < accepted["critical_regions"][key]
        ]
        if evaluated["total_score"] <= accepted["total_score"] or regressed:
            reason = "score_not_strictly_improved" if not regressed else "critical_region_regressed"
            return _circuit_break(root, accepted, evaluated, number, reason, regressed, history)
        accepted = evaluated
        _atomic_json(accepted_dir / "evidence.json", accepted)
        _atomic_json(accepted_dir / "ui_override.json", plan)
        history.append({"iteration": number, "decision": "promoted", "score": accepted["total_score"]})

    _atomic_json(final_dir / "evidence.json", accepted)
    shutil.copy2(accepted_dir / "ui_override.json", final_dir / "ui_override.json")
    failures = _final_quality_failures(accepted)
    result = {
        "status": "completed" if not failures else "manual_required",
        "reason": None if not failures else "quality_threshold_not_met",
        "best_score": accepted["total_score"],
        "best_iteration": int(history[-1]["iteration"]),
        "max_candidate_iterations": 3,
        "quality_threshold": {
            "total_score": FINAL_MIN_SCORE,
            "global_ssim": FINAL_MIN_GLOBAL_SSIM,
            "critical_region_ssim": FINAL_MIN_CRITICAL_REGION_SSIM,
            "pixel_similarity": FINAL_MIN_PIXEL_SIMILARITY,
        },
        "quality_failures": failures,
        "history": history,
        "rollback_completed": True,
    }
    _atomic_json(root / "best.json", {"score": accepted["total_score"], "evidence_sha256": _hash_json(accepted)})
    _atomic_json(root / "refine_summary.json", result)
    return result


def _final_quality_failures(evidence: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = evidence.get("metrics", {})
    if int(evidence.get("total_score", 0)) < FINAL_MIN_SCORE:
        failures.append(f"total_score<{FINAL_MIN_SCORE}")
    if float(metrics.get("global_ssim", 0.0)) < FINAL_MIN_GLOBAL_SSIM:
        failures.append(f"global_ssim<{FINAL_MIN_GLOBAL_SSIM:.2f}")
    if float(metrics.get("critical_region_ssim", 0.0)) < FINAL_MIN_CRITICAL_REGION_SSIM:
        failures.append(f"critical_region_ssim<{FINAL_MIN_CRITICAL_REGION_SSIM:.2f}")
    if float(metrics.get("pixel_similarity", 0.0)) < FINAL_MIN_PIXEL_SIMILARITY:
        failures.append(f"pixel_similarity<{FINAL_MIN_PIXEL_SIMILARITY:.2f}")
    return failures


def _normalise_evidence(raw: dict[str, Any]) -> dict[str, Any]:
    comparison = raw.get("comparison", {})
    gates = {name: bool(raw.get("hard_gates", {}).get(name, False)) for name in REQUIRED_GATES}
    critical = set(raw.get("critical_region_ids", []))
    scored = score_evidence(comparison, critical_region_ids=critical, hard_gates=gates)
    return {**scored, "source_hash": _hash_json(raw)}


def _circuit_break(root: Path, accepted: dict[str, Any], rejected: dict[str, Any], iteration: int, reason: str, details: list[str], history: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        "status": "manual_required", "reason": reason, "accepted_score": accepted["total_score"],
        "rejected_score": rejected["total_score"], "accepted_iteration": max(0, iteration - 1),
        "rejected_iteration": iteration, "rollback_completed": True, "details": details,
        "core_conflicts": _conflicts(accepted, rejected, details),
    }
    final_dir = root / "final"; final_dir.mkdir(exist_ok=True)
    shutil.copy2(root / "accepted" / "ui_override.json", final_dir / "ui_override.json")
    _atomic_json(final_dir / "evidence.json", accepted)
    _atomic_json(root / "circuit_breaker_report.json", report)
    history.append({"iteration": iteration, "decision": "circuit_breaker", "score": rejected["total_score"]})
    result = {**report, "history": history}
    _atomic_json(root / "refine_summary.json", result)
    return result


def _conflicts(accepted: dict[str, Any], rejected: dict[str, Any], details: list[str]) -> list[dict[str, Any]]:
    conflicts = []
    for key, before in accepted["critical_regions"].items():
        after = rejected["critical_regions"].get(key, before)
        if after < before:
            conflicts.append({"classification": "layout_propagation", "region": key, "delta": round(after - before, 6), "confidence": 1.0})
    if not conflicts and details:
        conflicts.append({"classification": "unknown_regression", "detail": details[0], "confidence": 0.5})
    return conflicts


def _atomic_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
