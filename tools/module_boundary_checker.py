#!/usr/bin/env python3
"""
C29 module boundary heuristic checker.

Checks:
  C29.6 - god module / too many direct layer dependencies
  C29.7 - cross-layer include or direct UI calls from non-UI modules
  C29.8 - private header reach-in
  C29.9 - shared writable global context
  C29.11 - public header declarations must match their C definitions

Usage:
    python tools/module_boundary_checker.py <file.c> [file2.h ...]
    python tools/module_boundary_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker, strip_comments


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
# Keep this deliberately line-oriented.  The earlier token-alternation form
# looked more expressive but could backtrack catastrophically across a typedef
# block when a function-like declaration did not match.
_RETURN_TYPE_RE = r"[A-Za-z_]\w*(?:\s+[A-Za-z_]\w*)*\s*\**"
FUNCTION_DECL_RE = re.compile(
    rf"^\s*(?:extern\s+)?(?P<return>{_RETURN_TYPE_RE})\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^;{}()]*)\)\s*;",
    re.MULTILINE,
)
FUNCTION_DEF_RE = re.compile(
    rf"^\s*(?:static\s+)?(?:inline\s+)?(?:extern\s+)?(?P<return>{_RETURN_TYPE_RE})\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^;{}()]*)\)\s*\{",
    re.MULTILINE,
)


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


def _normalise_type(value: str) -> str:
    """Normalise harmless whitespace and storage differences for C signatures."""
    value = re.sub(r"\b(?:extern|static|inline)\b", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s*\*\s*", "*", value)
    return value


def _split_parameters(value: str) -> list[str]:
    if not value.strip() or value.strip() == "void":
        return []
    result: list[str] = []
    current: list[str] = []
    depth = 0
    for char in value:
        if char == "," and depth == 0:
            result.append("".join(current).strip())
            current = []
            continue
        if char in "([":
            depth += 1
        elif char in ")]" and depth:
            depth -= 1
        current.append(char)
    if current:
        result.append("".join(current).strip())
    return result


def _normalise_parameter(value: str) -> str:
    value = value.strip()
    # Parameter arrays are adjusted to pointers by C.  Remove their identifier
    # before the common trailing-name rule below.
    value = re.sub(r"\s+[A-Za-z_]\w*\s*\[[^\]]*\]$", "*", value)
    # Keep a bare type (for example `int`) but drop a conventional trailing
    # parameter identifier (`const char *name` -> `const char*`).
    tokens = re.findall(r"[A-Za-z_]\w*", value)
    if len(tokens) >= 2:
        value = re.sub(r"\s+[A-Za-z_]\w*$", "", value)
    value = re.sub(r"\(\s*\*\s*[A-Za-z_]\w*\s*\)", "(*)", value)
    return _normalise_type(value)


def _signature_map(text: str, pattern: re.Pattern[str]) -> dict[str, tuple[str, tuple[str, ...], int]]:
    signatures: dict[str, tuple[str, tuple[str, ...], int]] = {}
    code = strip_comments(text)
    for match in pattern.finditer(code):
        name = match.group("name")
        if name in {"if", "for", "while", "switch"}:
            continue
        signatures[name] = (
            _normalise_type(match.group("return")),
            tuple(_normalise_parameter(param) for param in _split_parameters(match.group("params"))),
            code[:match.start("name")].count("\n") + 1,
        )
    return signatures


def _local_headers_for_source(path: Path, text: str) -> list[Path]:
    headers: set[Path] = set()
    sibling = path.with_suffix(".h")
    if sibling.is_file():
        headers.add(sibling.resolve())
    for include in LOCAL_INCLUDE_RE.findall(text):
        candidate = (path.parent / include).resolve()
        if candidate.is_file() and candidate.suffix.lower() == ".h":
            headers.add(candidate)
    return sorted(headers)


def check_interface_contracts(paths: list[Path]) -> list[dict]:
    """Compare local public-header declarations with included C definitions.

    Only sibling or explicitly quoted local headers are inspected.  External SDK
    headers are deliberately excluded, and declarations without a matching
    definition are not reported because implementations may live in a library.
    """
    issues: list[dict] = []
    for source in (path for path in paths if path.suffix.lower() in {".c", ".cpp"}):
        source_result = read_file(source)
        if source_result is None:
            continue
        _lines, source_text = source_result
        definitions = _signature_map(source_text, FUNCTION_DEF_RE)
        if not definitions:
            continue
        for header in _local_headers_for_source(source, source_text):
            header_result = read_file(header)
            if header_result is None:
                continue
            _header_lines, header_text = header_result
            declarations = _signature_map(header_text, FUNCTION_DECL_RE)
            for name, (decl_return, decl_params, decl_line) in declarations.items():
                definition = definitions.get(name)
                if definition is None:
                    continue
                def_return, def_params, _def_line = definition
                if (decl_return, decl_params) != (def_return, def_params):
                    issues.append(make_issue(
                        header, decl_line, "C29.11", "P0",
                        f"public declaration of {name} differs from definition in {source.name} "
                        f"(header: {decl_return}({', '.join(decl_params) or 'void'}); "
                        f"source: {def_return}({', '.join(def_params) or 'void'}))",
                    ))
    return issues


def check_paths(paths: list[Path]) -> list[dict]:
    issues: list[dict] = []
    for path in paths:
        issues.extend(check_file(path))
    issues.extend(check_interface_contracts(paths))
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
    raise SystemExit(run_checker(
        check_file, "C29 module boundary checker", ("C29",), {".c", ".h"},
        check_paths_fn=check_paths,
    ))
