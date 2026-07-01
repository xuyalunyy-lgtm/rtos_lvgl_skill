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

import argparse
import re
import sys
from pathlib import Path

# --- Patterns ---

COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
FUNC_DEF_RE = re.compile(
    r"(?:^|[\n;])\s*"
    r"(?:static\s+)?(?:inline\s+)?"
    r"(?:[A-Za-z_][\w\s\*]*\s+)+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.MULTILINE,
)
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
CONTROL_NAMES = {"if", "for", "while", "switch", "return", "sizeof"}

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


def strip_comments(text: str) -> str:
    """Remove C/C++ comments while preserving line numbers."""
    return COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def extract_functions(code: str) -> dict[str, dict[str, object]]:
    functions: dict[str, dict[str, object]] = {}
    for match in FUNC_DEF_RE.finditer(code):
        name = match.group("name")
        if name in CONTROL_NAMES:
            continue
        open_pos = code.find("{", match.end() - 1)
        close_pos = find_matching_brace(code, open_pos)
        if open_pos < 0 or close_pos < 0:
            continue
        functions[name] = {
            "body": code[open_pos + 1:close_pos],
            "line": code[:match.start("name")].count("\n") + 1,
        }
    return functions


def has_detach_call(body: str, functions: dict[str, dict[str, object]], seen: set[str] | None = None) -> bool:
    if DETACH_CALL_PATTERN.search(body):
        return True
    seen = seen or set()
    for callee in CALL_RE.findall(body):
        if callee in seen or callee not in functions:
            continue
        seen.add(callee)
        if has_detach_call(str(functions[callee]["body"]), functions, seen):
            return True
    return False


def matching_functions(
    pattern: re.Pattern[str],
    functions: dict[str, dict[str, object]],
) -> list[tuple[str, dict[str, object]]]:
    matched = []
    for name, info in functions.items():
        signature = f"{name}("
        body = str(info["body"])
        if pattern.search(signature) or pattern.search(body):
            matched.append((name, info))
    return matched


def check_file(path: Path) -> list[dict]:
    """Check a single .c file for C10 issues."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    code = strip_comments(text)
    functions = extract_functions(code)
    issues: list[dict] = []

    # Only check files that actually deal with voice/prompt/capture
    is_voice_file = any(kw in code.lower() for kw in [
        "prompt_tone", "playback", "uplink", "capture", "asr", "voice_session",
        "prompt_detach", "tts", "audio_detach",
    ])
    if not is_voice_file:
        return []

    # C10.1: stop 与 FINISHED 两条路径都必须真正 detach playback
    for name, info in matching_functions(STOP_PATTERN, functions):
        if not has_detach_call(str(info["body"]), functions):
            issues.append({
                "id": "C10.1",
                "file": f"{path}:{info['line']}",
                "issue": f"prompt stop 路径 {name} 未找到 detach playback 调用",
                "severity": "P0",
            })

    for name, info in matching_functions(FINISHED_PATTERN, functions):
        if not has_detach_call(str(info["body"]), functions):
            issues.append({
                "id": "C10.1",
                "file": f"{path}:{info['line']}",
                "issue": f"playback FINISHED 回调 {name} 未找到 detach playback 调用",
                "severity": "P0",
            })

    # C10.2: If uplink start exists, check settle delay
    has_uplink_start = bool(UPLINK_START_PATTERN.search(code))
    for _, info in functions.items():
        body = str(info["body"])
        for match in UPLINK_START_PATTERN.finditer(body):
            prefix = body[:match.start()]
            if not (SETTLE_PATTERN.search(prefix) or MIC_READY_PATTERN.search(prefix)):
                issues.append({
                    "id": "C10.2",
                    "file": f"{path}:{int(info['line']) + prefix.count(chr(10))}",
                    "issue": "start_uplink 前未找到 AEC settle / wait_mic_capture_ready",
                    "severity": "P0",
                })

    # C10.5: If voice session exists, check generation mechanism
    has_gen = bool(GEN_PATTERN.search(code))
    has_gen_check = bool(GEN_CHECK_PATTERN.search(code))
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
