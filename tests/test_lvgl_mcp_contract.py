"""Focused contracts for high-level LVGL MCP capability and run behavior."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from mcp import lvgl_run
from mcp.high_level_tools import apply_patch, compare_ui, inspect_design, render_ui
from mcp.lvgl_capabilities import get_capabilities, verification_plan


class TestLvglCapabilities(unittest.TestCase):
    def test_v8_is_compile_only_for_visual_acceptance(self) -> None:
        capability = get_capabilities("v8")
        self.assertTrue(capability["codegen"])
        self.assertTrue(capability["static_compile"])
        self.assertFalse(capability["native_render"])
        self.assertFalse(verification_plan("v8")["authoritative"])

    def test_v9_has_authoritative_native_render(self) -> None:
        capability = get_capabilities("v9")
        self.assertTrue(capability["native_render"])
        self.assertTrue(verification_plan("v9")["authoritative"])

    def test_v8_native_render_returns_capability_gap_before_spec_read(self) -> None:
        result = render_ui({
            "spec_path": "does-not-need-to-exist.json",
            "lvgl_version": "v8",
            "engine": "lvgl_simulator",
        })
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "capability_unavailable")
        self.assertEqual(result["recommended_engine"], "python_preview")


class TestLvglRunLedger(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="lvgl-run-")
        self.original_runs_root = lvgl_run.RUNS_ROOT
        lvgl_run.RUNS_ROOT = Path(self.tempdir.name) / "runs"
        self.design = Path(self.tempdir.name) / "design.png"
        Image.new("RGB", (480, 800), "white").save(self.design)

    def tearDown(self) -> None:
        lvgl_run.RUNS_ROOT = self.original_runs_root
        self.tempdir.cleanup()

    def test_run_inherits_inputs_and_records_stage(self) -> None:
        run = lvgl_run.create_run(
            design_path=str(self.design),
            display={"width": 480, "height": 800},
            lvgl_version="v9",
            artifacts={},
        )
        args, _ = lvgl_run.resolve_args(run["run_id"], {}, stage="generate")
        self.assertEqual(args["design_path"], str(self.design.resolve()))
        self.assertEqual(args["lvgl_version"], "v9")
        self.assertIn("generate", args["output_dir"])

        output = Path(args["output_dir"])
        lvgl_run.record_stage(
            run["run_id"],
            stage="generate",
            status="generated",
            artifacts={"output_dir": str(output)},
        )
        self.assertEqual(lvgl_run.load_run(run["run_id"])["status"], "generated")
        self.assertTrue((output / "run_manifest.json").is_file())
        self.assertTrue(lvgl_run.event_path(run["run_id"], 1).is_file())
        second_event = lvgl_run.event_path(run["run_id"], 2)
        self.assertTrue(second_event.is_file())
        self.assertEqual(
            json.loads(second_event.read_text(encoding="utf-8"))["previous_event_sha256"],
            hashlib.sha256(lvgl_run.event_path(run["run_id"], 1).read_bytes()).hexdigest(),
        )

    def test_inspect_returns_ledger_status_not_tool_status(self) -> None:
        result = inspect_design({
            "design_path": str(self.design),
            "output_dir": "artifacts/test_contract_inspect",
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "manual_required")
        self.assertEqual(result["run_status"], "manual_required")

    def test_conflicting_run_input_is_rejected(self) -> None:
        run = lvgl_run.create_run(
            design_path=str(self.design),
            display={"width": 480, "height": 800},
            lvgl_version="v9",
            artifacts={},
        )
        with self.assertRaisesRegex(ValueError, "lvgl_version conflicts"):
            lvgl_run.resolve_args(run["run_id"], {"lvgl_version": "v8"}, stage="generate")

    def test_non_authoritative_preview_cannot_verify_run(self) -> None:
        run = lvgl_run.create_run(
            design_path=str(self.design),
            display={"width": 480, "height": 800},
            lvgl_version="v9",
            artifacts={},
        )
        render_path = Path(self.tempdir.name) / "render.png"
        render_path.write_bytes(self.design.read_bytes())
        lvgl_run.record_stage(
            run["run_id"],
            stage="render",
            status="rendered",
            artifacts={"render_path": str(render_path)},
            details={"authoritative": False},
        )
        # Comparison cannot load the dummy bytes as an image, but its run
        # state must not become verified after the failed/preview path.
        result = compare_ui({"run_id": run["run_id"], "actual_path": str(render_path)})
        self.assertNotEqual(result.get("run_status"), "verified")

    def test_tampered_manifest_is_rejected(self) -> None:
        run = lvgl_run.create_run(
            design_path=str(self.design),
            display={"width": 480, "height": 800},
            lvgl_version="v9",
            artifacts={},
        )
        path = lvgl_run.manifest_path(run["run_id"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["status"] = "verified"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "event does not match manifest|status does not match"):
            lvgl_run.load_run(run["run_id"])

    def test_verified_run_can_apply_without_name_error(self) -> None:
        generated = Path(self.tempdir.name) / "generated"
        generated.mkdir()
        page = generated / "page.c"
        page.write_text("int page;\n", encoding="utf-8")
        run = lvgl_run.create_run(
            design_path=str(self.design),
            display={"width": 480, "height": 800},
            lvgl_version="v9",
            artifacts={},
        )
        lvgl_run.record_stage(
            run["run_id"],
            stage="generate",
            status="generated",
            artifacts={"c_path": str(page), "output_dir": str(generated)},
        )
        lvgl_run.record_stage(run["run_id"], stage="compare", status="verified", artifacts={})
        result = apply_patch({"run_id": run["run_id"], "target_dir": str(Path(self.tempdir.name) / "target")})
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "dry_run")


if __name__ == "__main__":
    unittest.main()
