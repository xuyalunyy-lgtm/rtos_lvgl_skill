"""App-level validators for multi-page LVGL MVP.

Validates route graph connectivity, generated C code structure,
thread boundary safety, and resource deduplication.  Pure analysis —
no I/O side effects.

Usage:
    from mcp.app_validator import validate_app
    result = validate_app(resolved_manifest, generated_files_dict)
"""
from __future__ import annotations

import re
from collections import deque
from typing import Any


# ── Public API ─────────────────────────────────────────────────────


def validate_app(
    manifest: dict[str, Any],
    generated_files: dict[str, str],
) -> dict[str, Any]:
    """Run all app-level validators.

    Args:
        manifest: Resolved Manifest v2 dict.
        generated_files: {relative_path: file_content} for all generated C/H files.

    Returns:
        {
            "ok": bool,
            "status": "verified" | "needs_manual_work" | "invalid",
            "errors": [...],
            "warnings": [...],
            "manual_required": [...],
            "details": {validator_name: result, ...}
        }
    """
    errors: list[str] = []
    warnings: list[str] = []
    manual_required: list[str] = []
    details: dict[str, Any] = {}

    pages = manifest.get("pages", [])
    routes = manifest.get("routes", [])
    shared = manifest.get("shared", {})
    entry_page = manifest.get("app", {}).get("entry_page", "")

    # 1. Route graph
    rg = validate_route_graph(pages, routes, entry_page)
    details["route_graph"] = rg
    errors.extend(rg.get("errors", []))
    warnings.extend(rg.get("warnings", []))

    # 2. Generated code structure
    code_result = validate_generated_code(generated_files)
    details["code_structure"] = code_result
    errors.extend(code_result.get("errors", []))
    warnings.extend(code_result.get("warnings", []))
    manual_required.extend(code_result.get("manual_required", []))

    # 3. Thread boundary
    presenter_files = {k: v for k, v in generated_files.items() if "presenter" in k.lower()}
    tb = validate_thread_boundary(presenter_files)
    details["thread_boundary"] = tb
    errors.extend(tb.get("errors", []))
    warnings.extend(tb.get("warnings", []))

    # 4. Resource dedup
    rd = validate_resource_dedup(pages, shared)
    details["resource_dedup"] = rd
    errors.extend(rd.get("errors", []))
    warnings.extend(rd.get("warnings", []))

    # Determine status
    if errors:
        status = "invalid"
    elif manual_required:
        status = "needs_manual_work"
    else:
        status = "verified"

    return {
        "ok": len(errors) == 0,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "manual_required": manual_required,
        "details": details,
    }


# ── Route graph ────────────────────────────────────────────────────


def validate_route_graph(
    pages: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    entry_page: str,
) -> dict[str, Any]:
    """Check that all pages are reachable from entry via forward routes.

    Returns:
        {"ok": bool, "errors": [...], "warnings": [...], "reachable": set, "orphan_pages": set}
    """
    errors: list[str] = []
    warnings: list[str] = []

    page_ids = {p.get("id") for p in pages if isinstance(p, dict)}
    if not entry_page:
        errors.append("No entry_page defined")
        return {"ok": False, "errors": errors, "warnings": warnings, "reachable": set(), "orphan_pages": page_ids}

    if entry_page not in page_ids:
        errors.append(f"Entry page {entry_page!r} not in pages")
        return {"ok": False, "errors": errors, "warnings": warnings, "reachable": set(), "orphan_pages": page_ids}

    # Build adjacency list (forward routes only — skip "back")
    adj: dict[str, set[str]] = {pid: set() for pid in page_ids}
    for route in routes:
        if not isinstance(route, dict):
            continue
        mode = route.get("mode", "push")
        if mode == "back":
            continue  # back is reverse navigation, not a forward edge
        src = route.get("from", "")
        dst = route.get("to", "")
        if src in page_ids and dst in page_ids:
            adj[src].add(dst)

    # BFS from entry
    reachable: set[str] = set()
    queue: deque[str] = deque([entry_page])
    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        for neighbor in adj.get(current, set()):
            if neighbor not in reachable:
                queue.append(neighbor)

    orphan_pages = page_ids - reachable
    for orphan in sorted(orphan_pages):
        errors.append(f"Page {orphan!r} is not reachable from entry page {entry_page!r}")

    # Warn on pages with no outgoing routes (leaf pages are OK, but flag them)
    for pid in sorted(page_ids):
        if pid not in orphan_pages and not adj.get(pid) and pid != entry_page:
            # Leaf page — acceptable but worth noting
            pass  # silent; leaf pages are normal

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "reachable": reachable,
        "orphan_pages": orphan_pages,
    }


# ── Generated code structure ───────────────────────────────────────


_INJECTION_PATTERNS = [
    (r'\bsystem\s*\(', "system() call"),
    (r'\bexec\s*\(', "exec() call"),
    (r'\bpopen\s*\(', "popen() call"),
    (r'#include\s*<', "system include (should use quotes)"),
    (r'__attribute__', "GCC attribute (non-portable)"),
    (r'\basm\s*\(', "inline assembly"),
]

