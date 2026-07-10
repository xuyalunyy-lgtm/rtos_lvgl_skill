#!/usr/bin/env python3
"""
cJSON static leak review tool.

Checks whether cJSON_Parse / cJSON_ParseWithLength and cJSON_Delete appear in pairs,
and flags potential leak paths.

Usage:
    python tools/cjson_leak_checker.py path/to/file.c
    python tools/cjson_leak_checker.py --dir path/to/dir
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

PARSE_PATTERNS = [re.compile(r"\b" + re.escape(api) + r"\s*\(") for api in lookup.get_apis("PARSE")]
DELETE_PATTERN = lookup.build_regex("DELETE")
CREATE_PATTERN = lookup.build_regex("CREATE")

PARSE_ASSIGN_PATTERN = re.compile(
    r"\b(?P<var>[A-Za-z_]\w*)\s*=\s*(?:\([^)]*\)\s*)?"
    r"cJSON_Parse(?:WithLength|WithOpts)?\s*\("
)
CONTROL_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof"}


@dataclass
class ParseSite:
    line_no: int
    line_text: str
    func_name: str = "global"
    var_name: str | None = None


@dataclass
class FunctionSpan:
    name: str
    start: int
    end: int


@dataclass
class CheckResult:
    file: str
    parse_sites: list[ParseSite] = field(default_factory=list)
    delete_count: int = 0
    create_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def strip_comments_preserve_lines(content: str) -> list[str]:
    """Remove C/C++ comments while preserving line numbers."""
    out: list[str] = []
    in_block = False
    for raw in content.splitlines():
        i = 0
        cleaned: list[str] = []
        while i < len(raw):
            if in_block:
                end = raw.find("*/", i)
                if end == -1:
                    i = len(raw)
                else:
                    in_block = False
                    i = end + 2
                continue
            if raw.startswith("//", i):
                break
            if raw.startswith("/*", i):
                in_block = True
                i += 2
                continue
            cleaned.append(raw[i])
            i += 1
        out.append("".join(cleaned))
    return out


def _match_function_header(text: str) -> str | None:
    if not text or text.endswith(";"):
        return None
    collapsed = " ".join(text.strip().split())
    m = re.search(r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*$", collapsed)
    if not m:
        return None
    name = m.group(1)
    if name in CONTROL_KEYWORDS:
        return None
    prefix = collapsed[: m.start(1)].strip()
    if not prefix:
        return None
    return name


def build_function_spans(lines: list[str]) -> tuple[list[FunctionSpan], list[str]]:
    spans: list[FunctionSpan] = []
    line_to_func = ["global"] * len(lines)
    current_name: str | None = None
    current_start = 0
    depth = 0
    pending_name: str | None = None
    pending_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if current_name is None:
            if pending_name is not None:
                if "{" in stripped:
                    current_name = pending_name
                    current_start = pending_start
                    depth = line.count("{") - line.count("}")
                    for j in range(current_start, i + 1):
                        line_to_func[j] = current_name
                    pending_name = None
                    if depth <= 0:
                        spans.append(FunctionSpan(current_name, current_start, i))
                        current_name = None
                    continue
                if stripped.endswith(";") or not stripped:
                    pending_name = None

            if "{" in stripped:
                header = stripped.split("{", 1)[0].strip()
                name = _match_function_header(header)
                if name:
                    current_name = name
                    current_start = i
                    depth = line.count("{") - line.count("}")
                    line_to_func[i] = current_name
                    if depth <= 0:
                        spans.append(FunctionSpan(current_name, current_start, i))
                        current_name = None
                    continue

            name = _match_function_header(stripped)
            if name:
                pending_name = name
                pending_start = i
            continue

        line_to_func[i] = current_name
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            spans.append(FunctionSpan(current_name, current_start, i))
            current_name = None

    return spans, line_to_func


def _line_deletes_var(line: str, var: str) -> bool:
    return re.search(rf"\bcJSON_Delete\s*\(\s*{re.escape(var)}\s*\)", line) is not None


def _is_null_guard_exit(body: list[tuple[int, str]], var: str, exit_idx: int) -> bool:
    start = max(0, exit_idx - 4)
    window = "\n".join(line for _, line in body[start : exit_idx + 1])
    null_guard = re.search(
        rf"\bif\s*\(\s*(?:{re.escape(var)}\s*==\s*NULL|"
        rf"NULL\s*==\s*{re.escape(var)}|!\s*{re.escape(var)})\s*\)",
        window,
    )
    if not null_guard:
        return False
    used_after_parse = re.search(
        rf"{re.escape(var)}\s*->|cJSON_GetObjectItem|cJSON_Is\w+\s*\(",
        window,
    )
    return used_after_parse is None


def _block_segment_before_exit(body: list[tuple[int, str]], exit_idx: int) -> str:
    start = 0
    for j in range(exit_idx, -1, -1):
        text = body[j][1].strip()
        if "{" in text or re.match(r"^[A-Za-z_]\w*\s*:\s*$", text):
            start = j
            break
    return "\n".join(line for _, line in body[start : exit_idx + 1])


def _label_deletes_var(body: list[tuple[int, str]], label: str, var: str) -> bool:
    for idx, (_, line) in enumerate(body):
        if not re.match(rf"^\s*{re.escape(label)}\s*:\s*(?:/\*.*\*/)?\s*$", line):
            continue
        for _, label_line in body[idx + 1 :]:
            if re.match(r"^\s*[A-Za-z_]\w*\s*:\s*$", label_line):
                return False
            if _line_deletes_var(label_line, var):
                return True
            if re.search(r"\breturn\b", label_line):
                return False
    return False


def _function_body_for(
    spans: list[FunctionSpan],
    clean_lines: list[str],
    func_name: str,
) -> list[tuple[int, str]]:
    for span in spans:
        if span.name == func_name:
            return [(i + 1, clean_lines[i]) for i in range(span.start, span.end + 1)]
    return [(i + 1, line) for i, line in enumerate(clean_lines)]


def analyze(content: str, filename: str = "<stdin>") -> CheckResult:
    result = CheckResult(file=filename)
    raw_lines = content.splitlines()
    lines = strip_comments_preserve_lines(content)
    spans, line_to_func = build_function_spans(lines)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        for pat in PARSE_PATTERNS:
            if pat.search(line):
                func = line_to_func[i]
                var_match = PARSE_ASSIGN_PATTERN.search(line)
                result.parse_sites.append(
                    ParseSite(
                        line_no=i + 1,
                        line_text=raw_lines[i].strip(),
                        func_name=func,
                        var_name=var_match.group("var") if var_match else None,
                    )
                )

        if DELETE_PATTERN.search(line):
            result.delete_count += 1

        if CREATE_PATTERN.search(line):
            result.create_count += 1

    if result.parse_sites:
        for site in result.parse_sites:
            func_body = _function_body_for(spans, lines, site.func_name)
            local_parse_idx = next(
                (idx for idx, (line_no, _) in enumerate(func_body) if line_no == site.line_no),
                None,
            )
            if local_parse_idx is None:
                continue

            var = site.var_name
            if var is None:
                result.errors.append(
                    f"Function '{site.func_name}()': L{site.line_no} Parse result not assigned — cannot free cJSON tree"
                )
                continue

            delete_lines = [
                line_no
                for line_no, text in func_body[local_parse_idx + 1 :]
                if _line_deletes_var(text, var)
            ]
            if not delete_lines:
                result.errors.append(
                    f"Function '{site.func_name}()': L{site.line_no} parsed into '{var}' but no cJSON_Delete({var}) found"
                )

            for idx in range(local_parse_idx + 1, len(func_body)):
                line_no, text = func_body[idx]
                stripped = text.strip()
                if not stripped:
                    continue

                goto_match = re.search(r"\bgoto\s+([A-Za-z_]\w*)\s*;", stripped)
                if goto_match:
                    if _is_null_guard_exit(func_body, var, idx):
                        continue
                    label = goto_match.group(1)
                    if _label_deletes_var(func_body, label, var):
                        continue
                    result.errors.append(
                        f"Function '{site.func_name}()': L{line_no} goto {label} before cJSON_Delete({var})"
                    )
                    continue

                if not re.search(r"\b(return|continue|break)\b", stripped):
                    continue
                if _is_null_guard_exit(func_body, var, idx):
                    continue
                segment = _block_segment_before_exit(func_body, idx)
                if _line_deletes_var(segment, var):
                    continue
                result.errors.append(
                    f"Function '{site.func_name}()': L{line_no} early exit before cJSON_Delete({var})"
                )

    # Create objects also need Delete
    if result.create_count > 0 and result.delete_count < result.create_count:
        result.warnings.append(
            f"cJSON_Create* called {result.create_count} times, Delete only {result.delete_count} times"
        )

    # Check common anti-patterns
    if any(site.var_name is None for site in result.parse_sites):
        result.warnings.append(
            "Parse result not assigned to variable — cannot track deallocation"
        )

    return result


def check_file(path: Path) -> list[dict]:
    """Check a single file, return issue dict list."""
    data = read_file(path)
    if data is None:
        return []
    _lines, text = data
    result = analyze(text, str(path))
    issues: list[dict] = []
    for e in result.errors:
        m = re.search(r"L(\d+)", e)
        line = int(m.group(1)) if m else 0
        issues.append(make_issue(path, line, "C3", "P0", e))
    for w in result.warnings:
        issues.append(make_issue(path, 0, "C3", "P1", w))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "cJSON static leak review", ("C3",),
                                 suffixes={".c", ".h", ".cpp"}))
