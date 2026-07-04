#!/usr/bin/env python3
"""
C29 module boundary heuristic checker.

Checks:
  C29.6 - god module / too many direct layer dependencies
  C29.7 - cross-layer include or direct UI calls from non-UI modules
  C29.8 - private header reach-in
  C29.9 - shared writable global context

Usage:
    python tools/module_boundary_checker.py <file.c> [file2.h ...]
    python tools/module_boundary_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker


LOCAL_INCLUDE_RE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)
EXTERN_CONTEXT_RE = re.compile(
    r"\bextern\s+[^;]*(?:g_|s_)[A-Za-z0-9_]*(?:ctx|context|state)\b[^;]*;",
    re.IGNORECASE,
)
GLOBAL_CONTEXT_RE = re.compile(
    r"^(?!\s*static\b)\s*[A-Za-z_][A-Za-z0-9_]*(?:_ctx_t|_context_t|_state_t)\s+g_[A-Za-z0-9_]+\s*;",
    re.MULTILINE,
)
LVGL_CALL_RE = re.compile(r"\blv_(?:obj|label|bar|img|btn|timer|disp)_\w*\s*\(")


LAYER_PREFIXES = {
    "ui": "ui",
    "view": "ui",
    "presenter": "presenter",
    "network": "service",
    "wss": "service",
    "wifi": "service",
    "cloud": "service",
    "storage": "service",
    "nvs": "service",
    "audio": "media",
    "video": "media",
    "camera": "media",
    "sensor": "driver",
    "driver": "driver",
    "gpio": "driver",
    "i2c": "driver",
    "spi": "driver",
    "lcd": "driver",
    "display": "driver",
}

HIGH_LAYER_PREFIXES = {"ui", "view", "presenter"}
LOW_LAYER_PREFIXES = {
    "network", "wss", "wifi", "cloud", "storage", "nvs", "audio", "video",
    "camera", "sensor", "driver", "gpio", "i2c", "spi", "lcd", "display",
}
PRIVATE_REACH_IN_HINTS = ("private", "internal")


def prefix_of(name: str) -> str:
    stem = Path(name).stem.lower()
    return stem.split("_", 1)[0]


def layer_of(name: str) -> str:
    return LAYER_PREFIXES.get(prefix_of(name), "unknown")


def is_low_layer(name: str) -> bool:
    return prefix_of(name) in LOW_LAYER_PREFIXES


def is_high_layer(name: str) -> bool:
    return prefix_of(name) in HIGH_LAYER_PREFIXES


def check_contract_fields(path: Path, text: str) -> list[dict]:
    if "module_boundary:" not in text:
        return []

    required = [
        "responsibility:",
        "public_api:",
        "dependencies:",
        "forbidden_dependencies:",
        "events_in:",
        "events_out:",
        "owned_resources:",
    ]
    issues = []
    for field in required:
        if field not in text:
            issues.append(make_issue(path, 1, "C29.6", "P1", f"module_boundary missing {field}"))
    return issues


def check_include_boundaries(path: Path, includes: list[str]) -> list[dict]:
    issues = []
    layers = {layer_of(inc) for inc in includes if layer_of(inc) != "unknown"}

    if len(layers) >= 4:
        issues.append(make_issue(
            path, 1, "C29.6", "P1",
            f"module directly includes too many layers: {', '.join(sorted(layers))}",
        ))

    source_low = is_low_layer(path.name)
    source_high = is_high_layer(path.name)
    for inc in includes:
        if source_low and is_high_layer(inc):
            issues.append(make_issue(path, 1, "C29.7", "P0", f"low-layer module includes high-layer header {inc}"))
        if source_high and is_low_layer(inc):
            issues.append(make_issue(path, 1, "C29.7", "P0", f"UI/presenter module includes low-layer header {inc}"))
        if any(hint in inc.lower() for hint in PRIVATE_REACH_IN_HINTS):
            issues.append(make_issue(path, 1, "C29.8", "P1", f"cross-module private/internal include {inc}"))

    return issues


def check_cross_layer_calls(path: Path, text: str) -> list[dict]:
    if is_high_layer(path.name):
        return []
    if LVGL_CALL_RE.search(text):
        return [make_issue(path, 1, "C29.7", "P0", "non-UI module directly calls LVGL API")]
    return []


def check_global_context(path: Path, text: str) -> list[dict]:
    issues = []
    for match in EXTERN_CONTEXT_RE.finditer(text):
        line = text[:match.start()].count("\n") + 1
        issues.append(make_issue(path, line, "C29.9", "P0", "shared extern writable module context"))
    for match in GLOBAL_CONTEXT_RE.finditer(text):
        line = text[:match.start()].count("\n") + 1
        issues.append(make_issue(path, line, "C29.9", "P0", "non-static global writable module context"))
    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    _lines, text = result
    includes = LOCAL_INCLUDE_RE.findall(text)

    issues = []
    issues.extend(check_contract_fields(path, text))
    issues.extend(check_include_boundaries(path, includes))
    issues.extend(check_cross_layer_calls(path, text))
    issues.extend(check_global_context(path, text))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C29 module boundary checker", ("C29",), {".c", ".h"}))
