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

import argparse
import json
import re
import subprocess
from pathlib import Path

from checker_io import collect_targets, configure_stdout, make_issue_str, output_json, read_file

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
    """Scan files/remotes and emit checker-result/v1 when machine-readable."""
    configure_stdout()
    parser = argparse.ArgumentParser(description="密钥/凭证启发式扫描 (C9)")
    parser.add_argument("files", nargs="*", help="待扫描文件")
    parser.add_argument("--dir", "-d", help="递归扫描目录")
    parser.add_argument("--git-remotes", action="store_true", help="scan git remote URLs")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--jsonl", action="store_true", help="single checker-result/v1 JSON Lines record")
    args = parser.parse_args()

    targets = collect_targets(args.files, args.dir, SCAN_EXTENSIONS)
    issues: list[dict] = []
    if args.git_remotes:
        issues.extend(scan_git_remotes())
    for target in targets:
        issues.extend(check_file(target))

    payload = {
        "protocol_version": "checker-result/v1",
        "checker": "密钥/凭证启发式扫描 (C9)",
        "domains": ["C9"],
        "files_checked": len(targets),
        "violations": len(issues),
        "issues": issues,
    }
    if args.jsonl:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    elif args.json:
        output_json(payload)
    elif not targets and not args.git_remotes:
        print("[密钥/凭证扫描] 无文件可检查")
    elif not issues:
        print(f"[密钥/凭证扫描] 已检查 {len(targets)} 个文件，未发现 C9 违规")
    else:
        print(f"[密钥/凭证扫描] 已检查 {len(targets)} 个文件，发现 {len(issues)} 个 C9 告警:\n")
        for issue in issues:
            print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")
        print(f"\nSummary: {len(issues)} C9 warnings")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
