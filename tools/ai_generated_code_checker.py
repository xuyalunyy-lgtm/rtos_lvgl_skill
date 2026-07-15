#!/usr/bin/env python3
"""C48 review for files explicitly marked as AI-generated."""
from __future__ import annotations
import re
from pathlib import Path
from checker_io import make_issue, read_file, run_checker, strip_comments

AI_MARKER = re.compile(r"generated\s+by\s+(?:chatgpt|llm|copilot|ai)|ai[- ]generated", re.I)
HALLUCINATED_API = re.compile(r"\b(?:esp_wifi_connect_async|xQueueCreateStaticEx|vTaskDelayMs)\s*\(")
EMPTY_ERROR = re.compile(r"if\s*\([^)]*(?:err|ret|result)[^)]*!=[^)]*\)\s*\{?\s*return\s*;?\s*\}?", re.I)

def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None: return []
    _lines, text = result
    if not AI_MARKER.search(text): return []
    code = strip_comments(text)
    issues = []
    for match in HALLUCINATED_API.finditer(code):
        issues.append(make_issue(path, code[:match.start()].count("\n") + 1, "C48.1", "P0", "AI-generated file calls a known non-portable/hallucinated API; verify against SDK map"))
    for match in EMPTY_ERROR.finditer(code):
        issues.append(make_issue(path, code[:match.start()].count("\n") + 1, "C48.2", "P1", "AI-generated error path returns without logging, cleanup, or error propagation"))
    if code.count("\n") > 40 and len(re.findall(r"^\s*//", text, re.M)) > 20:
        issues.append(make_issue(path, 1, "C48.3", "P2", "AI-generated file has excessive line-by-line comments; retain contract comments and remove narration"))
    return issues

if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C48 AI-generated code checker", ("C48",)))
