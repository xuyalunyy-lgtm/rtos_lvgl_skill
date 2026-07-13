from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path
from typing import Any

try:
    from assets import convert_image_to_png, read_image
    from schemas import DISPLAY_CONFIG, REGRESSION_SANDBOX_CONFIG, ROOT
    from codegen import generate_lvgl_layout_spec, require_choice, resolve_path, safe_symbol
except ImportError:  # pragma: no cover - package import fallback
    from .assets import convert_image_to_png, read_image
    from .schemas import DISPLAY_CONFIG, REGRESSION_SANDBOX_CONFIG, ROOT
    from .codegen import generate_lvgl_layout_spec, require_choice, resolve_path, safe_symbol

def prepare_lvgl_sim_project(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_sim"))
    output_dir.mkdir(parents=True, exist_ok=True)
    lvgl_root = str(args.get("lvgl_root") or os.environ.get("LVGL_ROOT") or "")
    readme = output_dir / "README.md"
    readme.write_text(
        textwrap.dedent(
            f"""\
            # LVGL simulator skeleton

            This directory is a generated placeholder for local LVGL UI checks.

            Required before native build:
            - Set `LVGL_ROOT` to a local LVGL checkout.
            - Copy generated `ui_*.c/.h` files into the app source list.

            Optional (for SDL2 display):
            - Install/configure SDL2 and expose `SDL2_DIR` or `SDL_ROOT`.

            Detected LVGL_ROOT: {lvgl_root or "not configured"}
            """
        ),
        encoding="utf-8",
        newline="\n",
    )
    available = bool(lvgl_root and Path(lvgl_root).exists())
    return {
        "ok": True,
        "available": available,
        "status": "ready" if available else "not_available",
        "artifacts": [str(readme)],
        "message": "simulator environment detected" if available else "set LVGL_ROOT and SDL2_DIR/SDL_ROOT to build locally",
    }

def sandbox_template_dir() -> Path:
    return ROOT / "assets" / "lvgl_regression_sandbox_template"

def _copytree_merge(src: Path, dst: Path) -> None:
    import shutil

    if not src.is_dir():
        raise ValueError(f"sandbox template not found: {src}")
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)

def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

def _tool_available(name: str) -> str | None:
    import shutil

    found = shutil.which(name)
    return str(Path(found).resolve()) if found else None

