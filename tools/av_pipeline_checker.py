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

import re
from pathlib import Path

from checker_io import (
    FunctionSpan,
    extract_functions,
    line_at,
    make_issue,
    read_file,
    run_checker,
    strip_comments,
)
from sdk_lookup import SdkLookup

# 全平台 SDK 查询
_ALL_PLATFORMS = ["esp32", "stm32", "jl", "bk", "zephyr"]
_lookup = SdkLookup(_ALL_PLATFORMS)


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
# SDK lookup 构建回调禁用 API 正则
_bad_callback_apis = set(_lookup.get_all_apis("TIMER_HANDLER", "PARSE", "SOCKET_RECV", "SOCKET_SEND", "SOCKET_CONNECT"))
# 补充 video/audio decode 和 codec 等非标准 SDK API
_bad_callback_apis.update(["video_decode", "audio_decode", "codec_open", "codec_create",
                            "h264_decode", "h264_encode", "jpeg_decode", "jpeg_encode",
                            "mjpeg_decode", "mjpeg_encode"])
_lv_apis = _lookup.get_all_apis("TIMER_HANDLER", "ASYNC_CALL", "OBJ_CREATE", "OBJ_SET", "OBJ_DELETE")
# 过滤 lv_ 排除项
_lv_filtered = [a for a in _lv_apis if a != "lv_disp_flush_ready"]
_bad_callback_apis.update(_lv_filtered)
BAD_CALLBACK_RE = re.compile(
    r"\b(?:%s)\s*\(" % "|".join(re.escape(a) for a in sorted(_bad_callback_apis)),
    re.IGNORECASE,
)
HOT_ALLOC_LOG_RE = _lookup.build_regex("HEAP_ALLOC", "HEAP_FREE", "PRINTF", "LOG_WRITE")
# 构建队列永久等待正则（QUEUE + TIMEOUT_FOREVER）
_queue_send_re = _lookup.build_regex("QUEUE_SEND", "QUEUE_RECV", "QUEUE_OVERWRITE")
_forever_re = _lookup.build_constant_regex("TIMEOUT_FOREVER")
_queue_m = re.search(r'\(\?:([^)]+)\)', _queue_send_re.pattern)
_forever_m = re.search(r'\(\?:([^)]+)\)', _forever_re.pattern)
_queue_core = _queue_m.group(1) if _queue_m else "xQueueSend"
_forever_core = _forever_m.group(1) if _forever_m else "portMAX_DELAY"
QUEUE_FOREVER_RE = re.compile(
    r"\b(?:%s)\s*\([^;]*(?:%s)" % (_queue_core, _forever_core),
    re.DOTALL,
)


def has_any(text: str, words: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(word in lower for word in words)


def check_audio_master(path: Path, code: str) -> list[dict[str, str]]:
    lower = code.lower()
    has_audio = any(kw in lower for kw in ("audio", "i2s", "pcm", "speaker", "mic", "aec"))
    has_video = any(kw in lower for kw in ("video", "camera", "preview", "h264", "jpeg", "lcd", "display"))
    if has_audio and has_video and not has_any(code, SYNC_KEYWORDS):
        return [make_issue(path, 1, "C25.1", "P0", "音视频同文件管线未找到 PTS/timestamp/audio_clock 等同步依据")]
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
            issues.append(make_issue(
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
        issues.append(make_issue(
            path,
            line_at(code, match.start()),
            "C25.3",
            "P1",
            "音视频热路径队列使用 portMAX_DELAY，可能阻塞 audio/camera/display 管线",
        ))
    return issues


def check_hotpath_alloc_log(path: Path, functions: list[FunctionSpan]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        if not HOT_FUNC_RE.search(func.name):
            continue
        for match in HOT_ALLOC_LOG_RE.finditer(func.body):
            rel_line = func.body[:match.start()].count("\n")
            issues.append(make_issue(
                path,
                func.line + rel_line,
                "C25.4",
                "P1",
                f"{func.name} 每帧/回调热路径中出现 {match.group(0).rstrip('(')}",
            ))
    return issues


def check_callback_isolation(path: Path, functions: list[FunctionSpan]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        if not CALLBACK_RE.search(func.name):
            continue
        for match in BAD_CALLBACK_RE.finditer(func.body):
            rel_line = func.body[:match.start()].count("\n")
            issues.append(make_issue(
                path,
                func.line + rel_line,
                "C25.5",
                "P0",
                f"{func.name} callback 中执行复杂操作 {match.group(0).rstrip('(')}，应只 notify/enqueue",
            ))
    return issues


def check_telemetry(path: Path, code: str) -> list[dict[str, str]]:
    lower = code.lower()
    if has_any(lower, SYNC_KEYWORDS) and not has_any(lower, TELEMETRY_KEYWORDS):
        return [make_issue(path, 1, "C25.6", "P2", "A/V sync 代码缺少 drift/drop/underrun 等遥测计数")]
    return []


def check_file(path: Path) -> list[dict[str, str]]:
    result = read_file(path)
    if result is None:
        return []

    _lines, text = result
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


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C25 音视频管线 / A/V Sync 检查器", ("C25",)))
