import json
from pathlib import Path

from mcp.asset_contract import validate_initial_manifest
from tests.ui_testkit_evaluate import passes_quality_gate


ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "tests" / "ui_cases" / "interactive_scene_favorited"


def test_real_case_contract_and_inputs_exist() -> None:
    case = json.loads((CASE_DIR / "case.json").read_text(encoding="utf-8"))
    manifest = json.loads((CASE_DIR / "initial_asset_manifest.json").read_text(encoding="utf-8"))
    assert validate_initial_manifest(manifest)["valid"]
    assert (ROOT / case["design"]).is_file()
    assert (ROOT / case["ui_dir"] / "assets").is_dir()
    assert len(case["quality_regions"]) == 3
    assert case["quality_profile"] == "mvp_90"


def test_testkit_compiles_real_page_without_scene_protocol() -> None:
    cmake = (ROOT / "native" / "lvgl_ui_testkit" / "CMakeLists.txt").read_text(encoding="utf-8")
    main = (ROOT / "native" / "lvgl_ui_testkit" / "src" / "testkit_main.c").read_text(encoding="utf-8")
    assert "${UI_GENERATED_SOURCES}" in cmake
    assert "ui_test_page_create(screen)" in main
    assert "ui_test_page_destroy()" in main
    assert "scene_decoder" not in cmake
    assert "scene.bin" not in main


def test_generated_v9_code_uses_public_event_api_and_valid_opacity() -> None:
    codegen = (ROOT / "mcp" / "codegen.py").read_text(encoding="utf-8")
    scene = (ROOT / "mcp" / "interactive_scene_auto.py").read_text(encoding="utf-8")
    assert "lv_obj_send_event(msg->target" in codegen
    assert "lv_event_send(msg->target" not in codegen
    assert "LV_OPA_24" not in scene
    assert "LV_OPA_32" not in scene


def test_90_percent_gate_requires_all_dimensions() -> None:
    passing = {
        "hard_gates_pass": True,
        "total_score": 9000,
        "metrics": {"global_ssim": 0.90, "critical_region_ssim": 0.90, "pixel_similarity": 0.90},
    }
    assert passes_quality_gate(passing)
    for key in ("global_ssim", "critical_region_ssim", "pixel_similarity"):
        candidate = json.loads(json.dumps(passing))
        candidate["metrics"][key] = 0.899999
        assert not passes_quality_gate(candidate)
