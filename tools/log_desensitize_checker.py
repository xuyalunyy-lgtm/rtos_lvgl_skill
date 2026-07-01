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

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

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
                        issues.append(make_issue(
                            path, i, "C14.4", "P1",
                            f"日志可能打印 {keyword} 明文（应脱敏）",
                        ))
                        break

    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    lines, _text = result
    return check_log_desensitize(path, lines)


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C14.4 日志脱敏检查器", ("C14.4",)))