_TODO_PATTERN = re.compile(r'\b(TODO|FIXME|HACK|XXX)\b', re.IGNORECASE)


def validate_generated_code(files: dict[str, str]) -> dict[str, Any]:
    """Check structural correctness of generated C/H code.

    Args:
        files: {path: content} mapping.

    Returns:
        {"ok": bool, "errors": [...], "warnings": [...], "manual_required": [...]}
    """
    errors: list[str] = []
    warnings: list[str] = []
    manual_required: list[str] = []

    for fpath, content in files.items():
        if not isinstance(content, str):
            continue

        # Brace balance
        balance = _check_balance(content)
        if not balance["balanced"]:
            errors.append(
                f"{fpath}: unbalanced delimiters — "
                f"braces={balance['braces']}, parens={balance['parens']}, brackets={balance['brackets']}"
            )

        # Injection patterns
        for pattern, desc in _INJECTION_PATTERNS:
            if re.search(pattern, content):
                warnings.append(f"{fpath}: potential injection: {desc}")

        # TODO/FIXME → manual_required
        for match in _TODO_PATTERN.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            manual_required.append(f"{fpath}:{line_num}: {match.group()}")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "manual_required": manual_required,
    }


def _check_balance(code: str) -> dict[str, Any]:
    """Check brace/paren/bracket balance, ignoring strings and comments."""
    # Remove single-line comments
    code = re.sub(r'//.*?$', '', code, flags=re.MULTILINE)
    # Remove multi-line comments
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    # Remove string literals
    code = re.sub(r'"[^"]*"', '""', code)

    braces = parens = brackets = 0
    for ch in code:
        if ch == '{':
            braces += 1
        elif ch == '}':
            braces -= 1
        elif ch == '(':
            parens += 1
        elif ch == ')':
            parens -= 1
        elif ch == '[':
            brackets += 1
        elif ch == ']':
            brackets -= 1

    return {
        "balanced": braces == 0 and parens == 0 and brackets == 0,
        "braces": braces,
        "parens": parens,
        "brackets": brackets,
    }


# ── Thread boundary ────────────────────────────────────────────────


_UNSAFE_LVGL_PATTERNS = [
    (r'\blv_timer_create\b', "lv_timer_create — must be on UI thread"),
    (r'\blv_thread\b', "lv_thread — direct thread creation in presenter"),
    (r'\blv_async_call\b', "lv_async_call — presenter should not dispatch async; use ui_app_post_event"),
]


def validate_thread_boundary(presenter_files: dict[str, str]) -> dict[str, Any]:
    """Verify Presenter code doesn't create threads or timers directly.

    The generated Presenter pattern is safe by construction (callbacks are
    LVGL event handlers running on the UI thread).  This validator catches
    any unsafe additions.

    Returns:
        {"ok": bool, "errors": [...], "warnings": [...]}
    """
    errors: list[str] = []
    warnings: list[str] = []

    for fpath, content in presenter_files.items():
        if not isinstance(content, str):
            continue
        for pattern, desc in _UNSAFE_LVGL_PATTERNS:
            if re.search(pattern, content):
                errors.append(f"{fpath}: thread boundary violation: {desc}")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ── Resource deduplication ─────────────────────────────────────────


def validate_resource_dedup(
    pages: list[dict[str, Any]],
    shared: dict[str, Any],
) -> dict[str, Any]:
    """Check that shared assets/fonts aren't re-declared at page level.

    Returns:
        {"ok": bool, "errors": [...], "warnings": [...]}
    """
    errors: list[str] = []
    warnings: list[str] = []

    shared_assets = set(shared.get("assets", {}).keys()) if isinstance(shared, dict) else set()
    shared_fonts = set(shared.get("fonts", {}).keys()) if isinstance(shared, dict) else set()

    for page in pages:
        if not isinstance(page, dict):
            continue
        pid = page.get("id", "unknown")

        page_assets = set(page.get("assets", {}).keys()) if isinstance(page.get("assets"), dict) else set()
        page_fonts = set(page.get("fonts", {}).keys()) if isinstance(page.get("fonts"), dict) else set()

        # Page-level overrides are expected (that's how inheritance works),
        # but warn if the page re-declares the exact same key/value as shared
        for key in page_assets & shared_assets:
            page_val = (page.get("assets") or {}).get(key)
            shared_val = shared.get("assets", {}).get(key)
            if page_val == shared_val:
                warnings.append(
                    f"Page {pid!r}: asset {key!r} duplicates shared value "
                    f"(redundant — inherited automatically)"
                )

        for key in page_fonts & shared_fonts:
            page_val = (page.get("fonts") or {}).get(key)
            shared_val = shared.get("fonts", {}).get(key)
            if page_val == shared_val:
                warnings.append(
                    f"Page {pid!r}: font {key!r} duplicates shared value "
                    f"(redundant — inherited automatically)"
                )

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
