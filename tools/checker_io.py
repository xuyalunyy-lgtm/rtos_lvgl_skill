"""Checker 脚本共用：Windows GBK 控制台 UTF-8 输出 + JSON 输出。"""
from __future__ import annotations

import json
import sys
from typing import Any


def configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def output_json(data: dict[str, Any], file=None) -> None:
    """输出 JSON 格式结果（CI 集成 / 机器可读）。"""
    stream = file or sys.stdout
    try:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        print(file=stream)
    except UnicodeEncodeError:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
            json.dump(data, stream, ensure_ascii=False, indent=2)
            print(file=stream)
        else:
            raise


def safe_print(text: str, file=None) -> None:
    """Print with UTF-8 fallback for Windows GBK consoles."""
    stream = file or sys.stdout
    try:
        print(text, end="", file=stream)
    except UnicodeEncodeError:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
            print(text, end="", file=stream)
        else:
            raise
