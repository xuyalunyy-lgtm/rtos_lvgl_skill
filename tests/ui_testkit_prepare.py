"""Prepare a generated UI package for the native LVGL UI TestKit."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.high_level_tools import generate_ui  # noqa: E402

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    case_path = args.case.resolve()
    case = json.loads(case_path.read_text(encoding="utf-8"))
    ui_dir = (ROOT / case["ui_dir"]).resolve()
    manifest_path = (ROOT / case["initial_asset_manifest"]).resolve()
    output = args.output.resolve()
    for key in ("create_function", "destroy_function"):
        if not IDENTIFIER.fullmatch(str(case.get(key, ""))):
            raise SystemExit(f"invalid {key}")
    if not IDENTIFIER.fullmatch(str(case.get("id", ""))):
        raise SystemExit("case id must be a C-safe identifier")
    page_header = str(case["page_header"])
    if Path(page_header).name != page_header or not page_header.endswith(".h"):
        raise SystemExit("page_header must be a local header name")

    result = generate_ui({
        "ui_dir": str(ui_dir),
        "asset_manifest_path": str(manifest_path),
        "strict_asset_contract": True,
        "delivery_mode": "final_only",
        # Native TestKit consumes the resolution report before its ephemeral
        # CI workspace is discarded, so this diagnostic path opts out of the
        # normal final-only cleanup policy.
        "cleanup_intermediates": False,
        "output_dir": str(output.relative_to(ROOT)),
    })
    if not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    adapter = output / "ui_test_adapter.c"
    adapter.write_text(
        '#include "lvgl_ui_testkit.h"\n'
        f'#include "{page_header}"\n\n'
        f'lv_obj_t *ui_test_page_create(lv_obj_t *parent) {{ return {case["create_function"]}(parent); }}\n'
        f'void ui_test_page_destroy(void) {{ {case["destroy_function"]}(); }}\n'
        f'const char *ui_test_page_name(void) {{ return "{case["id"]}"; }}\n',
        encoding="utf-8", newline="\n",
    )
    delivery_files = sorted(path for path in output.iterdir() if path.is_file())
    evidence_dir = Path(str(result.get("evidence_dir", "")))
    resolution_report_path = evidence_dir / "asset_resolution_report.json"
    resolution_report = json.loads(resolution_report_path.read_text(encoding="utf-8")) if resolution_report_path.is_file() else {"errors": ["asset resolution report missing"]}
    report = {
        "schema_version": "1.0",
        "case": case["id"],
        "status": result["status"],
        "initial_manifest_sha256": _sha256(manifest_path),
        "design_sha256": _sha256((ROOT / case["design"]).resolve()),
        "delivery_files": [{"name": path.name, "sha256": _sha256(path)} for path in delivery_files],
        "symbols": result.get("symbols", []),
        "fonts": result.get("font_sources", []),
        "resource_closure": result.get("resource_closure", {}),
        "asset_resolution_errors": resolution_report.get("errors", []),
        "evidence_dir": result.get("evidence_dir"),
    }
    report_path = output.parent / "build_input_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "generated_dir": str(output), "report": str(report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
