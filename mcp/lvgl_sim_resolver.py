"""LVGL Simulator Resolver — finds and runs the built-in headless simulator.

Locates the pre-compiled LVGL simulator binary for the current platform,
verifies its SHA256, and executes it in an isolated subprocess.

Usage:
    python mcp/lvgl_sim_resolver.py --scene scene.bin --output artifacts/render
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SIMULATOR_DIR = ROOT / "runtime" / "simulator"

# ── Platform detection ────────────────────────────────────────────


def detect_platform() -> str:
    """Detect current platform key."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        return "win-x64"
    elif system == "linux":
        if machine in ("aarch64", "arm64"):
            return "linux-arm64"
        return "linux-x64"
    elif system == "darwin":
        if machine == "arm64":
            return "macos-arm64"
        return "macos-x64"
    else:
        return f"{system}-{machine}"


# ── Runner resolution ─────────────────────────────────────────────


def resolve_runner(lvgl_version: str = "v9") -> dict[str, Any]:
    """Find the built-in LVGL simulator binary.

    Args:
        lvgl_version: "v8" or "v9"

    Returns:
        {"ok": bool, "path": str, "platform": str, "version": str, "sha256": str}
    """
    plat = detect_platform()
    runner_name = f"lvgl_sim_{lvgl_version}"
    if platform.system().lower() == "windows":
        runner_name += ".exe"

    runner_path = SIMULATOR_DIR / plat / runner_name

    if not runner_path.is_file():
        return {
            "ok": False,
            "error": f"Runner not found: {runner_path}",
            "platform": plat,
            "version": lvgl_version,
            "available_platforms": _list_available_platforms(),
        }

    # Compute SHA256
    sha256 = _file_hash(runner_path)

    # Verify against manifest
    manifest = _load_manifest()
    if manifest:
        expected = manifest.get(plat, {}).get(lvgl_version, {}).get("sha256")
        if expected and expected != sha256:
            return {
                "ok": False,
                "error": f"SHA256 mismatch: expected {expected}, got {sha256}",
                "path": str(runner_path),
            }

    return {
        "ok": True,
        "path": str(runner_path),
        "platform": plat,
        "version": lvgl_version,
        "sha256": sha256,
    }


def _list_available_platforms() -> list[str]:
    """List platforms with available runners."""
    if not SIMULATOR_DIR.is_dir():
        return []
    return [d.name for d in SIMULATOR_DIR.iterdir() if d.is_dir() and (d / "lvgl_sim_v9.exe").is_file() or (d / "lvgl_sim_v9").is_file()]


def _file_hash(path: Path) -> str:
    """SHA256 hash of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest() -> dict[str, Any] | None:
    """Load simulator manifest.json."""
    manifest_path = SIMULATOR_DIR / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── Runner execution ──────────────────────────────────────────────


def run_simulator(
    runner_path: str,
    scene_path: str,
    output_dir: str,
    width: int = 480,
    height: int = 800,
    render_time_ms: int = 100,
    timeout: int = 20,
) -> dict[str, Any]:
    """Run the LVGL simulator in an isolated subprocess.

    Args:
        runner_path: Path to simulator binary.
        scene_path: Path to scene.bin.
        output_dir: Output directory for render.ppm and object_tree.bin.
        width: Display width.
        height: Display height.
        render_time_ms: Render time in milliseconds.
        timeout: Subprocess timeout in seconds.

    Returns:
        Result dict with render and tree paths.
    """
    cmd = [
        runner_path,
        "--scene", scene_path,
        "--output", output_dir,
        "--width", str(width),
        "--height", str(height),
        "--render-time", str(render_time_ms),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        # Parse JSON output from stdout
        result = None
        for line in proc.stdout.strip().split("\n"):
            try:
                result = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

        if result is None:
            result = {"ok": proc.returncode == 0}

        result["exit_code"] = proc.returncode
        result["stderr"] = proc.stderr
        result["command"] = cmd

        # Convert PPM to PNG if possible
        ppm_path = Path(output_dir) / "render.ppm"
        png_path = Path(output_dir) / "render.png"
        if ppm_path.is_file():
            _ppm_to_png(ppm_path, png_path)
            if png_path.is_file():
                result["render_png"] = str(png_path)

        return result

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"Simulator timed out after {timeout}s",
            "command": cmd,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "error": f"Runner not found: {runner_path}",
            "command": cmd,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "command": cmd,
        }


def _ppm_to_png(ppm_path: Path, png_path: Path):
    """Convert PPM to PNG using Pillow or stdlib."""
    try:
        from PIL import Image
        img = Image.open(str(ppm_path))
        img.save(str(png_path))
    except ImportError:
        # Minimal PPM to PNG using stdlib
        _ppm_to_png_stdlib(ppm_path, png_path)


def _ppm_to_png_stdlib(ppm_path: Path, png_path: Path):
    """Convert PPM P6 to PNG using only stdlib."""
    import struct
    import zlib

    with open(ppm_path, "rb") as f:
        # Read PPM header
        magic = f.readline().strip()
        if magic != b"P6":
            return
        # Skip comments
        line = f.readline()
        while line.startswith(b"#"):
            line = f.readline()
        # Read dimensions
        dims = line.strip().split()
        width, height = int(dims[0]), int(dims[1])
        max_val = int(f.readline().strip())
        # Read pixels
        pixels = f.read()

    # Convert to PNG
    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)

    # Build raw image data (RGB)
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter none
        for x in range(width):
            idx = (y * width + x) * 3
            raw.extend(pixels[idx:idx + 3])

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)

    png_path.write_bytes(
        b"\x89PNG\r\n\x1a\n" +
        chunk(b"IHDR", ihdr) +
        chunk(b"IDAT", idat) +
        chunk(b"IEND", b"")
    )


# ── CLI ───────────────────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True, help="Path to scene.bin")
    parser.add_argument("--output", default="artifacts/render", help="Output directory")
    parser.add_argument("--lvgl-version", default="v9", choices=["v8", "v9"])
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Resolve runner
    runner = resolve_runner(args.lvgl_version)
    if not runner["ok"]:
        if args.json:
            print(json.dumps(runner, indent=2))
        else:
            print(f"ERROR: {runner.get('error')}")
        return 1

    # Run simulator
    Path(args.output).mkdir(parents=True, exist_ok=True)
    result = run_simulator(
        runner["path"],
        args.scene,
        args.output,
        args.width,
        args.height,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["ok"]:
            print(f"Render: {result.get('render_png', 'N/A')}")
            print(f"Tree: {result.get('tree', 'N/A')}")
        else:
            print(f"ERROR: {result.get('error')}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
