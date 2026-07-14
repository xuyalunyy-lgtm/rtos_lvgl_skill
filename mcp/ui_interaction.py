"""Persistent clarification contract for design-driven UI generation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_decisions(path: str | None, inline: dict[str, Any] | None) -> dict[str, Any]:
    """Merge persisted decisions with inline answers; inline values win."""
    decisions: dict[str, Any] = {}
    if path:
        source = Path(path)
        if not source.is_file():
            raise ValueError(f"ui_decisions_path not found: {path}")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"unable to read ui_decisions_path: {exc}") from exc
        stored = payload.get("decisions", payload) if isinstance(payload, dict) else None
        if not isinstance(stored, dict):
            raise ValueError("ui_decisions_path must contain a JSON object")
        decisions.update(stored)
    if inline is not None:
        if not isinstance(inline, dict):
            raise ValueError("interaction_decisions must be an object")
        decisions.update(inline)
    return decisions


def _answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _valid_bbox(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
        and value[2] > 0
        and value[3] > 0
    )


def _valid_blocking_answer(question_id: str, value: Any) -> bool:
    if not _answered(value) or not isinstance(value, dict):
        return False
    if question_id == "coordinate_space":
        return (
            isinstance(value.get("design_width"), int) and value["design_width"] > 0
            and isinstance(value.get("design_height"), int) and value["design_height"] > 0
            and _answered(value.get("display_mapping"))
        )
    if question_id == "bbox_canvas_policy":
        return isinstance(value.get("include_transparent_padding"), bool)
    if question_id == "font_policy":
        return (
            _answered(value.get("source"))
            and isinstance(value.get("match_sizes"), bool)
            and _answered(value.get("fallback"))
            and _answered(value.get("glyph_scope"))
        )
    if question_id == "interaction_policy":
        return (
            _answered(value.get("transition"))
            and isinstance(value.get("targets"), list)
            and isinstance(value.get("persistent_state"), list)
        )
    if question_id == "asset_inventory":
        return isinstance(value.get("assets"), list) and bool(value["assets"])
    if question_id.startswith("asset:"):
        return (
            _answered(value.get("page"))
            and _answered(value.get("state"))
            and _answered(value.get("layer"))
            and _valid_bbox(value.get("bbox"))
            and value.get("size_policy") in {"native", "contain", "stretch", "code_drawn"}
            and _answered(value.get("reuse_scope"))
        )
    return False


def build_interaction_contract(
    *,
    mode: str,
    analysis_questions: list[Any],
    asset_intents: list[dict[str, Any]] | None,
    decisions: dict[str, Any],
) -> dict[str, Any]:
    """Return deterministic questions and a code-generation readiness decision."""
    if mode not in {"standard", "high"}:
        raise ValueError("interaction_mode must be 'standard' or 'high'")

    questions: list[dict[str, Any]] = []
    if mode == "high":
        questions.extend([
            {
                "id": "coordinate_space",
                "impact": "blocking",
                "prompt": "Define the design coordinate space and display mapping.",
                "answer_schema": {"design_width": "integer", "design_height": "integer", "display_mapping": "string"},
            },
            {
                "id": "bbox_canvas_policy",
                "impact": "blocking",
                "prompt": "State whether each bbox uses the full source canvas including transparent padding.",
                "answer_schema": {"include_transparent_padding": "boolean"},
            },
            {
                "id": "font_policy",
                "impact": "blocking",
                "prompt": "Define font source, weight/size matching, fallback, and glyph subset policy.",
                "answer_schema": {"source": "string", "match_sizes": "boolean", "fallback": "string", "glyph_scope": "string"},
            },
            {
                "id": "interaction_policy",
                "impact": "blocking",
                "prompt": "Define page transitions, click targets, and persistent state.",
                "answer_schema": {"transition": "string", "targets": "array", "persistent_state": "array"},
            },
        ])
        if asset_intents:
            for item in asset_intents:
                symbol = str(item.get("symbol", "")).strip()
                if not symbol:
                    continue
                questions.append({
                    "id": f"asset:{symbol}",
                    "impact": "blocking",
                    "prompt": f"Confirm page/state/layer/bbox/size policy/reuse for {symbol}.",
                    "answer_schema": {
                        "page": "string", "state": "string", "layer": "string",
                        "bbox": "[x,y,w,h]", "size_policy": "native|contain|stretch|code_drawn",
                        "reuse_scope": "string",
                    },
                })
        else:
            questions.append({
                "id": "asset_inventory",
                "impact": "blocking",
                "prompt": "Provide the complete asset inventory before placement questions are generated.",
                "answer_schema": {"assets": "array"},
            })

    for index, question in enumerate(analysis_questions):
        prompt = question.get("prompt") if isinstance(question, dict) else str(question)
        questions.append({
            "id": f"analysis:{index + 1}",
            "impact": "advisory",
            "prompt": prompt,
        })

    blocking_ids = [question["id"] for question in questions if question["impact"] == "blocking"]
    unresolved = [question_id for question_id in blocking_ids if not _valid_blocking_answer(question_id, decisions.get(question_id))]
    return {
        "schema_version": 1,
        "mode": mode,
        "questions": questions,
        "resolved_ids": [question_id for question_id in blocking_ids if question_id not in unresolved],
        "unresolved_ids": unresolved,
        "ready_for_codegen": mode != "high" or not unresolved,
    }


def write_interaction_artifacts(output_dir: Path, contract: dict[str, Any], decisions: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    contract_path = output_dir / "clarification_contract.json"
    decisions_path = output_dir / "ui_decisions.json"
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    decisions_path.write_text(
        json.dumps({"schema_version": 1, "decisions": decisions}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    return contract_path, decisions_path
