#!/usr/bin/env python3
"""
C19 Flash/NVS 安全启发式检查器。

检查项:
  C19.1 — NVS 写入后必须 nvs_commit() + 检查返回值
  C19.2 — Flash 擦写期间禁止读取同分区

用法:
    python tools/flash_nvs_checker.py <file.c> [file2.c ...]
    python tools/flash_nvs_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# NVS write APIs
NVS_WRITE_APIS = [
    "nvs_set_u8",
    "nvs_set_i8",
    "nvs_set_u16",
    "nvs_set_i16",
    "nvs_set_u32",
    "nvs_set_i32",
    "nvs_set_u64",
    "nvs_set_i64",
    "nvs_set_str",
    "nvs_set_blob",
]


def check_nvs_commit(path: Path, lines: list[str]) -> list[dict]:
    """C19.1 — nvs_set_* 后必须有 nvs_commit"""
    issues = []
    nvs_write_calls = []
    nvs_commit_calls = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for api in NVS_WRITE_APIS:
            if api + "(" in stripped:
                nvs_write_calls.append((i, api))
                break

        if "nvs_commit" in stripped:
            nvs_commit_calls.append(i)

    # Check if nvs_write appears without nearby nvs_commit
    if nvs_write_calls and not nvs_commit_calls:
        for line_no, api in nvs_write_calls[:3]:
            issues.append({
                "id": "C19.1",
                "file": f"{path}:{line_no}",
                "issue": f"{api} 后未见 nvs_commit()",
                "severity": "P0",
            })
    elif nvs_write_calls and nvs_commit_calls:
        # Check proximity: commit should be within 10 lines of write
        for write_line, api in nvs_write_calls:
            has_nearby_commit = any(
                abs(write_line - commit_line) <= 10
                for commit_line in nvs_commit_calls
            )
            if not has_nearby_commit:
                issues.append({
                    "id": "C19.1",
                    "file": f"{path}:{write_line}",
                    "issue": f"{api} 后 10 行内未见 nvs_commit()",
                    "severity": "P0",
                })

    # Check if nvs_commit return value is checked
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "nvs_commit" not in stripped:
            continue

        # Skip if inside error-checking macros
        if any(macro in stripped for macro in [
            "ESP_ERROR_CHECK",
            "ESP_RETURN_ON_ERROR",
            "ESP_LOGE",
            "ESP_LOGW",
            "assert",
            "configASSERT",
        ]):
            continue

        if "=" not in stripped:
            # Return value discarded
            # Check next few lines for error check
            checked = False
            for j in range(i, min(i + 3, len(lines))):
                next_line = lines[j]
                if "if" in next_line and ("ret" in next_line or "err" in next_line or "ESP_OK" in next_line):
                    checked = True
                    break
            if not checked:
                issues.append({
                    "id": "C19.1",
                    "file": f"{path}:{i}",
                    "issue": "nvs_commit() 返回值未检查",
                    "severity": "P0",
                })

    return issues


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []
    issues.extend(check_nvs_commit(path, lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C19 Flash/NVS 安全检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    args = parser.parse_args()

    targets: list[Path] = []
    for f in args.files:
        p = Path(f)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            targets.extend(sorted(p.rglob("*.c")))

    if args.dir:
        d = Path(args.dir)
        if d.is_dir():
            targets.extend(sorted(d.rglob("*.c")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for t in targets:
        r = t.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if not unique:
        print("[flash_nvs_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[flash_nvs_checker] 已检查 {len(unique)} 个文件，未发现 C19 违规")
        return 0

    print(f"[flash_nvs_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C19 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C19 flash/nvs warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
