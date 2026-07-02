#!/usr/bin/env python3
"""
Skill Session Guard Hook — 会话纪律审计提醒。

在 UserPromptSubmit 或 Stop 事件时检查本轮是否遵守 skill 入口纪律。
仅用于提醒和审计，不阻断执行。

用法（在 hooks.json 中配置）：
{
  "hooks": {
    "UserPromptSubmit": [
      {"type": "command", "command": "python .codex/hooks/skill_session_guard.py --event prompt"}
    ],
    "Stop": [
      {"type": "command", "command": "python .codex/hooks/skill_session_guard.py --event stop"}
    ]
  }
}
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "session_guard_log.jsonl"


def log_event(event: str, detail: str = ""):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "detail": detail,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def on_prompt():
    """UserPromptSubmit 事件：提醒用户当前是否在 strict mode。"""
    log_event("prompt_submit", "checking skill discipline")
    # 输出提醒（Codex 会显示给用户）
    print("[skill-guard] 提示：当前项目配置了 freertos-embedded-architect skill。")
    print("[skill-guard] 如需严格模式，请说：启用 freertos-embedded-architect 严格模式")


def on_stop():
    """Stop 事件：记录本轮是否遵守了 skill 纪律。"""
    log_event("stop", "recording session state")
    print("[skill-guard] 本轮结束。如需持续遵守 skill 纪律，请保持严格模式激活。")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", choices=["prompt", "stop"], required=True)
    args = parser.parse_args()

    if args.event == "prompt":
        on_prompt()
    elif args.event == "stop":
        on_stop()


if __name__ == "__main__":
    main()