def _run_process(argv: list[str], *, cwd: Path, timeout: int, path_prefix: str = "") -> dict[str, Any]:
    import subprocess

    env = os.environ.copy()
    if path_prefix:
        env["PATH"] = path_prefix + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": -1,
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
            "timeout": True,
            "message": f"process timed out after {timeout}s",
        }
    return {"argv": argv, "cwd": str(cwd), "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "timeout": False}

def prepare_lvgl_regression_sandbox(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_regression_sandbox"))
    output_dir.mkdir(parents=True, exist_ok=True)
    _copytree_merge(sandbox_template_dir(), output_dir)

    config = dict(REGRESSION_SANDBOX_CONFIG)
    config["width"] = int(args.get("width", DISPLAY_CONFIG["display"]["width"]))
    config["height"] = int(args.get("height", DISPLAY_CONFIG["display"]["height"]))
    config["lvgl_root"] = str(args.get("lvgl_root", ""))
    config["sdl2_root"] = str(args.get("sdl2_root", ""))
    config["sdl2_dir"] = str(args.get("sdl2_dir", ""))
    config["sdl2_bin"] = str(args.get("sdl2_bin", ""))
    config["ui_under_test_dir"] = str(args.get("ui_under_test_dir", ""))
    config["ui_entry_function"] = str(args.get("ui_entry_function", ""))
    config["ui_header"] = str(args.get("ui_header", ""))
    config["prepared_from"] = str(sandbox_template_dir())
    if config["ui_entry_function"]:
        header = config["ui_header"] or "ui_under_test.h"
        entry = safe_symbol(config["ui_entry_function"])
        (output_dir / "src" / "ui_under_test_default.c").write_text(
            textwrap.dedent(
                f"""\
                #include "ui_under_test_default.h"
                #include "{header}"

                extern lv_obj_t *{entry}(lv_obj_t *parent);

                lv_obj_t *ui_under_test_create(lv_obj_t *parent)
                {{
                    return {entry}(parent);
                }}
                """
            ),
            encoding="utf-8",
            newline="\n",
        )
    _write_json(output_dir / "sandbox_config.json", config)

    return {
        "ok": True,
        "sandbox_dir": str(output_dir),
        "template_dir": str(sandbox_template_dir()),
        "artifacts": [str(output_dir / "sandbox_config.json"), str(output_dir / "CMakeLists.txt")],
        "next_steps": ["build_lvgl_regression_sandbox", "run_lvgl_regression_sandbox", "compare_lvgl_screenshot"],
    }

def _sandbox_config(sandbox_dir: Path) -> dict[str, Any]:
    path = sandbox_dir / "sandbox_config.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return dict(REGRESSION_SANDBOX_CONFIG)

def build_lvgl_regression_sandbox(args: dict[str, Any]) -> dict[str, Any]:
    sandbox_dir = resolve_path(args.get("sandbox_dir"))
    if not (sandbox_dir / "CMakeLists.txt").is_file():
        raise ValueError(f"not a regression sandbox: {sandbox_dir}")
    build_dir = resolve_path(args.get("build_dir", sandbox_dir / "build"))
    build_dir.mkdir(parents=True, exist_ok=True)
    cmake = str(args.get("cmake") or _tool_available("cmake") or "")
    if not cmake:
        return {"ok": True, "available": False, "status": "not_available", "message": "cmake not found", "artifacts": []}

    config = _sandbox_config(sandbox_dir)
    lvgl_root = str(args.get("lvgl_root") or config.get("lvgl_root") or os.environ.get("LVGL_ROOT") or "")
    sdl2_root = str(args.get("sdl2_root") or config.get("sdl2_root") or os.environ.get("SDL2_ROOT") or "")
    sdl2_dir = str(args.get("sdl2_dir") or config.get("sdl2_dir") or os.environ.get("SDL2_DIR") or "")
    ui_under_test_dir = str(args.get("ui_under_test_dir") or config.get("ui_under_test_dir") or "")
    width = int(args.get("width", config.get("width", DISPLAY_CONFIG["display"]["width"])))
    height = int(args.get("height", config.get("height", DISPLAY_CONFIG["display"]["height"])))
    generator = str(args.get("generator", ""))
    toolchain_bin = str(args.get("toolchain_bin") or os.environ.get("MINGW_BIN") or "")
    ninja_bin = str(args.get("ninja_bin") or os.environ.get("NINJA_BIN") or "")
    c_compiler = str(args.get("c_compiler") or os.environ.get("CC") or "")
    cxx_compiler = str(args.get("cxx_compiler") or os.environ.get("CXX") or "")
    toolchain_evidence: dict[str, Any] = {"source": "user_or_system"}

    # Fallback to bundled toolchain if no compiler found
    use_bundled = args.get("use_bundled_toolchain", True)
    if use_bundled and not c_compiler and not toolchain_bin:
        try:
            from toolchain_resolver import ensure_toolchain as _ensure_tc
            _tc = _ensure_tc()
            if _tc["ok"]:
                toolchain_bin = _tc["bin_dir"]
                c_compiler = _tc["gcc"]
                ninja_bin = _tc["ninja"]
                if not generator:
                    generator = "Ninja"
                toolchain_evidence = {
                    "source": "bundled",
                    "platform": _tc["platform"],
                    "version": _tc["version"],
                    "flavor": _tc["flavor"],
                }
        except Exception:
            pass  # bundled toolchain not available, continue with user-provided
    ninja_prefix = ""
    if ninja_bin:
        ninja_path = Path(ninja_bin)
        ninja_prefix = str(ninja_path.parent if ninja_path.name.lower() in {"ninja", "ninja.exe"} else ninja_path)
    ninja_available = bool(_tool_available("ninja") or (ninja_prefix and (Path(ninja_prefix) / "ninja.exe").is_file()))
    if not generator and ninja_available:
        generator = "Ninja"
    if not generator and toolchain_bin and (Path(toolchain_bin) / "mingw32-make.exe").is_file():
        generator = "MinGW Makefiles"
    timeout = int(args.get("timeout_seconds", 120))
    parallel = int(args.get("parallel", os.environ.get("LVGL_RENDER_PARALLEL", "4")))
    path_prefix = os.pathsep.join(part for part in (ninja_prefix, toolchain_bin) if part)

    configure = [cmake, "-S", str(sandbox_dir), "-B", str(build_dir), f"-DREGRESSION_WIDTH={width}", f"-DREGRESSION_HEIGHT={height}"]
    if generator:
        configure.extend(["-G", generator])
    if c_compiler:
        configure.append(f"-DCMAKE_C_COMPILER={c_compiler}")
    if cxx_compiler:
        configure.append(f"-DCMAKE_CXX_COMPILER={cxx_compiler}")
    if lvgl_root:
        configure.append(f"-DLVGL_ROOT={lvgl_root}")
    if sdl2_root:
        configure.append(f"-DSDL2_ROOT={sdl2_root}")
    if sdl2_dir:
        configure.append(f"-DSDL2_DIR={sdl2_dir}")
    configure.append(f"-DUI_UNDER_TEST_DIR={ui_under_test_dir}")
    configured = _run_process(configure, cwd=sandbox_dir, timeout=timeout, path_prefix=path_prefix)
    if configured["exit_code"] != 0:
        return {"ok": False, "available": True, "status": "configure_failed", "configure": configured, "artifacts": [str(build_dir)]}

    build_cmd = [cmake, "--build", str(build_dir), "--config", str(args.get("build_type", "Debug"))]
    if parallel > 1:
        build_cmd.extend(["--parallel", str(parallel)])
    built = _run_process(build_cmd, cwd=sandbox_dir, timeout=timeout, path_prefix=path_prefix)
    status = "built" if built["exit_code"] == 0 else ("timeout" if built.get("timeout") else "build_failed")
    return {
        "ok": built["exit_code"] == 0,
        "available": True,
        "status": status,
        "generator": generator,
        "path_prefix": path_prefix,
        "toolchain": toolchain_evidence,
        "configure": configured,
        "build": built,
        "artifacts": [str(build_dir)],
    }

def _guess_executable(sandbox_dir: Path, build_dir: Path) -> Path | None:
    names = ["lvgl_regression_sandbox.exe", "lvgl_regression_sandbox"]
    roots = [build_dir, build_dir / "Debug", build_dir / "Release", sandbox_dir / "bin"]
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    matches = list(build_dir.rglob("lvgl_regression_sandbox.exe")) + list(build_dir.rglob("lvgl_regression_sandbox"))
    return matches[0] if matches else None

def _scan_log(text: str, patterns: list[str]) -> list[str]:
    lower = text.lower()
    return [pattern for pattern in patterns if pattern.lower() in lower]

def run_lvgl_regression_sandbox(args: dict[str, Any]) -> dict[str, Any]:
    sandbox_dir = resolve_path(args.get("sandbox_dir"))
    build_dir = resolve_path(args.get("build_dir", sandbox_dir / "build"))
    executable = Path(str(args.get("executable"))) if args.get("executable") else _guess_executable(sandbox_dir, build_dir)
    if executable is None or not executable.is_file():
        return {"ok": True, "available": False, "status": "not_available", "message": "sandbox executable not found", "artifacts": []}

    output_dir = resolve_path(args.get("output_dir", sandbox_dir / "regression_out"))
    output_dir.mkdir(parents=True, exist_ok=True)
    timeout = int(args.get("timeout_seconds", REGRESSION_SANDBOX_CONFIG["timeout_seconds"]))
    config = _sandbox_config(sandbox_dir)
    toolchain_bin = str(args.get("toolchain_bin") or os.environ.get("MINGW_BIN") or "")
    if not toolchain_bin and args.get("use_bundled_toolchain", True):
        try:
            from toolchain_resolver import ensure_toolchain as _ensure_tc
            _tc = _ensure_tc()
            if _tc["ok"]:
                toolchain_bin = str(_tc["bin_dir"])
        except Exception:
            pass
    # SDL2 is optional — null display driver doesn't need SDL2.dll at runtime
    sdl2_bin = str(args.get("sdl2_bin") or config.get("sdl2_bin") or os.environ.get("SDL2_BIN") or "")
    sdl2_dir = Path(str(args.get("sdl2_dir") or config.get("sdl2_dir") or os.environ.get("SDL2_DIR") or ""))
    if not sdl2_bin and sdl2_dir:
        for candidate in (
            sdl2_dir.parent / "x86_64-w64-mingw32" / "bin",
            sdl2_dir.parent / "i686-w64-mingw32" / "bin",
            sdl2_dir.parent / "bin",
        ):
            if (candidate / "SDL2.dll").is_file():
                sdl2_bin = str(candidate)
                break
    path_prefix = os.pathsep.join(part for part in (sdl2_bin, toolchain_bin) if part)
    run = _run_process([str(executable)], cwd=sandbox_dir, timeout=timeout, path_prefix=path_prefix)
    log_path = output_dir / "run.log"
    log_text = run.get("stdout", "") + "\n" + run.get("stderr", "")
    log_path.write_text(log_text, encoding="utf-8", newline="\n")

    artifacts = [str(log_path)]
    produced_dir = build_dir / "regression"
    if produced_dir.is_dir():
        import shutil

        for pattern in ("*.ppm", "*.bmp", "*.png", "*.json"):
            for produced in produced_dir.glob(pattern):
                target = output_dir / produced.name
                shutil.copy2(produced, target)
                artifacts.append(str(target))

    issues = _scan_log(log_text, list(REGRESSION_SANDBOX_CONFIG["log_error_patterns"]))
    return {
        "ok": run["exit_code"] == 0 and not issues,
        "available": True,
        "status": "passed" if run["exit_code"] == 0 and not issues else "failed",
        "run": run,
        "runtime_path_prefix": path_prefix,
        "log_issues": issues,
        "artifacts": sorted(set(artifacts)),
    }

def _hash_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()

def compare_lvgl_screenshot(args: dict[str, Any]) -> dict[str, Any]:
    actual = resolve_path(args.get("actual_path"))
    baseline = resolve_path(args.get("baseline_path"))
    if not actual.is_file():
        raise ValueError(f"actual_path does not exist: {actual}")
    if not baseline.is_file():
        raise ValueError(f"baseline_path does not exist: {baseline}")
    max_changed_ratio = float(args.get("max_changed_ratio", REGRESSION_SANDBOX_CONFIG["pixel_threshold"]["max_changed_ratio"]))
    max_channel_delta = int(args.get("max_channel_delta", REGRESSION_SANDBOX_CONFIG["pixel_threshold"]["max_channel_delta"]))

    aw, ah, ap = read_image(actual)
    bw, bh, bp = read_image(baseline)
    if (aw, ah) != (bw, bh):
        return {
            "ok": False,
            "status": "dimension_mismatch",
            "actual": {"path": str(actual), "width": aw, "height": ah, "sha256": _hash_bytes(actual.read_bytes())},
            "baseline": {"path": str(baseline), "width": bw, "height": bh, "sha256": _hash_bytes(baseline.read_bytes())},
        }

    changed = 0
    max_delta = 0
    for a, b in zip(ap, bp):
        delta = max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))
        max_delta = max(max_delta, delta)
        if delta > max_channel_delta:
            changed += 1
    total = max(1, len(ap))
    changed_ratio = changed / total
    ok = changed_ratio <= max_changed_ratio
    return {
        "ok": ok,
        "status": "passed" if ok else "pixel_diff_failed",
        "width": aw,
        "height": ah,
        "changed_pixels": changed,
        "total_pixels": total,
        "changed_ratio": changed_ratio,
        "max_channel_delta": max_delta,
        "threshold": {"max_changed_ratio": max_changed_ratio, "max_channel_delta": max_channel_delta},
        "actual_sha256": _hash_bytes(actual.read_bytes()),
        "baseline_sha256": _hash_bytes(baseline.read_bytes()),
        "artifacts": [str(actual), str(baseline)],
    }

