from pathlib import Path

from mcp.refine_guard import evaluate_refinement_run


GATES = {
    "native_render": True, "compile": True, "nodes_nonempty": True,
    "not_blank": True, "assets": True, "fonts": True, "memory": True,
    "flows": True, "no_capability_gap": True, "no_design_cheat": True,
}


def _evidence(similarity: float, *, operation: bool = False) -> dict:
    override = {"operations": []}
    if operation:
        override = {"operations": [{"type": "set_bbox", "page": "home", "state": "default", "node": "title", "value": [0, 0, 10, 10]}]}
    return {
        "comparison": {
            "global_ssim": similarity,
            "changed_pixel_ratio": 1.0 - similarity,
            "region_diffs": [{"id": "critical", "ssim": similarity}],
            "control_tree_diffs": [], "text_diffs": [],
        },
        "critical_region_ids": ["critical"],
        "hard_gates": GATES,
        "override": override,
    }


def test_final_requires_every_90_percent_gate(tmp_path: Path) -> None:
    result = evaluate_refinement_run(tmp_path / "low", _evidence(0.89), [])
    assert result["status"] == "manual_required"
    assert result["reason"] == "quality_threshold_not_met"
    assert "global_ssim<0.90" in result["quality_failures"]
    assert (tmp_path / "low" / "final" / "ui_override.json").is_file()


def test_up_to_three_monotonic_candidates_deliver_highest(tmp_path: Path) -> None:
    candidates = [_evidence(0.91, operation=True), _evidence(0.93, operation=True), _evidence(0.95, operation=True)]
    result = evaluate_refinement_run(tmp_path / "high", _evidence(0.90), candidates)
    assert result["status"] == "completed"
    assert result["best_iteration"] == 3
    assert result["best_score"] >= 9000
    assert len(result["history"]) == 4
    assert result["quality_failures"] == []
