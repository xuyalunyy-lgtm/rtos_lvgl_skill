"""Evidence-driven LVGL refinement entry point.

This module intentionally never treats design-analysis confidence as a visual
score. A refinement run starts only after native render/compile evidence is
available, then delegates monotonic promotion to :mod:`mcp.refine_guard`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_ITERATIONS = 3


def refine_loop(
    design_path: str,
    screen_width: int,
    screen_height: int,
    lvgl_version: str = "v9",
    cut_dir: str | None = None,
    output_dir: str = "artifacts/lvgl_refine",
    max_iterations: int = MAX_ITERATIONS,
    baseline_evidence_path: str | None = None,
    candidate_evidence_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate native evidence with strict, transactional monotonicity.

    ``design_path`` remains for MCP compatibility and traceability. Callers
    must provide evidence emitted by the native app harness or CI; without it
    the response is an explicit capability gap instead of a fake refinement.
    """
    del screen_width, screen_height, lvgl_version, cut_dir
    if max_iterations < 1 or max_iterations > MAX_ITERATIONS:
        return {"ok": False, "status": "invalid_iterations", "errors": ["max_iterations must be 1..3"]}
    if not Path(design_path).is_file():
        return {"ok": False, "status": "design_not_found", "errors": [f"Design not found: {design_path}"]}
    if not baseline_evidence_path:
        return {
            "ok": False,
            "status": "native_evidence_required",
            "errors": ["refine_ui requires native compile/render/flow evidence; analysis confidence is not accepted"],
            "output_dir": output_dir,
        }
    try:
        baseline = json.loads(Path(baseline_evidence_path).read_text(encoding="utf-8"))
        candidates = [json.loads(Path(path).read_text(encoding="utf-8")) for path in (candidate_evidence_paths or [])]
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": "invalid_evidence", "errors": [str(exc)]}
    if len(candidates) > max_iterations:
        return {"ok": False, "status": "invalid_evidence", "errors": ["candidate evidence exceeds max_iterations"]}
    from mcp.refine_guard import evaluate_refinement_run
    result = evaluate_refinement_run(output_dir, baseline, candidates)
    return {"ok": result.get("status") == "completed", **result, "output_dir": output_dir}
