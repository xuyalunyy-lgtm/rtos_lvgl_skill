"""LVGL compile gate — static validation of generated C/H code.

Checks syntax, symbol declarations, API version consistency, and injection safety.
Does NOT require actual LVGL headers — pure static analysis.

Usage:
    python mcp/lvgl_compile_gate.py --c path/to/page.c --h path/to/page.h --lvgl-version v9 --json
    python mcp/lvgl_compile_gate.py --dir artifacts/lvgl_ui --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ── v8/v9 API signatures ──────────────────────────────────────────

V8_ONLY_APIS = {
    "lv_img_create", "lv_img_set_src", "lv_img_set_auto_size",
    "lv_img_set_offset_x", "lv_img_set_offset_y", "lv_img_set_angle",
    "lv_img_set_zoom", "lv_img_set_pivot", "lv_img_set_antialias",
    "lv_img_dsc_t", "LV_IMG_CF_TRUE_COLOR", "LV_IMG_CF_TRUE_COLOR_ALPHA",
    "LV_IMG_CF_ALPHA_8BIT", "LV_IMG_CF_INDEXED_1BIT",
}

V9_ONLY_APIS = {
    "lv_image_create", "lv_image_set_src", "lv_image_set_rotation",
    "lv_image_set_scale", "lv_image_set_pivot", "lv_image_set_antialias",
    "lv_image_dsc_t", "LV_IMAGE_HEADER_MAGIC",
    "LV_COLOR_FORMAT_RGB565", "LV_COLOR_FORMAT_RGB565A8",
    "LV_COLOR_FORMAT_RGB888", "LV_COLOR_FORMAT_ARGB8888",
    "LV_COLOR_FORMAT_A8",
}


def _extract_identifiers(code: str) -> set[str]:
    """Extract all identifiers from C code."""
    # Remove comments
    code = re.sub(r'//.*?$', '', code, flags=re.MULTILINE)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    # Remove strings
    code = re.sub(r'"[^"]*"', '""', code)
    # Extract identifiers
    return set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', code))


def _extract_macros(code: str) -> set[str]:
    """Extract #define macro names."""
    return set(re.findall(r'#define\s+([A-Z_][A-Z0-9_]*)', code))


def _extract_function_decls(code: str) -> set[str]:
    """Extract function declarations from header."""
    return set(re.findall(r'^\s*(?:void|lv_obj_t\s*\*|int|bool|static)\s+(\w+)\s*\(', code, re.MULTILINE))


def _preprocess_for_balance(code: str, lvgl_version: str) -> str:
    """Keep active LVGL preprocessor branches for structural validation.

    LVGL's font converter emits version-gated initializers where both source
    branches are individually incomplete.  Counting every branch reports a
    valid font C file as malformed, so this small evaluator selects the target
    LVGL branch and treats unknown feature macros as disabled.
    """
    macros: dict[str, int] = {
        "LVGL_VERSION_MAJOR": 9 if lvgl_version == "v9" else 8,
        "LVGL_VERSION_MINOR": 0,
    }

    def evaluate(expression: str) -> bool:
        expression = re.sub(r"LV_VERSION_CHECK\s*\([^)]*\)", "0", expression)
        expression = re.sub(r"defined\s*\((\w+)\)", lambda match: "1" if match.group(1) in macros else "0", expression)
        expression = expression.replace("&&", " and ").replace("||", " or ")
        expression = re.sub(r"!(?!=)", " not ", expression)
        expression = re.sub(r"\b[A-Za-z_]\w*\b", lambda match: str(macros.get(match.group(0), 0)), expression)
        if not re.fullmatch(r"(?:\d+|and|or|not|[()<>!=+\-*/%\s])+", expression):
            return False
        try:
            return bool(eval(expression, {"__builtins__": {}}, {}))
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError):
            return False

    active = True
    stack: list[dict[str, bool]] = []
    kept: list[str] = []
    for line in code.splitlines(keepends=True):
        directive = re.match(r"\s*#\s*(\w+)(?:\s+(.*?))?\s*$", line)
        if not directive:
            if active:
                kept.append(line)
            continue

        command, argument = directive.group(1), (directive.group(2) or "").strip()
        if command == "define" and active:
            match = re.match(r"(\w+)(?:\s+([0-9]+))?", argument)
            if match:
                macros[match.group(1)] = int(match.group(2) or "1")
        elif command in {"if", "ifdef", "ifndef"}:
            condition = (
                evaluate(argument) if command == "if"
                else (argument in macros if command == "ifdef" else argument not in macros)
            )
            stack.append({"parent": active, "taken": bool(condition)})
            active = active and bool(condition)
        elif command == "elif" and stack:
            frame = stack[-1]
            condition = evaluate(argument)
            active = frame["parent"] and not frame["taken"] and condition
            frame["taken"] = frame["taken"] or condition
        elif command == "else" and stack:
            frame = stack[-1]
            active = frame["parent"] and not frame["taken"]
            frame["taken"] = True
        elif command == "endif" and stack:
            active = stack.pop()["parent"]
    return "".join(kept)


