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
import shutil
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
        lvgl_version: "v9" only (v8 not yet supported)

    Returns:
        {"ok": bool, "path": str, "platform": str, "version": str, "sha256": str}
    """
    if lvgl_version != "v9":
        return {
            "ok": False,
            "error": f"LVGL {lvgl_version} not supported. Only v9 is currently available.",
            "status": "unsupported_version",
        }

    # A bundled binary is trusted only when it has a matching release manifest.
    manifest = _load_manifest()
    plat = detect_platform()
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("scene_protocol_version") != 1:
        return {
            "ok": False,
            "error": "Missing or incompatible simulator manifest",
            "status": "integrity_check_failed",
        }
    entry = manifest.get("runners", {}).get(f"{plat}/{lvgl_version}") if manifest else None
    if not isinstance(entry, dict):
        return {
            "ok": False,
            "error": f"No manifest entry for {plat}/{lvgl_version}",
            "status": "integrity_check_failed",
        }
    expected = entry.get("sha256")
    expected_file = entry.get("file")
    if not isinstance(expected_file, str):
        return {"ok": False, "error": "Runner manifest file is invalid", "status": "integrity_check_failed"}
    file_parts = Path(expected_file).parts
    if len(file_parts) != 2 or file_parts[0] != plat or file_parts[1] in {"", ".", ".."}:
        return {"ok": False, "error": "Runner manifest file is outside its platform directory", "status": "integrity_check_failed"}
    runner_path = SIMULATOR_DIR / file_parts[0] / file_parts[1]
    if not runner_path.is_file():
        return {
            "ok": False,
            "error": f"Runner not found: {runner_path}",
            "status": "environment_unavailable",
            "platform": plat,
            "version": lvgl_version,
            "available_platforms": _list_available_platforms(),
        }

    sha256 = _file_hash(runner_path)
    if not isinstance(expected, str) or len(expected) != 64 or expected != sha256:
        return {
            "ok": False,
            "error": f"SHA256 mismatch: expected {expected}, got {sha256}",
            "status": "integrity_check_failed",
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
    return [
        d.name for d in SIMULATOR_DIR.iterdir()
        if d.is_dir() and any(d.glob("lvgl_sim_v9*"))
    ]


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


def _path_for_runner(path: str) -> str:
    """Return a path the bundled Windows runner can reopen reliably.

    Its filesystem adapters use fixed native path buffers.  Workspace-relative
    paths avoid corruption seen with long absolute paths for output and binary
    font files.  The simulator inherits this process's working directory, so
    use a relative path whenever both locations are on the same drive.
    """
    source = Path(path).resolve()
    try:
        return os.path.relpath(source, start=Path.cwd())
    except ValueError:
        # Different Windows drive: retain the original absolute path and let
        # the runner report its normal font-load error.
        return str(source)


def _stage_windows_runner(runner_path: str, output_dir: str) -> Path | None:
    """Stage the Windows runner away from its bundle directory for one run.

    The LVGL Windows binary-font backend is sensitive to its executable
    directory.  A short-lived sibling copy of the render output avoids that
    native limitation without weakening the manifest validation performed by
    ``resolve_runner`` before this function is reached.
    """
    if platform.system().lower() != "windows":
        return None
    source = Path(runner_path).resolve()
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / ".lvgl_sim_runner.exe"
    if source == target:
        return None
    shutil.copy2(source, target)
    return target


def run_simulator(
    runner_path: str,
    scene_path: str,
    output_dir: str,
    width: int = 480,
    height: int = 800,
    render_time_ms: int = 100,
    timeout: int = 20,
    asset_pack_path: str | None = None,
    font_bindings: dict[str, str] | None = None,
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
    staged_runner: Path | None = None
    cmd = [runner_path]
    try:
        staged_runner = _stage_windows_runner(runner_path, output_dir)
        executable = str(staged_runner) if staged_runner else runner_path
        cmd = [
            executable,
            "--scene", _path_for_runner(scene_path),
            "--output", _path_for_runner(output_dir),
            "--width", str(width),
            "--height", str(height),
            "--render-time", str(render_time_ms),
        ]
        if asset_pack_path:
            cmd.extend(["--assets", _path_for_runner(asset_pack_path)])
        for font_id, font_path in sorted((font_bindings or {}).items()):
            cmd.extend(["--font", f"{font_id}={_path_for_runner(font_path)}"])

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

        # A successful process is not enough: enforce the runner output contract.
        ppm_path = Path(output_dir) / "render.ppm"
        tree_path = Path(output_dir) / "object_tree.bin"
        if proc.returncode != 0 or not result.get("ok"):
            result["ok"] = False
            result.setdefault("error", "Simulator returned failure")
            return result
        if not ppm_path.is_file() or ppm_path.stat().st_size <= 100:
            result["ok"] = False
            result["error"] = "Simulator did not produce a valid render.ppm"
            return result
        if not tree_path.is_file() or tree_path.stat().st_size <= 20:
            result["ok"] = False
            result["error"] = "Simulator did not produce a valid object_tree.bin"
            return result

        result["tree"] = str(tree_path)
        # Convert PPM to PNG if possible
        png_path = Path(output_dir) / "render.png"
        if ppm_path.is_file():
            _ppm_to_png(ppm_path, png_path)
            if png_path.is_file():
                result["render_png"] = str(png_path)

        # Read evidence files produced by runner
        asset_report_path = Path(output_dir) / "asset_load_report.json"
        if asset_report_path.is_file():
            try:
                result["asset_load_report"] = json.loads(asset_report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        font_report_path = Path(output_dir) / "font_load_report.json"
        if font_report_path.is_file():
            try:
                result["font_load_report"] = json.loads(font_report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        caps_path = Path(output_dir) / "renderer_capabilities.json"
        if caps_path.is_file():
            try:
                result["renderer_capabilities"] = json.loads(caps_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        # Convert binary object tree to JSON
        if tree_path.is_file():
            try:
                from mcp.lvgl_ir.object_tree_reader import read_object_tree
                tree_json_path = Path(output_dir) / "object_tree.json"
                tree_json = read_object_tree(tree_path)
                tree_json_path.write_text(
                    json.dumps(tree_json, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n",
                )
                result["tree_json"] = str(tree_json_path)
                result["object_tree"] = tree_json
            except Exception:
                pass

        # Check for capability gaps
        unsupported = result.get("unsupported_opcodes", [])
        if unsupported:
            result["capability_gap"] = True
            result["capability_gap_opcodes"] = unsupported

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
    finally:
        if staged_runner:
            try:
                staged_runner.unlink(missing_ok=True)
            except OSError:
                pass


def run_runner_self_test(runner_path: str, timeout: int = 20) -> dict[str, Any]:
    """Execute the runner's built-in self-test and require JSON success."""
    cmd = [runner_path, "--self-test"]
    try:
        proc = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        result: dict[str, Any] = {"ok": False}
        for line in proc.stdout.strip().split("\n"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                result = parsed
                break
        result["exit_code"] = proc.returncode
        result["stderr"] = proc.stderr
        result["command"] = cmd
        if proc.returncode != 0 or not result.get("ok"):
            result["ok"] = False
            result.setdefault("error", "Runner self-test failed")
        return result
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Runner self-test timed out after {timeout}s", "command": cmd}
    except FileNotFoundError:
        return {"ok": False, "error": f"Runner not found: {runner_path}", "command": cmd}
    except Exception as e:
        return {"ok": False, "error": str(e), "command": cmd}


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
    parser.add_argument("--lvgl-version", default="v9", choices=["v9"])
    parser.add_argument("--assets", help="Optional asset.pack path")
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
        asset_pack_path=args.assets,
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