def list_lvgl_regression_artifacts(args: dict[str, Any]) -> dict[str, Any]:
    sandbox_dir = resolve_path(args.get("sandbox_dir"))
    patterns = ["*.ppm", "*.bmp", "*.png", "*.log", "*.json"]
    files: list[str] = []
    for pattern in patterns:
        files.extend(str(path) for path in sandbox_dir.rglob(pattern) if path.is_file())
    return {"ok": True, "sandbox_dir": str(sandbox_dir), "artifacts": sorted(set(files))}

def _first_artifact(artifacts: list[str], suffixes: tuple[str, ...], *, prefer: str = "") -> Path | None:
    paths = [Path(item) for item in artifacts if str(item).lower().endswith(suffixes)]
    if prefer:
        for path in paths:
            if path.name.lower() == prefer.lower():
                return path
    return paths[0] if paths else None

def _copy_image_for_probe(source: Path, output_dir: Path) -> Path:
    import shutil

    target = output_dir / f"screen{source.suffix.lower() or '.ppm'}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target

def _default_object_tree(width: int, height: int, screenshot_path: Path, *, source: str, available: bool = False) -> dict[str, Any]:
    return {
        "schema": "freertos-embedded-architect.lvgl.object-tree.v1",
        "source": source,
        "screenshot": str(screenshot_path),
        "display": {"width": width, "height": height},
        "introspection": {
            "available": available,
            "note": "C-side object_tree.json was not produced; this fallback only preserves screen bounds.",
        },
        "tree": {"type": "screen", "x": 0, "y": 0, "w": width, "h": height, "children": []},
    }