def _check_brace_balance(code: str, lvgl_version: str = "v9") -> dict[str, Any]:
    """Check brace/parenthesis/bracket balance."""
    # Resolve version branches first, then remove strings and comments.
    code = _preprocess_for_balance(code, lvgl_version)
    code = re.sub(r'//.*?$', '', code, flags=re.MULTILINE)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    code = re.sub(r'"[^"]*"', '""', code)

    braces = 0
    parens = 0
    brackets = 0
    for i, ch in enumerate(code):
        if ch == '{': braces += 1
        elif ch == '}': braces -= 1
        elif ch == '(': parens += 1
        elif ch == ')': parens -= 1
        elif ch == '[': brackets += 1
        elif ch == ']': brackets -= 1

    return {
        "balanced": braces == 0 and parens == 0 and brackets == 0,
        "braces": braces,
        "parens": parens,
        "brackets": brackets,
    }


def _check_missing_semicolons(code: str) -> list[str]:
    """Check for obvious missing semicolons."""
    issues = []
    lines = code.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('#'):
            continue
        # Lines that should end with semicolon
        if any(stripped.startswith(kw) for kw in ['lv_', 'return ']):
            if not stripped.endswith(';') and not stripped.endswith('{') and not stripped.endswith('}') and not stripped.endswith('('):
                issues.append(f"Line {i+1}: possibly missing semicolon: {stripped[:60]}")
    return issues


def _check_api_version(code: str, version: str) -> list[str]:
    """Check for v8/v9 API mixing."""
    issues = []
    used_apis = _extract_identifiers(code)

    if version == "v8":
        wrong_apis = used_apis & V9_ONLY_APIS
        if wrong_apis:
            issues.append(f"v9 API used in v8 code: {sorted(wrong_apis)}")
    elif version == "v9":
        wrong_apis = used_apis & V8_ONLY_APIS
        if wrong_apis:
            issues.append(f"v8 API used in v9 code: {sorted(wrong_apis)}")

    return issues


def _check_injection(code: str) -> list[str]:
    """Check for potential C injection patterns."""
    issues = []
    # Check for suspicious patterns
    patterns = [
        (r'system\s*\(', "system() call"),
        (r'exec\s*\(', "exec() call"),
        (r'popen\s*\(', "popen() call"),
        (r'#include\s*<', "system include (should use quotes)"),
        (r'__attribute__', "GCC attribute (non-portable)"),
        (r'asm\s*\(', "inline assembly"),
    ]
    for pattern, desc in patterns:
        if re.search(pattern, code):
            issues.append(f"Potential injection: {desc}")

    return issues


def _check_undeclared_symbols(c_code: str, h_code: str) -> list[str]:
    """Check for undeclared symbols."""
    issues = []
    # Extract used macros from C code
    used_macros = set(re.findall(r'\b([A-Z][A-Z0-9_]{2,})\b', c_code))
    # Extract declared macros from H code
    declared_macros = _extract_macros(h_code)
    # Also include standard LVGL macros
    standard_macros = {"LV_ANIM_OFF", "LV_ANIM_ON", "LV_FLEX_FLOW_ROW", "LV_FLEX_FLOW_COLUMN",
                       "LV_FLEX_ALIGN_START", "LV_FLEX_ALIGN_CENTER", "LV_FLEX_ALIGN_END",
                       "LV_FLEX_ALIGN_SPACE_BETWEEN", "LV_FLEX_ALIGN_SPACE_AROUND",
                       "LV_TEXT_ALIGN_LEFT", "LV_TEXT_ALIGN_CENTER", "LV_TEXT_ALIGN_RIGHT",
                       "LV_ATTRIBUTE_MEM_ALIGN", "LV_ATTRIBUTE_LARGE_CONST",
                       "NULL", "true", "false"}
    declared_macros.update(standard_macros)

    # Filter out likely constants (short names, single letter)
    used_macros = {m for m in used_macros if len(m) > 2}
    undeclared = used_macros - declared_macros
    if undeclared:
        issues.append(f"Undeclared macros: {sorted(undeclared)[:10]}")

    return issues


