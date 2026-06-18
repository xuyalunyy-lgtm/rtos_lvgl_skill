#!/usr/bin/env python3
"""
C14.4 日志脱敏启发式检查器。

检查项:
  C14.4 — 日志禁止打印密码/token/密钥明文

用法:
    python tools/log_desensitize_checker.py <file.c> [file2.c ...]
    python tools/log_desensitize_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Log macros
LOG_MACROS = [
    "LOG_E",
    "LOG_W",
    "LOG_I",
    "LOG_D",
    "LOG_V",
    "ESP_LOGE",
    "ESP_LOGW",
    "ESP_LOGI",
    "ESP_LOGD",
    "ESP_LOGV",
    "printf",
    "fprintf",
    "snprintf",
]

# Sensitive keywords that should not be printed
SENSITIVE_KEYWORDS = [
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "privatekey",
    "credential",
    "auth_token",
    "access_token",
    "refresh_token",
    "session_key",
    "encryption_key",
]


def check_log_desensitize(path: Path, lines: list[str]) -> list[dict]:
    """C14.4 — 日志中禁止打印敏感信息明文"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Check if line contains log macro
        has_log_macro = False
        for macro in LOG_MACROS:
            if macro + "(" in stripped:
                has_log_macro = True
                break

        if not has_log_macro:
            continue

        # Check if line contains sensitive keyword
        line_lower = stripped.lower()
        for keyword in SENSITIVE_KEYWORDS:
            if keyword in line_lower:
                # Check if it's actually printing the value (not just the variable name)
                # Pattern: LOG_I(TAG, "password: %s", password)
                # But not: LOG_I(TAG, "Connecting to WiFi")  (no sensitive value)
                if re.search(rf'{keyword}\s*["\']|["\'].*{keyword}', line_lower):
                    # It's printing a label with sensitive keyword
                    # Check if there's a format specifier after
                    if re.search(r'%[sdxf]', stripped):
                        issues.append({
                            "id": "C14.4",
                            "file": f"{path}:{i}",
                            "issue": f"日志可能打印 {keyword} 明文（应脱敏）",
                            "severity": "P1",
                        })
                        break

    return issues


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []
    issues.extend(check_log_desensitize(path, lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C14.4 日志脱敏检查器")
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
        print("[log_desensitize_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[log_desensitize_checker] 已检查 {len(unique)} 个文件，未发现 C14.4 违规")
        return 0

    print(f"[log_desensitize_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C14.4 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C14.4 log-desensitize warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
