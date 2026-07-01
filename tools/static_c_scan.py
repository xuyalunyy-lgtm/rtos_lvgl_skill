#!/usr/bin/env python3
"""Shared helpers for lightweight C/C++ heuristic checkers."""

from __future__ import annotations

import re
from pathlib import Path


COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
FUNC_DEF_RE = re.compile(
    r"(?:^|[\n;])\s*"
    r"(?:static\s+)?(?:inline\s+)?"
    r"(?:[A-Za-z_][\w\s\*]*\s+)+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.MULTILINE,
)


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def line_at(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def nearby(text: str, pos: int, before: int = 240, after: int = 160) -> str:
    return text[max(0, pos - before):min(len(text), pos + after)]


def find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def extract_functions(code: str) -> list[dict[str, object]]:
    functions: list[dict[str, object]] = []
    for match in FUNC_DEF_RE.finditer(code):
        name = match.group("name")
        if name in {"if", "for", "while", "switch", "return", "sizeof"}:
            continue
        open_pos = code.find("{", match.end() - 1)
        close_pos = find_matching_brace(code, open_pos)
        if open_pos < 0 or close_pos < 0:
            continue
        functions.append({
            "name": name,
            "body": code[open_pos + 1:close_pos],
            "line": line_at(code, match.start("name")),
        })
    return functions


def collect_c_like_files(files: list[str], dir_path: str | None) -> list[Path]:
    targets: list[Path] = []
    for item in files:
        path = Path(item)
        if path.is_file() and path.suffix.lower() in {".c", ".h", ".cpp", ".cc", ".cxx"}:
            targets.append(path)
        elif path.is_dir():
            targets.extend(sorted_c_like(path))
    if dir_path:
        root = Path(dir_path)
        if root.is_dir():
            targets.extend(sorted_c_like(root))

    seen: set[Path] = set()
    unique: list[Path] = []
    for target in targets:
        resolved = target.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def sorted_c_like(root: Path) -> list[Path]:
    paths: list[Path] = []
    for suffix in ("*.c", "*.h", "*.cpp", "*.cc", "*.cxx"):
        paths.extend(root.rglob(suffix))
    return sorted(paths)


def make_issue(path: Path, line: int, cid: str, severity: str, msg: str) -> dict[str, str]:
    return {"id": cid, "severity": severity, "file": f"{path}:{line}", "issue": msg}
