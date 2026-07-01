#!/usr/bin/env python3
"""
C10 语音/Uplink 时序启发式检查器。

检查项:
  C10.1 — prompt/TTS stop + FINISHED 两路径是否都 detach playback
  C10.2 — start_uplink / capture_on 是否在 settle delay 之后
  C10.5 — session generation 变量是否存在（stale FINISHED/timer/TTS chunk 需人工确认）

用法:
    python tools/voice_sequence_checker.py <file.c> [file2.c ...]
    python tools/voice_sequence_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import FunctionSpan, make_issue, read_file, run_checker, strip_comments, extract_functions

# --- Patterns ---

CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")

# C10.1: detach 函数调用名（仅清 flag 不算真正 detach playback）
DETACH_CALL_PATTERN = re.compile(
    r"\b(?:"
    r"\w*detach\w*playback\w*|"
    r"\w*playback\w*detach\w*|"
    r"close_playback_session|"
    r"release_playback_session|"
    r"unregister_playback"
    r")\s*\("
)

# C10.1: stop + FINISHED 回调
STOP_PATTERN = re.compile(r"\b(?:\w*_stop(?:_stream)?|prompt_tone_stop|tts_stop)\s*\(")
FINISHED_PATTERN = re.compile(
    r"\b(?:\w*on_playback_finished\w*|on_playback_end|on_audio_end|FINISHED|AUDIO_SERVER_EVENT_END)\s*\("
)

# C10.2: uplink / capture start
UPLINK_START_PATTERN = re.compile(
    r"\b(?:audio_start_uplink|start_uplink|capture_on|start_capture|begin_capture|session_begin_capture)\s*\("
)

# C10.2: settle delay
SETTLE_PATTERN = re.compile(r"(?:AEC_SETTLE|aec.?settle|vTaskDelay\s*\(\s*pdMS_TO_TICKS\s*\(\s*\d{2,4}\s*\)\s*\))", re.IGNORECASE)
MIC_READY_PATTERN = re.compile(r"(?:wait_mic_capture_ready|mic_capture_ready|heal_mic)", re.IGNORECASE)

# C10.5: generation
GEN_PATTERN = re.compile(r"(?:capture_gen|session_gen|voice_gen)\s*")
GEN_CHECK_PATTERN = re.compile(r"(?:is_current_generation|session_is_current|generation\s*!=|generation\s*==|gen\s*!=|gen\s*==)")


def _build_func_map(functions: list[FunctionSpan]) -> dict[str, FunctionSpan]:
    return {f.name: f for f in functions}


def has_detach_call(body: str, func_map: dict[str, FunctionSpan], seen: set[str] | None = None) -> bool:
    if DETACH_CALL_PATTERN.search(body):
        return True
    seen = seen or set()
    for callee in CALL_RE.findall(body):
        if callee in seen or callee not in func_map:
            continue
        seen.add(callee)
        if has_detach_call(func_map[callee].body, func_map, seen):
            return True
    return False


def matching_functions(
    pattern: re.Pattern[str],
    func_map: dict[str, FunctionSpan],
) -> list[tuple[str, FunctionSpan]]:
    matched = []
    for name, info in func_map.items():
        signature = f"{name}("
        if pattern.search(signature) or pattern.search(info.body):
            matched.append((name, info))
    return matched


def check_file(path: Path) -> list[dict]:
    """Check a single .c file for C10 issues."""
    result = read_file(path)
    if result is None:
        return []
    _, text = result

    code = strip_comments(text)
    func_map = _build_func_map(extract_functions(code))
    issues: list[dict] = []

    # Only check files that actually deal with voice/prompt/capture
    is_voice_file = any(kw in code.lower() for kw in [
        "prompt_tone", "playback", "uplink", "capture", "asr", "voice_session",
        "prompt_detach", "tts", "audio_detach",
    ])
    if not is_voice_file:
        return []

    # C10.1: stop 与 FINISHED 两条路径都必须真正 detach playback
    for name, info in matching_functions(STOP_PATTERN, func_map):
        if not has_detach_call(info.body, func_map):
            issues.append(make_issue(path, info.line, "C10.1", "P0",
                f"prompt stop 路径 {name} 未找到 detach playback 调用"))

    for name, info in matching_functions(FINISHED_PATTERN, func_map):
        if not has_detach_call(info.body, func_map):
            issues.append(make_issue(path, info.line, "C10.1", "P0",
                f"playback FINISHED 回调 {name} 未找到 detach playback 调用"))

    # C10.2: If uplink start exists, check settle delay
    has_uplink_start = bool(UPLINK_START_PATTERN.search(code))
    for _, info in func_map.items():
        for match in UPLINK_START_PATTERN.finditer(info.body):
            prefix = info.body[:match.start()]
            if not (SETTLE_PATTERN.search(prefix) or MIC_READY_PATTERN.search(prefix)):
                issues.append(make_issue(path, info.line + prefix.count("\n"), "C10.2", "P0",
                    "start_uplink 前未找到 AEC settle / wait_mic_capture_ready"))

    # C10.5: If voice session exists, check generation mechanism
    has_gen = bool(GEN_PATTERN.search(code))
    has_gen_check = bool(GEN_CHECK_PATTERN.search(code))
    if has_uplink_start and not has_gen:
        issues.append(make_issue(path, 1, "C10.5", "P1",
            "未找到 session generation 变量（capture_gen），无法过滤 stale 回调"))

    if has_gen and not has_gen_check:
        issues.append(make_issue(path, 1, "C10.5", "P1",
            "有 capture_gen 但未在回调中校验 generation"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C10 语音/Uplink 时序检查器", ("C10",)))
