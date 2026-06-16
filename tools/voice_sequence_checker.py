#!/usr/bin/env python3
"""
C10 语音/Uplink 时序启发式检查器。

检查项:
  C10.1 — prompt/TTS stop + FINISHED 两路径是否都 detach playback
  C10.2 — start_uplink / capture_on 是否在 settle delay 之后
  C10.5 — session generation 变量是否存在

用法:
    python tools/voice_sequence_checker.py <file.c> [file2.c ...]
    python tools/voice_sequence_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --- Patterns ---

# C10.1: detach 函数名
DETACH_PATTERNS = [
    r"audio_detach_playback",
    r"detach_playback",
    r"close_playback_session",
    r"playback_attached\s*=\s*(?:0|false|FALSE)",
]

# C10.1: stop + FINISHED 回调
STOP_PATTERN = re.compile(r"(?:_stop|_stop_stream|prompt_tone_stop|tts_stop)\s*\(")
FINISHED_PATTERN = re.compile(r"(?:on_playback_finished|on_playback_end|on_audio_end|FINISHED|AUDIO_SERVER_EVENT_END)\s*\(")

# C10.2: uplink / capture start
UPLINK_START_PATTERN = re.compile(r"(?:start_uplink|capture_on|start_capture|begin_capture)\s*\(")

# C10.2: settle delay
SETTLE_PATTERN = re.compile(r"(?:AEC_SETTLE|aec.?settle|vTaskDelay\s*\(\s*pdMS_TO_TICKS\s*\(\s*\d{2,4}\s*\)\s*\))", re.IGNORECASE)
MIC_READY_PATTERN = re.compile(r"(?:wait_mic_capture_ready|mic_capture_ready|heal_mic)", re.IGNORECASE)

# C10.5: generation
GEN_PATTERN = re.compile(r"(?:capture_gen|session_gen|voice_gen)\s*")
GEN_CHECK_PATTERN = re.compile(r"(?:is_current_generation|session_is_current|generation\s*!=|generation\s*==|gen\s*!=|gen\s*==)")


def check_file(path: Path) -> list[dict]:
    """Check a single .c file for C10 issues."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    issues: list[dict] = []
    lines = text.splitlines()

    has_stop = bool(STOP_PATTERN.search(text))
    has_finished = bool(FINISHED_PATTERN.search(text))
    has_detach = any(re.search(p, text) for p in DETACH_PATTERNS)
    has_uplink_start = bool(UPLINK_START_PATTERN.search(text))
    has_settle = bool(SETTLE_PATTERN.search(text)) or bool(MIC_READY_PATTERN.search(text))
    has_gen = bool(GEN_PATTERN.search(text))
    has_gen_check = bool(GEN_CHECK_PATTERN.search(text))

    # Only check files that actually deal with voice/prompt/capture
    is_voice_file = any(kw in text.lower() for kw in [
        "prompt_tone", "playback", "uplink", "capture", "asr", "voice_session",
        "prompt_detach", "tts", "audio_detach",
    ])
    if not is_voice_file:
        return []

    # C10.1: If stop exists, check both stop and FINISHED paths have detach
    if has_stop and not has_detach:
        issues.append({
            "id": "C10.1",
            "file": str(path),
            "issue": "prompt stop 路径未找到 detach_playback 调用",
            "severity": "P0",
        })

    if has_finished and not has_detach:
        issues.append({
            "id": "C10.1",
            "file": str(path),
            "issue": "playback FINISHED 回调未找到 detach_playback 调用",
            "severity": "P0",
        })

    # C10.2: If uplink start exists, check settle delay
    if has_uplink_start and not has_settle:
        # Find line numbers for context
        for i, line in enumerate(lines, 1):
            if UPLINK_START_PATTERN.search(line):
                issues.append({
                    "id": "C10.2",
                    "file": f"{path}:{i}",
                    "issue": "start_uplink 前未找到 AEC settle / wait_mic_capture_ready",
                    "severity": "P0",
                })
                break

    # C10.5: If voice session exists, check generation mechanism
    if has_uplink_start and not has_gen:
        issues.append({
            "id": "C10.5",
            "file": str(path),
            "issue": "未找到 session generation 变量（capture_gen），无法过滤 stale 回调",
            "severity": "P1",
        })

    if has_gen and not has_gen_check:
        issues.append({
            "id": "C10.5",
            "file": str(path),
            "issue": "有 capture_gen 但未在回调中校验 generation",
            "severity": "P1",
        })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C10 语音/Uplink 时序检查器")
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

    # Deduplicate
    seen: set[Path] = set()
    unique: list[Path] = []
    for t in targets:
        r = t.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if not unique:
        print("[voice_sequence_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        issues = check_file(path)
        all_issues.extend(issues)

    if not all_issues:
        print(f"[voice_sequence_checker] 已检查 {len(unique)} 个文件，未发现 C10 违规")
        return 0

    print(f"[voice_sequence_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C10 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C10 warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())