#!/usr/bin/env python3
"""
Routing sampling evaluation — calibrate keyword weights and cross-domain threshold.

Reads 60 real-world-style requests from JSON fixture, classifies each, and produces
detailed statistics including confusion matrix, per-language breakdown, and threshold
sensitivity analysis. Non-blocking for CI; outputs JSON artifact for human review.

Usage:
    python scripts/eval_routing_sampling.py
    python scripts/eval_routing_sampling.py --json > artifacts/routing_sampling.json
    python scripts/eval_routing_sampling.py --threshold-scan
    python scripts/eval_routing_sampling.py --id cr_01
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(ROOT / "tools"))

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "routing_sampling.json"

# ── Core evaluation ──

def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def classify_with_scores(text: str, threshold: float | None = None) -> dict:
    """Classify request and return full scoring details.

    Returns dict with:
        result: the classify_request output
        all_scores: {workflow: score} for all matched workflows
        best_score, second_score, score_gap
        matched_keywords: {workflow: [keywords]}
        threshold_used: the cross-domain threshold applied
    """
    from context_router import ROUTE_KEYWORDS, classify_request, CROSS_DOMAIN_AMBIGUITY_THRESHOLD
    import re

    if threshold is None:
        threshold = CROSS_DOMAIN_AMBIGUITY_THRESHOLD

    text_lower = text.lower()
    scores: dict[str, int] = {}
    matched_kw: dict[str, list[str]] = {}

    def _kw_match(kw: str, text: str) -> tuple[bool, int]:
        kw_lower = kw.lower()
        is_phrase = " " in kw_lower or not kw_lower.isascii()
        if len(kw_lower) <= 3 and kw_lower.isascii():
            if re.search(r'\b' + re.escape(kw_lower) + r'\b', text):
                return True, 1
            return False, 0
        if kw_lower in text:
            return True, 3 if is_phrase else 1
        return False, 0

    for wf_id, spec in ROUTE_KEYWORDS.items():
        score = 0
        terms = []
        for kw in spec["keywords"]:
            hit, weight = _kw_match(kw, text_lower)
            if hit:
                score += weight
                terms.append(kw)
        if score > 0:
            scores[wf_id] = score
            matched_kw[wf_id] = terms

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_score = sorted_scores[0][1] if sorted_scores else 0
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    # Re-classify with the given threshold to simulate threshold change
    result = classify_request(text, cross_domain_threshold=threshold)

    return {
        "result": result,
        "all_scores": dict(sorted_scores),
        "best_score": best_score,
        "second_score": second_score,
        "score_gap": best_score - second_score,
        "matched_keywords": {wf: matched_kw.get(wf, []) for wf in scores},
        "threshold_used": threshold,
    }


def evaluate_sample(sample: dict, threshold: float | None = None) -> dict:
    """Evaluate a single sampling request with full detail."""
    detail = classify_with_scores(sample["request"], threshold)
    result = detail["result"]

    # Determine expected
    expected_wf = sample.get("expected_workflow")
    expect_clarification = sample.get("expected_clarification", False)

    # Determine actual
    is_clarification = result.get("clarification_required", False)
    actual_wf = result.get("workflow") if not is_clarification else None

    # Check correctness
    if expect_clarification:
        correct = is_clarification
        outcome = "correct_clarification" if correct else "missed_clarification"
    else:
        if is_clarification:
            correct = False
            outcome = "false_clarification"
        else:
            correct = actual_wf == expected_wf
            outcome = "correct_route" if correct else "wrong_route"

    return {
        "id": sample["id"],
        "request": sample["request"],
        "language": sample.get("language", "unknown"),
        "expected_workflow": expected_wf,
        "expected_clarification": expect_clarification,
        "actual_workflow": actual_wf,
        "actual_clarification": is_clarification,
        "clarification_reason": result.get("clarification_reason"),
        "outcome": outcome,
        "correct": correct,
        "all_scores": detail["all_scores"],
        "best_score": detail["best_score"],
        "second_score": detail["second_score"],
        "score_gap": detail["score_gap"],
        "matched_keywords": detail["matched_keywords"],
        "threshold_used": threshold,
        "human_reason": sample.get("reason", ""),
    }


def compute_stats(results: list[dict]) -> dict:
    """Compute aggregate statistics from evaluation results."""
    total = len(results)
    correct = sum(1 for r in results if r["correct"])

    # Split by type
    positive = [r for r in results if not r["expected_clarification"]]
    negative = [r for r in results if r["expected_clarification"]]

    auto_correct = sum(1 for r in positive if r["correct"])
    auto_total = len(positive)
    clarif_correct = sum(1 for r in negative if r["correct"])
    clarif_total = len(negative)

    # Confusion matrix (for positive cases only)
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in positive:
        confusion[r["expected_workflow"]][r["actual_workflow"] or "clarification"] += 1

    # Per-language breakdown
    by_lang: dict[str, dict] = {}
    for lang in set(r["language"] for r in results):
        lang_results = [r for r in results if r["language"] == lang]
        by_lang[lang] = {
            "total": len(lang_results),
            "correct": sum(1 for r in lang_results if r["correct"]),
            "accuracy": sum(1 for r in lang_results if r["correct"]) / len(lang_results) if lang_results else 0,
        }

    # Outcome counts
    outcomes = Counter(r["outcome"] for r in results)

    return {
        "total": total,
        "overall_conformance": correct / total if total else 0,
        "auto_routing": {
            "total": auto_total,
            "correct": auto_correct,
            "accuracy": auto_correct / auto_total if auto_total else 0,
        },
        "clarification": {
            "total": clarif_total,
            "correct": clarif_correct,
            "accuracy": clarif_correct / clarif_total if clarif_total else 0,
        },
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "by_language": by_lang,
        "outcomes": dict(outcomes),
    }


# ── Threshold scanning ──

def reclassify_with_threshold(sample: dict, threshold: float) -> dict:
    """Re-classify a sample with a different cross-domain threshold.

    This replicates the classify_request logic but with a custom threshold.
    """
    from context_router import ROUTE_KEYWORDS
    import re

    text = sample["request"]
    text_lower = text.lower()
    scores: dict[str, int] = {}
    matched_kw: dict[str, list[str]] = {}

    def _kw_match(kw: str, text: str) -> tuple[bool, int]:
        kw_lower = kw.lower()
        is_phrase = " " in kw_lower or not kw_lower.isascii()
        if len(kw_lower) <= 3 and kw_lower.isascii():
            if re.search(r'\b' + re.escape(kw_lower) + r'\b', text):
                return True, 1
            return False, 0
        if kw_lower in text:
            return True, 3 if is_phrase else 1
        return False, 0

    for wf_id, spec in ROUTE_KEYWORDS.items():
        score = 0
        terms = []
        for kw in spec["keywords"]:
            hit, weight = _kw_match(kw, text_lower)
            if hit:
                score += weight
                terms.append(kw)
        if score > 0:
            scores[wf_id] = score
            matched_kw[wf_id] = terms

    if not scores:
        return {"clarification_required": True, "clarification_reason": "No keyword matched"}

    best_wf = max(scores, key=scores.get)
    best_score = scores[best_wf]

    # Same-domain tie check
    tied = [wf for wf, s in scores.items() if s == best_score]
    if len(tied) > 1:
        domains = {wf: ROUTE_KEYWORDS[wf]["domain"] for wf in tied}
        if len(set(domains.values())) > 1:
            return {"clarification_required": True, "clarification_reason": f"Tied across domains: {tied}"}

    # Cross-domain check with custom threshold
    matched_domains = {ROUTE_KEYWORDS[wf]["domain"] for wf in scores}
    if len(matched_domains) > 1:
        cross_competitors = [
            (wf, s) for wf, s in scores.items()
            if ROUTE_KEYWORDS[wf]["domain"] != ROUTE_KEYWORDS[best_wf]["domain"]
        ]
        if cross_competitors:
            top_competitor_score = max(s for _, s in cross_competitors)
            if top_competitor_score >= best_score * threshold:
                competitors = [
                    f"{wf}({ROUTE_KEYWORDS[wf]['domain']},score={s})"
                    for wf, s in cross_competitors if s == top_competitor_score
                ]
                return {
                    "clarification_required": True,
                    "clarification_reason": f"Cross-domain: {best_wf} vs {', '.join(competitors)}",
                }

    return {
        "domain": ROUTE_KEYWORDS[best_wf]["domain"],
        "workflow": best_wf,
        "routing_reason": f"Matched: {', '.join(matched_kw[best_wf])}",
    }


def threshold_scan(samples: list[dict], thresholds: list[float], selection_policy: str = "") -> list[dict]:
    """Run evaluation at multiple thresholds and compare.

    Applies selection policy to determine the best threshold:
    "Maximize conformance; on tie choose the highest threshold with zero false routes
    and zero false clarifications."
    """
    results = []
    for t in thresholds:
        eval_results = []
        for sample in samples:
            result = reclassify_with_threshold(sample, t)
            expected_wf = sample.get("expected_workflow")
            expect_clar = sample.get("expected_clarification", False)
            is_clar = result.get("clarification_required", False)
            actual_wf = result.get("workflow") if not is_clar else None

            if expect_clar:
                correct = is_clar
            elif is_clar:
                correct = False
            else:
                correct = actual_wf == expected_wf

            eval_results.append({
                "id": sample["id"],
                "correct": correct,
                "expect_clarification": expect_clar,
                "is_clarification": is_clar,
                "expected_workflow": expected_wf,
                "actual_workflow": actual_wf,
            })

        total = len(eval_results)
        correct = sum(1 for r in eval_results if r["correct"])
        positive = [r for r in eval_results if not r["expect_clarification"]]
        false_routes = sum(1 for r in positive if not r["correct"] and not r["is_clarification"])
        false_clarifs = sum(1 for r in positive if r["is_clarification"])

        results.append({
            "threshold": t,
            "overall_conformance": correct / total if total else 0,
            "correct": correct,
            "total": total,
            "false_auto_routes": false_routes,
            "false_clarifications": false_clarifs,
            "auto_routing_accuracy": sum(1 for r in positive if r["correct"]) / len(positive) if positive else 0,
        })

    # Apply selection policy: maximize conformance; on tie pick highest threshold
    # with zero false routes and zero false clarifications
    if results:
        best_conformance = max(r["overall_conformance"] for r in results)
        candidates = [r for r in results if r["overall_conformance"] == best_conformance]
        perfect = [r for r in candidates if r["false_auto_routes"] == 0 and r["false_clarifications"] == 0]
        if perfect:
            selected = max(perfect, key=lambda r: r["threshold"])
        else:
            selected = max(candidates, key=lambda r: r["threshold"])
        for r in results:
            r["selected"] = r["threshold"] == selected["threshold"]

    return results


# ── CLI ──

def main() -> int:
    parser = argparse.ArgumentParser(description="Routing sampling evaluation")
    parser.add_argument("--json", action="store_true", help="Output JSON artifact")
    parser.add_argument("--threshold-scan", action="store_true", help="Run threshold sensitivity analysis")
    parser.add_argument("--id", help="Run only this sample ID")
    args = parser.parse_args()

    fixture = load_fixture()
    samples = fixture["samples"]

    if args.id:
        samples = [s for s in samples if s["id"] == args.id]
        if not samples:
            print(f"Sample not found: {args.id}", file=sys.stderr)
            return 1

    if args.threshold_scan:
        meta = fixture.get("meta", {})
        thresholds = meta.get("threshold_candidates", [0.4, 0.5, 0.6])
        policy = meta.get("selection_policy", "")
        scan_results = threshold_scan(samples, thresholds, policy)

        # Validate: the fixture's configured threshold must be in candidates
        configured = meta.get("cross_domain_ambiguity_threshold", 0.5)
        if configured not in thresholds:
            print(f"ERROR: configured threshold {configured} not in candidates {thresholds}", file=sys.stderr)
            return 1

        # Validate: the selected threshold from scan matches fixture
        selected = [r for r in scan_results if r.get("selected")]
        if selected and selected[0]["threshold"] != configured:
            print(f"WARNING: scan selected {selected[0]['threshold']} but fixture has {configured}", file=sys.stderr)

        if args.json:
            json.dump({
                "threshold_scan": scan_results,
                "configured_threshold": configured,
                "selection_policy": policy,
                "validation": {
                    "configured_in_candidates": configured in thresholds,
                    "scan_matches_config": not selected or selected[0]["threshold"] == configured,
                },
            }, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            print("Threshold Scan Results\n")
            print(f"{'Threshold':<12} {'Conformance':<14} {'Correct':<10} {'False Routes':<14} {'False Clarifs':<14} {'Selected':<10}")
            print("-" * 74)
            for r in scan_results:
                sel = "← selected" if r.get("selected") else ""
                print(f"{r['threshold']:<12.1%} {r['overall_conformance']:<14.1%} {r['correct']:<10} {r['false_auto_routes']:<14} {r['false_clarifications']:<14} {sel}")
            print(f"\nPolicy: {policy}")
            print(f"Configured threshold: {configured}")
        return 0

    # Full evaluation — use fixture config or module default
    from context_router import CROSS_DOMAIN_AMBIGUITY_THRESHOLD
    threshold = fixture.get("meta", {}).get("cross_domain_ambiguity_threshold",
                 fixture.get("meta", {}).get("best_cross_domain_threshold",
                 CROSS_DOMAIN_AMBIGUITY_THRESHOLD))
    results = [evaluate_sample(s, threshold) for s in samples]
    stats = compute_stats(results)

    if args.json:
        artifact = {
            "meta": fixture.get("meta", {}),
            "stats": stats,
            "results": results,
        }
        json.dump(artifact, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print(f"Routing Sampling Evaluation ({stats['total']} requests, threshold={threshold})\n")

        # Per-sample results
        print(f"{'ID':<10} {'Lang':<5} {'Expected':<18} {'Got':<18} {'Outcome':<20} {'Gap':<5} Keywords")
        print("-" * 100)
        for r in results:
            expect = r["expected_workflow"] or ("clarif" if r["expected_clarification"] else "?")
            got = r["actual_workflow"] or ("clarif" if r["actual_clarification"] else "?")
            kws = ", ".join(r["matched_keywords"].get(r["actual_workflow"] or "", []))[:30]
            outcome_icon = {"correct_route": "✓", "correct_clarification": "✓", "wrong_route": "✗", "false_clarification": "✗", "missed_clarification": "✗"}[r["outcome"]]
            print(f"{r['id']:<10} {r['language']:<5} {expect:<18} {got:<18} {outcome_icon} {r['outcome']:<18} {r['score_gap']:<5} {kws}")

        # Summary
        print(f"\n{'='*60}")
        print(f"Overall conformance:  {stats['overall_conformance']:.1%} ({stats['total']} total)")
        print(f"Auto-routing:         {stats['auto_routing']['accuracy']:.1%} ({stats['auto_routing']['correct']}/{stats['auto_routing']['total']})")
        print(f"Clarification:        {stats['clarification']['accuracy']:.1%} ({stats['clarification']['correct']}/{stats['clarification']['total']})")

        # Per-language
        print(f"\nBy language:")
        for lang, ls in sorted(stats["by_language"].items()):
            print(f"  {lang:<6} {ls['accuracy']:.1%} ({ls['correct']}/{ls['total']})")

        # Confusion matrix (abbreviated)
        if stats["confusion_matrix"]:
            print(f"\nConfusion matrix (expected → actual):")
            for expected, actuals in sorted(stats["confusion_matrix"].items()):
                for actual, count in sorted(actuals.items(), key=lambda x: -x[1]):
                    if actual != expected or count > 1:
                        print(f"  {expected:<18} → {actual:<18} ({count})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