def validate_compile(
    c_code: str,
    h_code: str,
    lvgl_version: str = "v9",
) -> dict[str, Any]:
    """Validate generated C/H code for compile readiness.

    Args:
        c_code: C source code.
        h_code: H header code.
        lvgl_version: Target LVGL version.

    Returns:
        Validation result dict.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Brace balance
    balance = _check_brace_balance(c_code, lvgl_version)
    if not balance["balanced"]:
        errors.append(f"Unbalanced braces: {balance}")

    # Missing semicolons
    semicolons = _check_missing_semicolons(c_code)
    if semicolons:
        warnings.extend(semicolons[:5])

    # API version check
    api_issues = _check_api_version(c_code, lvgl_version)
    if api_issues:
        errors.extend(api_issues)

    # Injection check
    injection_issues = _check_injection(c_code)
    if injection_issues:
        warnings.extend(injection_issues)

    # Undeclared symbols
    undeclared = _check_undeclared_symbols(c_code, h_code)
    if undeclared:
        warnings.extend(undeclared)

    # Basic header guard check
    if '#ifndef' not in h_code or '#define' not in h_code:
        warnings.append("Header missing include guard")

    # Check for empty code
    if len(c_code.strip()) < 100:
        errors.append("C code is too short (likely empty)")

    ok = len(errors) == 0

    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "brace_balance": balance["balanced"],
            "api_version": len(api_issues) == 0,
            "injection_safe": len(injection_issues) == 0,
        },
    }


def validate_directory(dir_path: str, lvgl_version: str = "v9") -> dict[str, Any]:
    """Validate all C/H files in a directory."""
    d = Path(dir_path)
    if not d.is_dir():
        return {"ok": False, "errors": [f"Directory not found: {dir_path}"]}

    c_files = list(d.glob("*.c"))
    h_files = list(d.glob("*.h"))

    if not c_files:
        return {"ok": False, "errors": ["No .c files found"]}

    all_errors = []
    all_warnings = []
    file_results = {}

    for c_file in c_files:
        # Find matching header
        h_file = d / f"{c_file.stem}.h"
        if not h_file.exists():
            h_file = next(iter(h_files), None)

        c_code = c_file.read_text(encoding="utf-8", errors="replace")
        h_code = h_file.read_text(encoding="utf-8", errors="replace") if h_file and h_file.exists() else ""

        result = validate_compile(c_code, h_code, lvgl_version)
        file_results[c_file.name] = result
        all_errors.extend(f"{c_file.name}: {e}" for e in result["errors"])
        all_warnings.extend(f"{c_file.name}: {w}" for w in result["warnings"])

    return {
        "ok": len(all_errors) == 0,
        "errors": all_errors,
        "warnings": all_warnings,
        "files": file_results,
    }


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c", help="Path to C source file")
    parser.add_argument("--h", help="Path to H header file")
    parser.add_argument("--dir", help="Directory containing C/H files")
    parser.add_argument("--lvgl-version", default="v9", choices=["v8", "v9"])
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.dir:
        result = validate_directory(args.dir, args.lvgl_version)
    elif args.c:
        c_path = Path(args.c)
        if not c_path.is_file():
            print(f"ERROR: C file not found: {args.c}")
            return 1
        c_code = c_path.read_text(encoding="utf-8")
        h_code = ""
        if args.h:
            h_path = Path(args.h)
            if h_path.is_file():
                h_code = h_path.read_text(encoding="utf-8")
        result = validate_compile(c_code, h_code, args.lvgl_version)
    else:
        print("ERROR: --c or --dir required")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Status: {'PASS' if result['ok'] else 'FAIL'}")
        for e in result["errors"]:
            print(f"  ERROR: {e}")
        for w in result["warnings"][:10]:
            print(f"  WARN: {w}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
