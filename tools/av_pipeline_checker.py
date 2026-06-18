#!/usr/bin/env python3
"""
C25 音视频管线 / A/V Sync 启发式检查器。

检查项:
  C25.1 — 同时存在 audio/video 管线时必须有 audio clock / PTS 同步依据
  C25.2 — audio/video frame 结构必须带 PTS/timestamp、seq、duration/sample_count
  C25.3 — media hot path 队列禁止 portMAX_DELAY
  C25.4 — per-frame hot path 禁 malloc/free/printf/LOG_*
  C25.5 — camera/LCD/DMA callback 禁复杂 UI/codec/network/json 操作
  C25.6 — A/V sync 文件建议保留 drift/drop/underrun 计数

用法:
    python tools/av_pipeline_checker.py <file.c> [file2.c ...]
    python tools/av_pipeline_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
FUNC_DEF_RE = re.compile(
    r"(?:^|[\n;])\s*"
    r"(?:static\s+)?(?:inline\s+)?"
    r"(?:[A-Za-z_][\w\s\*]*\s+)+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.MULTILINE,
)
STRUCT_RE = re.compile(
    r"typedef\s+struct(?:\s+[A-Za-z_]\w*)?\s*\{(?P<body>.*?)\}\s*(?P<name>[A-Za-z_]\w*)\s*;",
    re.DOTALL,
)

MEDIA_KEYWORDS = (
    "audio", "i2s", "pcm", "speaker", "mic", "codec", "aec",
    "video", "camera", "frame", "preview", "h264", "jpeg", "mjpeg",
    "lcd", "display", "lvgl", "lv_", "av_", "pts", "timestamp",
)
SYNC_KEYWORDS = (
    "pts", "timestamp", "audio_clock", "sample_clock", "i2s_clock",
    "av_sync", "drift", "sample_count", "duration_ms",
)
TELEMETRY_KEYWORDS = (
    "dropped", "drop_", "late_", "drift", "underrun", "overrun", "high_water",
)
FRAME_NAME_RE = re.compile(r"(?:audio|video|media|camera|av)_.*frame|frame_.*(?:audio|video|media|camera|av)")
HOT_FUNC_RE = re.compile(
    r"(?:audio|video|camera|av|codec|decode|encode|render|capture|playback|frame|isr|callback|cb)",
    re.IGNORECASE,
)
CALLBACK_RE = re.compile(
    r"(?:camera.*(?:callback|cb|isr)|.*frame.*(?:callback|cb)|HAL_.*CpltCallback|.*dma.*(?:callback|cb|isr)|lcd_flush_cb|.*flush_cb)",
    re.IGNORECASE,
)
BAD_CALLBACK_RE = re.compile(
    r"\b(?:lv_(?!disp_flush_ready)\w+|cJSON_\w+|recv|send|connect|video_decode\w*|audio_decode\w*|"
    r"codec_\w+|h264_\w+|jpeg_\w+|mjpeg_\w+)\s*\(",
    re.IGNORECASE,
)
HOT_ALLOC_LOG_RE = re.compile(
    r"\b(?:malloc|calloc|free|pvPortMalloc|vPortFree|heap_caps_malloc|heap_caps_calloc|"
    r"printf|puts|LOG_[A-Z]+|ESP_LOG[IEWD])\s*\(",
)
QUEUE_FOREVER_RE = re.compile(r"\bxQueue(?:Send|Receive|SendToBack|SendToFront|Overwrite)\s*\([^;]*portMAX_DELAY", re.DOTALL)


def strip_comments(text: str) -> str:
    """Remove C/C++ comments while preserving line numbers."""
    return COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def line_at(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


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


def extract_functions(code: str) -> list[dict[str, object]]:
    functions: list[dict[str, object]] = []
    for match in FUNC_DEF_RE.finditer(code):
        name = match.group("name")
        if name in {"if", "for", "while", "switch", "return", "sizeof"}:
            continue
        open_pos = code.find("{", match.end() - 1)
        close_pos = find_matching_brace(code, open_pos)
        if open_pos < 0 or close_pos < 0:
            continue
        functions.append({
            "name": name,
            "body": code[open_pos + 1:close_pos],
            "line": line_at(code, match.start("name")),
        })
    return functions


def has_any(text: str, words: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(word in lower for word in words)


def issue(path: Path, line: int | str, cid: str, severity: str, msg: str) -> dict[str, str]:
    loc = f"{path}:{line}" if isinstance(line, int) else str(path)
    return {"id": cid, "file": loc, "severity": severity, "issue": msg}


def check_audio_master(path: Path, code: str) -> list[dict[str, str]]:
    lower = code.lower()
    has_audio = any(kw in lower for kw in ("audio", "i2s", "pcm", "speaker", "mic", "aec"))
    has_video = any(kw in lower for kw in ("video", "camera", "preview", "h264", "jpeg", "lcd", "display"))
    if has_audio and has_video and not has_any(code, SYNC_KEYWORDS):
        return [issue(path, 1, "C25.1", "P0", "音视频同文件管线未找到 PTS/timestamp/audio_clock 等同步依据")]
    return []


def check_frame_structs(path: Path, code: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for match in STRUCT_RE.finditer(code):
        name = match.group("name")
        body = match.group("body")
        combined = f"{name} {body}".lower()
        if not FRAME_NAME_RE.search(combined):
            continue

        has_pts = any(token in combined for token in ("pts", "timestamp"))
        has_seq = re.search(r"\b(?:seq|sequence)\b", combined) is not None
        has_duration = any(token in combined for token in ("duration", "sample_count", "samples"))
        if not (has_pts and has_seq and has_duration):
            missing = []
            if not has_pts:
                missing.append("PTS/timestamp")
            if not has_seq:
                missing.append("seq")
            if not has_duration:
                missing.append("duration/sample_count")
            issues.append(issue(
                path,
                line_at(code, match.start()),
                "C25.2",
                "P0",
                f"{name} 缺少帧元数据: {', '.join(missing)}",
            ))
    return issues


def check_queue_forever(path: Path, code: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not has_any(code, MEDIA_KEYWORDS):
        return issues
    for match in QUEUE_FOREVER_RE.finditer(code):
        issues.append(issue(
            path,
            line_at(code, match.start()),
            "C25.3",
            "P1",
            "音视频热路径队列使用 portMAX_DELAY，可能阻塞 audio/camera/display 管线",
        ))
    return issues


def check_hotpath_alloc_log(path: Path, functions: list[dict[str, object]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        name = str(func["name"])
        body = str(func["body"])
        if not HOT_FUNC_RE.search(name):
            continue
        for match in HOT_ALLOC_LOG_RE.finditer(body):
            rel_line = body[:match.start()].count("\n")
            issues.append(issue(
                path,
                int(func["line"]) + rel_line,
                "C25.4",
                "P1",
                f"{name} 每帧/回调热路径中出现 {match.group(0).rstrip('(')}",
            ))
    return issues


def check_callback_isolation(path: Path, functions: list[dict[str, object]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        name = str(func["name"])
        body = str(func["body"])
        if not CALLBACK_RE.search(name):
            continue
        for match in BAD_CALLBACK_RE.finditer(body):
            rel_line = body[:match.start()].count("\n")
            issues.append(issue(
                path,
                int(func["line"]) + rel_line,
                "C25.5",
                "P0",
                f"{name} callback 中执行复杂操作 {match.group(0).rstrip('(')}，应只 notify/enqueue",
            ))
    return issues


def check_telemetry(path: Path, code: str) -> list[dict[str, str]]:
    lower = code.lower()
    if has_any(lower, SYNC_KEYWORDS) and not has_any(lower, TELEMETRY_KEYWORDS):
        return [issue(path, 1, "C25.6", "P2", "A/V sync 代码缺少 drift/drop/underrun 等遥测计数")]
    return []


def check_file(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    code = strip_comments(text)
    if not has_any(code, MEDIA_KEYWORDS):
        return []

    functions = extract_functions(code)
    issues: list[dict[str, str]] = []
    issues.extend(check_audio_master(path, code))
    issues.extend(check_frame_structs(path, code))
    issues.extend(check_queue_forever(path, code))
    issues.extend(check_hotpath_alloc_log(path, functions))
    issues.extend(check_callback_isolation(path, functions))
    issues.extend(check_telemetry(path, code))
    return issues


def collect_targets(files: list[str], dir_path: str | None) -> list[Path]:
    targets: list[Path] = []
    for f in files:
        p = Path(f)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            targets.extend(sorted(p.rglob("*.c")))
            targets.extend(sorted(p.rglob("*.cpp")))
    if dir_path:
        d = Path(dir_path)
        if d.is_dir():
            targets.extend(sorted(d.rglob("*.c")))
            targets.extend(sorted(d.rglob("*.cpp")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for target in targets:
        resolved = target.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description="C25 音视频管线 / A/V Sync 检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c/.cpp 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    args = parser.parse_args()

    targets = collect_targets(args.files, args.dir)
    if not targets:
        print("[av_pipeline_checker] 无文件可检查")
        return 0

    all_issues: list[dict[str, str]] = []
    for path in targets:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[av_pipeline_checker] 已检查 {len(targets)} 个文件，未发现 C25 违规")
        return 0

    print(f"[av_pipeline_checker] 已检查 {len(targets)} 个文件，发现 {len(all_issues)} 个 C25 告警:\n")
    for item in all_issues:
        print(f"  [{item['severity']}] {item['id']} — {item['file']} — {item['issue']}")

    print(f"\nSummary: {len(all_issues)} C25 A/V pipeline warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
