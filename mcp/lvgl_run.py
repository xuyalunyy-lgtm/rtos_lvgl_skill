"""Append-only run ledger for high-level LVGL MCP calls."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = ROOT / "artifacts" / "lvgl_runs"
RUN_STATUSES = {
    "inspected", "generated", "rendered", "compared", "verified",
    "manual_required", "capability_unavailable", "failed",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _validate_payload(run_id: str, payload: dict[str, Any]) -> None:
    """Verify the manifest read model against its immutable event chain."""
    if payload.get("schema_version") != 1 or payload.get("run_id") != run_id:
        raise ValueError("run manifest identity mismatch")
    stages = payload.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("run manifest has no stages")

    inputs = payload.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("run manifest inputs are invalid")
    design_path = inputs.get("design_path")
    expected_design_hash = inputs.get("design_sha256")
    if isinstance(design_path, str) and expected_design_hash:
        if _hash_file(Path(design_path)) != expected_design_hash:
            raise ValueError("run design artifact hash mismatch")

    previous_hash: str | None = None
    for sequence, stage in enumerate(stages, start=1):
        if not isinstance(stage, dict) or stage.get("sequence") != sequence:
            raise ValueError("run stage sequence is invalid")
        event = event_path(run_id, sequence)
        event_hash = _hash_file(event)
        if event_hash is None:
            raise ValueError(f"run event missing: {event.name}")
        try:
            event_payload = json.loads(event.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"run event is invalid: {event.name}") from exc
        expected_event = {
            "run_id": run_id,
            "previous_event_sha256": previous_hash,
            **stage,
        }
        if event_payload != expected_event:
            raise ValueError(f"run event does not match manifest: {event.name}")
        for artifact in stage.get("artifacts", []):
            if not isinstance(artifact, dict):
                raise ValueError("run artifact entry is invalid")
            expected_hash = artifact.get("sha256")
            raw_path = artifact.get("path")
            if expected_hash and (not isinstance(raw_path, str) or _hash_file(Path(raw_path)) != expected_hash):
                raise ValueError(f"run artifact hash mismatch: {artifact.get('name', 'unknown')}")
        previous_hash = event_hash

    if payload.get("status") != stages[-1].get("status"):
        raise ValueError("run status does not match its latest event")


def run_dir(run_id: str) -> Path:
    path = (RUNS_ROOT / run_id).resolve()
    if not path.is_relative_to(RUNS_ROOT.resolve()):
        raise ValueError("invalid run_id")
    return path


def manifest_path(run_id: str) -> Path:
    return run_dir(run_id) / "run_manifest.json"


def event_path(run_id: str, sequence: int) -> Path:
    """Return the immutable event file for one recorded pipeline stage."""
    return run_dir(run_id) / "events" / f"{sequence:04d}.json"


def create_run(*, design_path: str, display: dict[str, Any], lvgl_version: str, artifacts: dict[str, str]) -> dict[str, Any]:
    """Create a run with immutable inputs and an initially inspected stage."""
    run_id = uuid.uuid4().hex
    design = Path(design_path).resolve()
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": _now(),
        "status": "inspected",
        "inputs": {
            "design_path": str(design),
            "design_sha256": _hash_file(design),
            "display": display,
            "lvgl_version": lvgl_version,
        },
        "stages": [{
            "sequence": 1,
            "stage": "inspect",
            "status": "inspected",
            "at": _now(),
            "artifacts": _artifact_entries(artifacts),
        }],
    }
    _write(manifest_path(run_id), payload)
    _write(event_path(run_id, 1), {
        "run_id": run_id,
        "previous_event_sha256": None,
        **payload["stages"][0],
    })
    return payload


def load_run(run_id: str) -> dict[str, Any]:
    path = manifest_path(run_id)
    if not path.is_file():
        raise ValueError(f"run_id not found: {run_id}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid run manifest for {run_id}: {exc}") from exc
    _validate_payload(run_id, payload)
    return payload


def default_stage_dir(run_id: str, stage: str) -> str:
    path = run_dir(run_id) / stage
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def latest_artifact(run_id: str, name: str) -> str | None:
    """Return the newest recorded artifact path with the requested name."""
    payload = load_run(run_id)
    for stage in reversed(payload.get("stages", [])):
        for artifact in reversed(stage.get("artifacts", [])):
            if artifact.get("name") == name:
                value = artifact.get("path")
                return str(value) if value else None
    return None


def stage_artifact(run_id: str, stage_name: str, name: str) -> str | None:
    """Return an artifact from the newest occurrence of a specific stage."""
    payload = load_run(run_id)
    for stage in reversed(payload.get("stages", [])):
        if stage.get("stage") != stage_name:
            continue
        for artifact in reversed(stage.get("artifacts", [])):
            if artifact.get("name") == name:
                value = artifact.get("path")
                return str(value) if value else None
    return None


def record_stage(run_id: str, *, stage: str, status: str, artifacts: dict[str, str], details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append a hash-linked stage event and refresh the manifest read model."""
    if status not in RUN_STATUSES:
        raise ValueError(f"invalid run status: {status}")
    payload = load_run(run_id)
    sequence = len(payload.get("stages", [])) + 1
    previous_hash = _hash_file(event_path(run_id, sequence - 1)) if sequence > 1 else None
    entry = {
        "sequence": sequence,
        "stage": stage,
        "status": status,
        "at": _now(),
        "artifacts": _artifact_entries(artifacts),
    }
    if details:
        entry["details"] = details
    _write(event_path(run_id, sequence), {
        "run_id": run_id,
        "previous_event_sha256": previous_hash,
        **entry,
    })
    payload.setdefault("stages", []).append(entry)
    payload["status"] = status
    payload["updated_at"] = _now()
    _write(manifest_path(run_id), payload)

    output_dir = artifacts.get("output_dir")
    if output_dir:
        output = Path(output_dir)
        if output.is_dir():
            _write(output / "run_manifest.json", payload)
    return payload


def resolve_args(run_id: str, args: dict[str, Any], *, stage: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fill omitted pipeline inputs from a run and reject conflicting values."""
    payload = load_run(run_id)
    inputs = payload.get("inputs", {})
    resolved = dict(args)
    for key in ("design_path", "lvgl_version"):
        inherited = inputs.get(key)
        supplied = resolved.get(key)
        if supplied is not None and inherited is not None and str(supplied) != str(inherited):
            raise ValueError(f"{key} conflicts with run_id {run_id}")
        if supplied is None and inherited is not None:
            resolved[key] = inherited

    inherited_display = inputs.get("display") or {}
    supplied_display = resolved.get("display") or {}
    for key in ("width", "height", "rotation", "color_format"):
        if key in supplied_display and key in inherited_display and supplied_display[key] != inherited_display[key]:
            raise ValueError(f"display.{key} conflicts with run_id {run_id}")
    if inherited_display:
        resolved["display"] = {**inherited_display, **supplied_display}
    if not resolved.get("output_dir"):
        resolved["output_dir"] = default_stage_dir(run_id, stage)
    return resolved, payload


def _artifact_entries(artifacts: dict[str, str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name, raw_path in sorted(artifacts.items()):
        if not raw_path:
            continue
        path = Path(raw_path)
        entries.append({"name": name, "path": str(path), "sha256": _hash_file(path)})
    return entries