def _write_snippet_source(args: dict[str, Any], snippet_dir: Path) -> tuple[Path, str, str] | None:
    c_code = args.get("c_code")
    if not c_code:
        return None
    entry = safe_symbol(str(args.get("ui_entry_function") or "ui_snippet_create"))
    header = str(args.get("ui_header") or "ui_snippet.h")
    snippet_dir.mkdir(parents=True, exist_ok=True)
    header_text = str(args.get("c_header") or textwrap.dedent(
        f"""\
        #ifndef UI_SNIPPET_H
        #define UI_SNIPPET_H

        #include "lvgl.h"

        lv_obj_t *{entry}(lv_obj_t *parent);

        #endif /* UI_SNIPPET_H */
        """
    ))
    (snippet_dir / header).write_text(header_text, encoding="utf-8", newline="\n")
    source = str(c_code)
    if "lvgl.h" not in source:
        source = f'#include "lvgl.h"\n#include "{header}"\n\n' + source
    (snippet_dir / "ui_snippet.c").write_text(source, encoding="utf-8", newline="\n")
    return snippet_dir, entry, header

def _load_or_create_object_tree(artifacts: list[str], screenshot_path: Path, output_dir: Path, *, source: str) -> Path:
    existing = _first_artifact(artifacts, (".json",), prefer="object_tree.json")
    target = output_dir / "object_tree.json"
    if existing is not None and existing.is_file():
        if existing.resolve() != target.resolve():
            target.write_bytes(existing.read_bytes())
        return target
    width, height, _ = read_image(screenshot_path)
    _write_json(target, _default_object_tree(width, height, screenshot_path, source=source))
    return target

