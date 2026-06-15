"""Checker 脚本共用：Windows GBK 控制台 UTF-8 输出。"""
from __future__ import annotations

import sys


def configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
