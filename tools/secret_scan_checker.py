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
    python tools/secret_scan_checker.py --git-remotes
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from checker_io import configure_stdout

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
    ".config",
    ".cfg",
    ".env",
    ".ini",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".sh",
    ".py",
    ".c",
    ".h",
    ".md",
}

SKIP_DIRS = {
    ".git",
    "build",
    "node_modules",
    "__pycache__",
    "freertos-skill-lite",
    "fixtures",
    "examples",
}


@dataclass
class Finding:
    file: str
    line_no: int
    rule: str
    line_text: str
    hint: str


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def violation_count(self) -> int:
        return len(self.findings)


def should_scan_file(path: Path) -> bool:
    if path.name.endswith(".example") or path.name.endswith(".sample"):
        return False
    if path.suffix.lower() in SCAN_EXTENSIONS or path.name in (
        "config",
        "config.local",
        "config.merged",
    ):
        return True
    return False


def scan_text(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    rel = str(path)

    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if m := SENSITIVE_KEY.search(line):
            key = m.group(0).split("=", 1)[0].strip()
            if NONEMPTY_VALUE.search(line):
                findings.append(
                    Finding(
                        rel,
                        i,
                        "C9.1",
                        stripped[:120],
                        f"敏感 Kconfig 键 {key} 含非空值，应移至 config.secrets（不入库）",
                    )
                )

        if GIT_CRED_URL.search(line):
            findings.append(
                Finding(
                    rel,
                    i,
                    "C9.2",
                    "<redacted>",
                    "Git URL 内嵌凭证，改用 SSH 或 credential helper",
                )
            )

        if "CONFIG_" in line and HEX_OR_B64_BLOB.search(line):
            if SENSITIVE_KEY.search(line) or "SECRET" in line or "TOKEN" in line:
                continue  # 已由 C9.1 覆盖
            if any(x in line for x in ("CLIENT_ID", "UUID", "DEVICE_ID")):
                continue  # 公开标识符

    return findings


def scan_file(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"[warn] 无法读取 {path}: {exc}", file=sys.stderr)
        return []
    return scan_text(path, text)


def collect_files(targets: list[str], dir_path: str | None) -> list[Path]:
    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_file():
            files.append(p.resolve())
        elif p.is_dir():
            for f in p.rglob("*"):
                if not f.is_file():
                    continue
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                if should_scan_file(f):
                    files.append(f.resolve())
    if dir_path:
        root = Path(dir_path)
        if root.is_dir():
            for f in root.rglob("*"):
                if not f.is_file():
                    continue
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                if should_scan_file(f):
                    files.append(f.resolve())
    seen: set[Path] = set()
    out: list[Path] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return sorted(out)


def scan_git_remotes() -> list[Finding]:
    findings: list[Finding] = []
    try:
        proc = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return findings
    if proc.returncode != 0:
        return findings
    for i, line in enumerate(proc.stdout.splitlines(), start=1):
        if GIT_CRED_URL.search(line):
            findings.append(
                Finding(
                    "git-remote",
                    i,
                    "C9.2",
                    "<redacted>",
                    "git remote URL 含内嵌 token/密码",
                )
            )
    return findings


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="密钥/凭证启发式扫描 (C9)")
    parser.add_argument("files", nargs="*", help="待扫描文件或目录")
    parser.add_argument("--dir", "-d", help="递归扫描目录")
    parser.add_argument("--git-remotes", action="store_true", help="扫描当前仓库 git remote")
    args = parser.parse_args()

    result = ScanResult()
    if args.git_remotes:
        result.findings.extend(scan_git_remotes())

    paths = collect_files(args.files, args.dir)
    for p in paths:
        result.findings.extend(scan_file(p))

    print(f"扫描文件数: {len(paths)}")
    print(f"违规数: {result.violation_count}")
    for f in result.findings:
        print(f"\n[{f.rule}] {f.file}:{f.line_no}")
        print(f"  {f.hint}")
        if f.line_text != "<redacted>":
            print(f"  > {f.line_text}")

    return 1 if result.violation_count else 0


if __name__ == "__main__":
    sys.exit(main())