def _summarize_tree(tree: dict[str, Any]) -> dict[str, Any]:
    from collections import Counter

    nodes: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        nodes.append(node)
        for child in node.get("children", []) or []:
            walk(child)

    walk(tree.get("tree"))
    types = Counter(str(node.get("type", "unknown")) for node in nodes)
    texts = sorted(str(node.get("text")) for node in nodes if node.get("text") not in (None, ""))
    return {"node_count": len(nodes), "types": dict(sorted(types.items())), "texts": texts}

def compare_lvgl_object_tree(args: dict[str, Any]) -> dict[str, Any]:
    actual = resolve_path(args.get("actual_path"))
    baseline = resolve_path(args.get("baseline_path"))
    if not actual.is_file():
        raise ValueError(f"actual_path does not exist: {actual}")
    if not baseline.is_file():
        raise ValueError(f"baseline_path does not exist: {baseline}")
    actual_tree = json.loads(actual.read_text(encoding="utf-8"))
    baseline_tree = json.loads(baseline.read_text(encoding="utf-8"))
    actual_summary = _summarize_tree(actual_tree)
    baseline_summary = _summarize_tree(baseline_tree)
    diffs: list[str] = []
    if actual_summary["node_count"] != baseline_summary["node_count"]:
        diffs.append("node_count")
    if actual_summary["types"] != baseline_summary["types"]:
        diffs.append("types")
    if actual_summary["texts"] != baseline_summary["texts"]:
        diffs.append("texts")
    return {
        "ok": not diffs,
        "status": "passed" if not diffs else "structure_diff_failed",
        "diffs": diffs,
        "actual": actual_summary,
        "baseline": baseline_summary,
        "artifacts": [str(actual), str(baseline)],
    }

