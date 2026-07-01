#!/usr/bin/env python3
"""
仓库密钥/凭证静态扫描（启发式）。

检查：
  - Kconfig/config 中非空 SECRET/PASSWORD/TOKEN/API_KEY/LICENSE/ACCESS_KEY/LCS_KEY/LCS_IV
  - Git remote URL 内嵌用户名/密码
  - 疑似高熵硬编码密钥

用法:
    python tools/secret_scan_checker.py path/to/config
    python tools/secret_scan_checker.py --dir ./projects
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from checker_io import make_issue_str, read_file, run_checker

# Kconfig / sdkconfig 敏感键名
SENSITIVE_KEY = re.compile(
    r"^CONFIG_[A-Z0-9_]*(SECRET|PASSWORD|TOKEN|API_KEY|PRIVATE_KEY|ACCESS_KEY|LICENSE|LCS_KEY|LCS_IV)[A-Z0-9_]*\s*=",
    re.MULTILINE,
)

# 非空字符串值（排除 "" 与 is not set）
NONEMPTY_VALUE = re.compile(r'=\s*"([^"]{8,})"')

# Git remote 内嵌凭证 https://user:pass@host
GIT_CRED_URL = re.compile(
    r"https?://[^/\s:@]+:[^/\s@]+@[^\s]+",
    re.IGNORECASE,
)

# 通用高熵字面量（config 行内）
HEX_OR_B64_BLOB = re.compile(
    r'=\s*"[A-Za-z0-9+/=_-]{24,}"',
)

SCAN_EXTENSIONS = {
    "",  # extensionless (Kconfig, config.secrets, etc.)
    ".config", ".cfg", ".env", ".ini",
    ".yaml", ".yml", ".json", ".toml",
    ".sh", ".py", ".c", ".h", ".md",
}


def scan_text(path: Path, text: str) -> list[dict]:
    """核心扫描逻辑，返回标准 issue dict 列表。"""
    issues: list[dict] = []
    rel = str(path)

    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if m := SENSITIVE_KEY.search(line):
            key = m.group(0).split("=", 1)[0].strip()
            if NONEMPTY_VALUE.search(line):
                issues.append(
                    make_issue_str(
                        f"{rel}:{i}",
                        "C9.1",
                        "P0",
                        f"敏感 Kconfig 键 {key} 含非空值，应移至 config.secrets（不入库）",
                    )
                )

        if GIT_CRED_URL.search(line):
            issues.append(
                make_issue_str(
                    f"{rel}:{i}",
                    "C9.2",
                    "P0",
                    "Git URL 内嵌凭证，改用 SSH 或 credential helper",
                )
            )

        if "CONFIG_" in line and HEX_OR_B64_BLOB.search(line):
            if SENSITIVE_KEY.search(line) or "SECRET" in line or "TOKEN" in line:
                continue  # 已由 C9.1 覆盖
            if any(x in line for x in ("CLIENT_ID", "UUID", "DEVICE_ID")):
                continue  # 公开标识符

    return issues


def check_file(path: Path) -> list[dict]:
    """标准 checker 接口：读取文件并扫描。"""
    result = read_file(path)
    if result is None:
        return []
    _lines, text = result
    return scan_text(path, text)


def scan_git_remotes() -> list[dict]:
    """扫描当前仓库 git remote URL 中的内嵌凭证。"""
    issues: list[dict] = []
    try:
        proc = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return issues
    if proc.returncode != 0:
        return issues
    for i, line in enumerate(proc.stdout.splitlines(), start=1):
        if GIT_CRED_URL.search(line):
            issues.append(
                make_issue_str(
                    f"git-remote:{i}",
                    "C9.2",
                    "P0",
                    "git remote URL 含内嵌 token/密码",
                )
            )
    return issues


def main() -> int:
    """支持 --git-remotes + 标准 run_checker 接口。"""
    import sys

    git_remotes = "--git-remotes" in sys.argv
    if git_remotes:
        sys.argv.remove("--git-remotes")

    from checker_io import configure_stdout, output_json
    configure_stdout()

    exit_code = 0

    if git_remotes:
        remote_issues = scan_git_remotes()
        if remote_issues:
            for iss in remote_issues:
                print(f"  [{iss['severity']}] {iss['id']} — {iss['file']} — {iss['issue']}")
            exit_code = 1
        else:
            print("[密钥/凭证扫描] git remote 无内嵌凭证")

    # 标准文件扫描（如果有文件参数）
    remaining_args = sys.argv[1:]
    if remaining_args:
        file_rc = run_checker(check_file, "密钥/凭证启发式扫描 (C9)", ("C9",), SCAN_EXTENSIONS)
        exit_code = max(exit_code, file_rc)
    elif git_remotes and not remaining_args:
        pass  # 仅扫描 git remotes，无文件参数

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
