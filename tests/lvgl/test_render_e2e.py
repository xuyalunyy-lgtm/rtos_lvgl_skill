"""End-to-end render test: UI Spec → scene.bin → render + object tree.

This test verifies the full pipeline works without a native runner.
When a native runner is available, it also tests real rendering.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "mcp"))

from lvgl_ir.scene_encoder import encode_spec
from lvgl_sim_resolver import resolve_runner, run_simulator


# ── Test spec ─────────────────────────────────────────────────────


TEST_SPEC = {
    "schema_version": "2.0",
    "page_name": "e2e_test",
    "display": {"width": 480, "height": 800},
    "lvgl_version": "v9",
    "theme": {"primary_color": "#2196F3", "background_color": "#F5F5FA"},
    "nodes": [
        {"id": "root", "type": "screen"},
        {"id": "header", "type": "container", "parent_id": "root",
         "layout": {"mode": "flex-row", "gap": 10},
         "styles": {"bg_color": "#2196F3", "height": 50}},
        {"id": "title", "type": "label", "parent_id": "header", "text": "E2E Test"},
        {"id": "content", "type": "container", "parent_id": "root"},
        {"id": "btn", "type": "button", "parent_id": "content",
         "styles": {"bg_color": "#4CAF50", "radius": 12}},
        {"id": "bar", "type": "bar", "parent_id": "content", "value": 60,
         "styles": {"width": 200, "height": 20}},
    ],
}


# ── Scene encoder tests ───────────────────────────────────────────


class TestSceneEncoderE2E:
    def test_encode_test_spec(self, tmp_path):
        scene_bytes = encode_spec(TEST_SPEC)
        scene_path = tmp_path / "scene.bin"
        scene_path.write_bytes(scene_bytes)

        assert scene_path.exists()
        assert scene_path.stat().st_size > 32

    def test_encode_all_golden_pages(self, tmp_path):
        golden_dir = ROOT / "golden_pages"
        if not golden_dir.exists():
            pytest.skip("No golden_pages directory")

        for page_dir in sorted(golden_dir.iterdir()):
            if not page_dir.is_dir():
                continue
            spec_path = page_dir / "expected" / "ui_spec.json"
            if not spec_path.is_file():
                continue

            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            scene_bytes = encode_spec(spec)

            assert len(scene_bytes) > 32, f"{page_dir.name}: scene too small"
            # Verify header
            magic = int.from_bytes(scene_bytes[:4], "little")
            assert magic == 0x004E4353, f"{page_dir.name}: bad magic"


# ── Native runner tests (skip if unavailable) ─────────────────────


class TestNativeRunnerE2E:
    @pytest.fixture
    def runner_info(self):
        info = resolve_runner("v9")
        if not info["ok"]:
            pytest.skip(f"Runner not available: {info.get('error')}")
        return info

    def test_runner_self_test(self, runner_info, tmp_path):
        result = run_simulator(
            runner_info["path"],
            str(tmp_path / "dummy.bin"),  # won't be used for --self-test
            str(tmp_path),
        )
        # self-test is triggered by --self-test flag, not by scene
        # This test just verifies the binary exists and is executable
        assert runner_info["path"]

    def test_render_test_spec(self, runner_info, tmp_path):
        # Encode scene
        scene_bytes = encode_spec(TEST_SPEC)
        scene_path = tmp_path / "scene.bin"
        scene_path.write_bytes(scene_bytes)

        # Render
        result = run_simulator(
            runner_info["path"],
            str(scene_path),
            str(tmp_path / "render"),
            width=480,
            height=800,
        )

        assert result["ok"], f"Render failed: {result.get('error')}"

        # Verify outputs
        ppm_path = tmp_path / "render" / "render.ppm"
        tree_path = tmp_path / "render" / "object_tree.bin"

        assert ppm_path.exists(), "render.ppm not found"
        assert tree_path.exists(), "object_tree.bin not found"
        assert ppm_path.stat().st_size > 100, "render.ppm too small"
        assert tree_path.stat().st_size > 20, "object_tree.bin too small"

    def test_render_golden_pages(self, runner_info, tmp_path):
        golden_dir = ROOT / "golden_pages"
        if not golden_dir.exists():
            pytest.skip("No golden_pages directory")

        for page_dir in sorted(golden_dir.iterdir()):
            if not page_dir.is_dir():
                continue
            spec_path = page_dir / "expected" / "ui_spec.json"
            if not spec_path.is_file():
                continue

            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            scene_bytes = encode_spec(spec)

            page_tmp = tmp_path / page_dir.name
            scene_path = page_tmp / "scene.bin"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_bytes(scene_bytes)

            result = run_simulator(
                runner_info["path"],
                str(scene_path),
                str(page_tmp / "render"),
                width=spec.get("display", {}).get("width", 480),
                height=spec.get("display", {}).get("height", 800),
            )

            assert result["ok"], f"{page_dir.name}: render failed: {result.get('error')}"