def lvgl_render_cache_dir(args: dict[str, Any]) -> Path:
    return resolve_path(args.get("cache_dir", ROOT / REGRESSION_SANDBOX_CONFIG["default_cache_dir"]))

def lvgl_render(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_render"))
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = str(args.get("render_mode", "auto"))
    require_choice("render_mode", mode, {"auto", "probe", "preview"})
    cache_dir = lvgl_render_cache_dir(args)
    cache_dir.mkdir(parents=True, exist_ok=True)

    diagnostics_path = output_dir / "diagnostics.json"
    png_path = output_dir / "render.png"
    object_tree_path = output_dir / "object_tree.json"

    if mode == "probe":
        probe_source = resolve_path(args.get("probe_image_path", sandbox_template_dir() / "baselines" / "probe.ppm"))
        screenshot_path = _copy_image_for_probe(probe_source, output_dir)
        png_meta = convert_image_to_png(screenshot_path, png_path)
        width, height, _ = read_image(screenshot_path)
        _write_json(object_tree_path, _default_object_tree(width, height, screenshot_path, source="probe", available=False))
        diagnostics = {"ok": True, "available": True, "status": "probe", "log_issues": [], "mode": mode}
        _write_json(diagnostics_path, diagnostics)
        return {
            "ok": True,
            "available": True,
            "status": "probe",
            "screenshot_path": str(screenshot_path),
            "png_path": str(png_path),
            "png": png_meta,
            "object_tree_path": str(object_tree_path),
            "diagnostics_path": str(diagnostics_path),
            "artifacts": [str(screenshot_path), str(png_path), str(object_tree_path), str(diagnostics_path)],
        }

    # Preview mode: pure Python rendering, zero native dependencies.
    if mode == "preview":
        from lvgl_preview import render_tree_to_png, spec_to_tree, write_object_tree

        spec_json = args.get("spec_json")
        spec_path = args.get("spec_path")
        tree_json = args.get("object_tree_json")
        tree_path = args.get("object_tree_path")
        width = int(args.get("width", DISPLAY_CONFIG["display"]["width"]))
        height = int(args.get("height", DISPLAY_CONFIG["display"]["height"]))
        base_dir = resolve_path(args.get("base_dir", ROOT))

        if tree_json:
            tree = tree_json
            source = "object_tree"
        elif tree_path:
            source_path = resolve_path(tree_path)
            tree = json.loads(source_path.read_text(encoding="utf-8"))
            base_dir = source_path.parent
            source = "object_tree_path"
        elif spec_json:
            tree = spec_to_tree(spec_json, display_width=width, display_height=height)
            source = "layout_spec"
        elif spec_path:
            source_path = resolve_path(spec_path)
            spec = json.loads(source_path.read_text(encoding="utf-8"))
            tree = spec_to_tree(spec, display_width=width, display_height=height)
            base_dir = source_path.parent
            source = "layout_spec_path"
        else:
            page_name = str(args.get("page_name", "page"))
            design_notes = str(args.get("design_notes", ""))
            default_spec = generate_lvgl_layout_spec({
                "page_name": page_name,
                "design_notes": design_notes,
            })
            tree = spec_to_tree(default_spec, display_width=width, display_height=height)
            source = "generated_spec"

        png_path = render_tree_to_png(tree, output_dir, "render.png", base_dir=base_dir, display_width=width, display_height=height)
        object_tree_path = write_object_tree(tree, output_dir, "object_tree.json")
        diagnostics = {
            "ok": True,
            "available": True,
            "status": "preview",
            "source": source,
            "mode": mode,
            "screenshot_path": str(png_path),
            "png_path": str(png_path),
            "object_tree_path": str(object_tree_path),
            "log_issues": [],
        }
        _write_json(diagnostics_path, diagnostics)
        return {
            "ok": True,
            "available": True,
            "status": "preview",
            "source": source,
            "screenshot_path": str(png_path),
            "png_path": str(png_path),
            "object_tree_path": str(object_tree_path),
            "diagnostics_path": str(diagnostics_path),
            "artifacts": [str(png_path), str(object_tree_path), str(diagnostics_path)],
        }

    snippet_dir_arg = resolve_path(args.get("snippet_dir", cache_dir / "snippet"))
    snippet = _write_snippet_source(args, snippet_dir_arg)
    render_args = dict(args)
    sandbox_dir = resolve_path(args.get("sandbox_dir", cache_dir / "sandbox"))
    build_dir = resolve_path(args.get("build_dir", cache_dir / "build"))
    render_args["output_dir"] = str(sandbox_dir)
    if snippet is not None:
        snippet_dir, entry, header = snippet
        render_args["ui_under_test_dir"] = str(snippet_dir)
        render_args["ui_entry_function"] = entry
        render_args["ui_header"] = header

    prepared = prepare_lvgl_regression_sandbox(render_args)
    sandbox_path = Path(prepared["sandbox_dir"])
    built = build_lvgl_regression_sandbox({**args, "sandbox_dir": str(sandbox_path), "build_dir": str(build_dir)})
    diagnostics: dict[str, Any] = {
        "mode": mode,
        "cache_dir": str(cache_dir),
        "sandbox_dir": str(sandbox_path),
        "build_dir": str(build_dir),
        "prepare": prepared,
        "build": built,
        "log_issues": [],
    }
    if not built.get("ok"):
        diagnostics.update({"ok": False, "available": built.get("available", True), "status": built.get("status", "build_failed")})
        _write_json(diagnostics_path, diagnostics)
        return {
            "ok": False,
            "available": built.get("available", True),
            "status": built.get("status", "build_failed"),
            "stage": "build",
            "diagnostics_path": str(diagnostics_path),
            "cache_dir": str(cache_dir),
            "sandbox_dir": str(sandbox_path),
            "build_dir": str(build_dir),
            "prepare": prepared,
            "build": built,
            "artifacts": prepared.get("artifacts", []) + built.get("artifacts", []) + [str(diagnostics_path)],
        }
    if built.get("available") is False:
        diagnostics.update({"ok": True, "available": False, "status": "not_available"})
        _write_json(diagnostics_path, diagnostics)
        return {
            "ok": True,
            "available": False,
            "status": "not_available",
            "stage": "build",
            "diagnostics_path": str(diagnostics_path),
            "cache_dir": str(cache_dir),
            "sandbox_dir": str(sandbox_path),
            "build_dir": str(build_dir),
            "prepare": prepared,
            "build": built,
            "artifacts": prepared.get("artifacts", []) + [str(diagnostics_path)],
        }

    ran = run_lvgl_regression_sandbox({**args, "sandbox_dir": str(sandbox_path), "build_dir": str(build_dir), "output_dir": str(output_dir / "run")})
    artifacts = list(prepared.get("artifacts", [])) + list(built.get("artifacts", [])) + list(ran.get("artifacts", []))
    screenshot = _first_artifact(list(ran.get("artifacts", [])), (".ppm", ".bmp", ".png"), prefer="screen.ppm")
    diagnostics.update({"run": ran, "log_issues": ran.get("log_issues", [])})
    if screenshot is None or not screenshot.is_file():
        diagnostics.update({"ok": False, "available": True, "status": "screenshot_missing"})
        _write_json(diagnostics_path, diagnostics)
        return {
            "ok": False,
            "available": True,
            "status": "screenshot_missing",
            "stage": "run",
            "diagnostics_path": str(diagnostics_path),
            "cache_dir": str(cache_dir),
            "sandbox_dir": str(sandbox_path),
            "build_dir": str(build_dir),
            "prepare": prepared,
            "build": built,
            "run": ran,
            "artifacts": artifacts + [str(diagnostics_path)],
        }

    png_meta = convert_image_to_png(screenshot, png_path)
    object_tree_path = _load_or_create_object_tree(list(ran.get("artifacts", [])), screenshot, output_dir, source="sandbox")
    diagnostics.update({"ok": bool(ran.get("ok")), "available": True, "status": ran.get("status", "failed"), "screenshot_path": str(screenshot), "png_path": str(png_path), "object_tree_path": str(object_tree_path)})
    _write_json(diagnostics_path, diagnostics)
    return {
        "ok": bool(ran.get("ok")),
        "available": True,
        "status": "passed" if ran.get("ok") else "failed",
        "stage": "complete",
        "screenshot_path": str(screenshot),
        "png_path": str(png_path),
        "png": png_meta,
        "object_tree_path": str(object_tree_path),
        "diagnostics_path": str(diagnostics_path),
        "cache_dir": str(cache_dir),
        "sandbox_dir": str(sandbox_path),
        "build_dir": str(build_dir),
        "prepare": prepared,
        "build": built,
        "run": ran,
        "artifacts": sorted(set(artifacts + [str(screenshot), str(png_path), str(object_tree_path), str(diagnostics_path)])),
    }

def run_lvgl_ui_regression(args: dict[str, Any]) -> dict[str, Any]:
    rendered = lvgl_render(args)
    if rendered.get("available") is False:
        return {"ok": True, "available": False, "stage": "render", "render": rendered, "artifacts": rendered.get("artifacts", [])}
    if not rendered.get("ok"):
        return {"ok": False, "available": True, "stage": "render", "render": rendered, "artifacts": rendered.get("artifacts", [])}

    comparison: dict[str, Any] | None = None
    baseline = args.get("baseline_path")
    actual_screenshot = rendered.get("screenshot_path")
    if baseline and actual_screenshot:
        comparison = compare_lvgl_screenshot({**args, "actual_path": str(actual_screenshot), "baseline_path": str(baseline)})

    structure: dict[str, Any] | None = None
    baseline_tree = args.get("baseline_object_tree_path")
    actual_tree = rendered.get("object_tree_path")
    if baseline_tree and actual_tree:
        structure = compare_lvgl_object_tree({"actual_path": str(actual_tree), "baseline_path": str(baseline_tree)})

    log_issues = []
    diagnostics_path = rendered.get("diagnostics_path")
    if diagnostics_path and Path(str(diagnostics_path)).is_file():
        diagnostics = json.loads(Path(str(diagnostics_path)).read_text(encoding="utf-8"))
        log_issues = diagnostics.get("log_issues", []) or []

    ok = bool(rendered.get("ok")) and (comparison is None or bool(comparison.get("ok"))) and (structure is None or bool(structure.get("ok"))) and not log_issues
    return {
        "ok": ok,
        "available": True,
        "stage": "complete",
        "render": rendered,
        "comparison": comparison,
        "structure": structure,
        "log_issues": log_issues,
        "artifacts": rendered.get("artifacts", []),
    }

__all__ = [
    "build_lvgl_regression_sandbox",
    "compare_lvgl_object_tree",
    "compare_lvgl_screenshot",
    "list_lvgl_regression_artifacts",
    "lvgl_render",
    "prepare_lvgl_regression_sandbox",
    "prepare_lvgl_sim_project",
    "run_lvgl_regression_sandbox",
    "run_lvgl_ui_regression",
]
