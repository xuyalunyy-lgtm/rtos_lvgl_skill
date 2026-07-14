"""Publish the minimal compilable multi-page LVGL delivery."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.assets import find_lv_font_conv, unique_glyph_text


SEMANTIC_PAGES = (
    "home_default",
    "home_schedule",
    "push_interactive_favorited",
    "status_device_initial",
)


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _copy_sources(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".c", ".h"}:
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _collect_fonts(semantic_dir: Path) -> dict[str, dict[str, Any]]:
    fonts: dict[str, dict[str, Any]] = {}
    for page_id in SEMANTIC_PAGES:
        spec_path = semantic_dir / page_id / "ui_spec.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        sources = {
            str(item["symbol"]): Path(str(item["source"]))
            for item in spec.get("fonts", [])
        }
        for node in spec.get("nodes", []):
            if node.get("type") != "label":
                continue
            symbol = str(node.get("styles", {}).get("font_id", ""))
            if not symbol:
                continue
            match = re.search(r"_(\d+)$", symbol)
            if not match or symbol not in sources:
                raise ValueError(f"cannot resolve font source or size for {page_id}:{symbol}")
            source = sources[symbol].resolve()
            entry = fonts.setdefault(symbol, {"size": int(match.group(1)), "source": source, "texts": []})
            if entry["source"] != source or entry["size"] != int(match.group(1)):
                raise ValueError(f"conflicting font definition for {symbol}")
            entry["texts"].append(str(node.get("text", "")))
    return fonts


def _generate_fonts(semantic_dir: Path, delivery: Path) -> list[Path]:
    converter = find_lv_font_conv()
    if not converter:
        raise RuntimeError("lv_font_conv is required to publish the merged font bundle")
    generated: list[Path] = []
    fonts = _collect_fonts(semantic_dir)
    for symbol, item in sorted(fonts.items()):
        source = Path(item["source"])
        if not source.is_file():
            raise FileNotFoundError(f"font source not found: {source}")
        output = delivery / f"{symbol}.c"
        command = [
            converter,
            "--font", str(source),
            "--symbols", unique_glyph_text("\n".join(item["texts"])),
            "--size", str(item["size"]),
            "--bpp", "4",
            "--no-compress",
            "--format", "lvgl",
            "--lv-include", "lvgl.h",
            "--lv-font-name", symbol,
            "-o", str(output),
        ]
        process = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
        if process.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"font generation failed for {symbol}: {process.stderr[-500:]}")
        generated.append(output)
    header = delivery / "ui_auto_fonts.h"
    header.write_text(
        "#ifndef UI_AUTO_FONTS_H\n#define UI_AUTO_FONTS_H\n#include \"lvgl.h\"\n\n"
        + "\n".join(f"LV_FONT_DECLARE({path.stem});" for path in generated)
        + "\n\n#endif\n",
        encoding="utf-8",
        newline="\n",
    )
    return generated


def _write_cmake(delivery: Path) -> Path:
    sources = sorted(path.relative_to(delivery).as_posix() for path in delivery.rglob("*.c"))
    cmake = delivery / "ui_generated.cmake"
    cmake.write_text(
        "set(UI_GENERATED_SOURCES\n"
        + "".join(f'    "${{CMAKE_CURRENT_LIST_DIR}}/{path}"\n' for path in sources)
        + ")\n",
        encoding="utf-8",
        newline="\n",
    )
    return cmake


def publish(app_dir: Path, semantic_dir: Path, delivery: Path) -> dict[str, Any]:
    artifacts_root = (ROOT / "artifacts").resolve()
    app_dir = app_dir.resolve()
    semantic_dir = semantic_dir.resolve()
    delivery = delivery.resolve()
    if not _contained(delivery, artifacts_root):
        raise ValueError("delivery must be inside artifacts/")
    if not app_dir.is_dir() or not semantic_dir.is_dir():
        raise FileNotFoundError("app and semantic directories must exist")
    if delivery.exists():
        shutil.rmtree(delivery)
    delivery.mkdir(parents=True)

    for directory in ("app", "pages", "presenters"):
        _copy_sources(app_dir / directory, delivery / directory)
    for page_id in SEMANTIC_PAGES:
        firmware = semantic_dir / page_id / "firmware"
        target = delivery / "pages" / page_id
        for suffix in ("c", "h"):
            source = firmware / f"ui_page_{page_id}.{suffix}"
            shutil.copy2(source, target / source.name)

    assets_dir = semantic_dir / "assets"
    for path in sorted(assets_dir.glob("UI_IMG_*.c")):
        shutil.copy2(path, delivery / path.name)
    shutil.copy2(assets_dir / "ui_auto_assets.h", delivery / "ui_auto_assets.h")
    font_sources = _generate_fonts(semantic_dir, delivery)
    cmake = _write_cmake(delivery)

    forbidden = [
        path for path in delivery.rglob("*")
        if path.is_file() and path.suffix.lower() not in {".c", ".h", ".cmake"}
    ]
    if forbidden:
        raise RuntimeError("non-delivery artifacts were published: " + ", ".join(str(path) for path in forbidden))
    files = sorted(path for path in delivery.rglob("*") if path.is_file())
    return {
        "ok": True,
        "delivery_dir": str(delivery),
        "files": len(files),
        "c_sources": sum(path.suffix == ".c" for path in files),
        "headers": sum(path.suffix == ".h" for path in files),
        "font_sources": [path.name for path in font_sources],
        "cmake": str(cmake),
        "sha256": hashlib.sha256(
            "".join(
                hashlib.sha256(path.read_bytes()).hexdigest()
                for path in files
            ).encode("ascii")
        ).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", type=Path, required=True)
    parser.add_argument("--semantic-dir", type=Path, required=True)
    parser.add_argument("--delivery-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    result = publish(args.app_dir, args.semantic_dir, args.delivery_dir)
    if args.summary:
        summary = args.summary.resolve()
        if not _contained(summary, (ROOT / "artifacts").resolve()):
            raise ValueError("summary must be inside artifacts/")
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
