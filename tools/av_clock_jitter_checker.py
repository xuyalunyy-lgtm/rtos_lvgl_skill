#!/usr/bin/env python3
"""
C27 音视频时钟漂移 / Jitter Buffer 启发式检查器。
检查项:
  C27.1 — A/V sync 必须有 master clock 与单调 PTS
  C27.2 — jitter buffer 必须有 capacity + low/high/target watermarks
  C27.3 — drift correction 必须限幅
  C27.4 — render/playback/sync 热路径禁止按 drift/PTS vTaskDelay 或 portMAX_DELAY 等待
  C27.5 — underrun/overrun/jitter handler 禁止 malloc/free/printf/LOG_*，且要有补偿策略
  C27.6 — 建议保留 drift/jitter/underrun/overrun/drop/insert/resync 遥测
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import extract_functions, line_at, make_issue, read_file, run_checker, strip_comments


DEFINE_RE = re.compile(r"^\s*#define\s+([A-Za-z_]\w*)\s+\(?(-?[0-9]+)U?\)?", re.MULTILINE)

MEDIA_RE = re.compile(
    r"(audio|video|camera|pcm|i2s|av_|pts|timestamp|jitter|rtp|lip|sync|drift)",
    re.IGNORECASE,
)
AUDIO_RE = re.compile(r"(audio|pcm|i2s|speaker|mic)", re.IGNORECASE)
VIDEO_RE = re.compile(r"(video|camera|preview|display|frame)", re.IGNORECASE)
CLOCK_RE = re.compile(
    r"(AV_MASTER_CLOCK|master_clock|audio_clock|sample_clock|i2s_clock|clock_master)",
    re.IGNORECASE,
)
PTS_RE = re.compile(r"(pts_(?:us|ms)|timestamp_(?:us|ms)|presentation_time|rtp_timestamp)", re.IGNORECASE)
TICK_AS_MEDIA_TIME_RE = re.compile(
    r"\b(?:[A-Za-z_]\w*\s*(?:->|\.)\s*)?"
    r"(?:pts|timestamp|presentation_time)[A-Za-z0-9_]*\s*=\s*"
    r"(?:xTaskGetTickCount|HAL_GetTick|osKernelGetTickCount)\s*\(",
    re.IGNORECASE,
)
JITTER_RE = re.compile(r"(jitter|rtp|packet|network_stream|ring)", re.IGNORECASE)
CAPACITY_RE = re.compile(r"(CAPACITY|DEPTH|QUEUE_LEN|RING_SIZE|MAX_FRAMES)", re.IGNORECASE)
WATERMARK_RE = re.compile(r"(LOW_WATER|HIGH_WATER|WATERMARK|TARGET_DELAY|TARGET_DEPTH)", re.IGNORECASE)
DRIFT_RE = re.compile(r"(drift|ppm|skew|resample_ratio|clock_error)", re.IGNORECASE)
CLAMP_RE = re.compile(r"(clamp|limit|bounded|MAX_DRIFT|DRIFT_PPM_LIMIT|PPM_LIMIT)", re.IGNORECASE)
HOT_WAIT_RE = re.compile(
    r"\b(?:vTaskDelay|osDelay|k_sleep)\s*\([^;]*(?:drift|pts|sync|diff|delta|wait)",
    re.IGNORECASE | re.DOTALL,
)
FOREVER_WAIT_RE = re.compile(
    r"\b(?:xQueueReceive|xQueueSend|xSemaphoreTake)\s*\([^;]*portMAX_DELAY",
    re.IGNORECASE | re.DOTALL,
)
HOT_FUNC_RE = re.compile(r"(render|playback|sync|jitter|underrun|overrun|frame|pop|push)", re.IGNORECASE)
RECOVERY_FUNC_RE = re.compile(r"(underrun|overrun|jitter).*", re.IGNORECASE)
ALLOC_LOG_RE = re.compile(
    r"\b(?:malloc|calloc|free|pvPortMalloc|vPortFree|heap_caps_malloc|heap_caps_calloc|"
    r"printf|puts|LOG_[A-Z]+|ESP_LOG[IEWD])\s*\("
)
COMPENSATION_RE = re.compile(r"(silence|zero|memset|repeat|hold|freeze|drop|insert|resync)", re.IGNORECASE)
TELEMETRY_RE = re.compile(
    r"(drift_ms|drift_ppm|jitter_depth|jitter_low|jitter_high|underrun_count|overrun_count|"
    r"late_frame|dropped_frame|inserted_silence|resync_count)",
    re.IGNORECASE,
)


def parse_defines(code: str) -> dict[str, int]:
    return {name: int(value) for name, value in DEFINE_RE.findall(code)}


def is_av_clock_file(code: str) -> bool:
    return MEDIA_RE.search(code) is not None


def check_clock_source(path: Path, code: str) -> list[dict[str, str]]:
    has_audio = AUDIO_RE.search(code) is not None
    has_video = VIDEO_RE.search(code) is not None
    has_sync = re.search(r"(av_sync|lip|drift|jitter)", code, re.IGNORECASE) is not None
    issues: list[dict[str, str]] = []
    if (has_audio and has_video and has_sync) and not CLOCK_RE.search(code):
        issues.append(make_issue(path, 1, "C27.1", "P0", "A/V sync 缺少唯一 master clock / audio_clock / sample_clock"))
    tick_match = TICK_AS_MEDIA_TIME_RE.search(code)
    if tick_match and not (CLOCK_RE.search(code) and PTS_RE.search(code)):
        issues.append(make_issue(path, line_at(code, tick_match.start()), "C27.1", "P0", "使用系统 tick 作为媒体时间戳，缺少单调 PTS/audio clock"))
    return issues


def check_jitter_watermarks(path: Path, defines: dict[str, int], code: str) -> list[dict[str, str]]:
    if not JITTER_RE.search(code):
        return []
    names = "\n".join(defines)
    has_capacity = CAPACITY_RE.search(names) is not None
    has_watermarks = WATERMARK_RE.search(names) is not None
    issues: list[dict[str, str]] = []
    if not has_capacity:
        issues.append(make_issue(path, 1, "C27.2", "P0", "jitter buffer 缺少 capacity/depth/ring size 上限"))
    if not has_watermarks:
        issues.append(make_issue(path, 1, "C27.2", "P0", "jitter buffer 缺少 low/high watermark 或 target delay"))
    return issues


def check_drift_clamp(path: Path, defines: dict[str, int], code: str) -> list[dict[str, str]]:
    if not DRIFT_RE.search(code):
        return []
    issues: list[dict[str, str]] = []
    if not CLAMP_RE.search(code):
        issues.append(make_issue(path, 1, "C27.3", "P1", "drift correction 存在但未找到 clamp/limit/ppm 上限"))
    for name, value in defines.items():
        upper = name.upper()
        if ("DRIFT" in upper or "PPM" in upper) and "LIMIT" in upper and abs(value) > 1000:
            issues.append(make_issue(path, 1, "C27.3", "P1", f"{name}={value} 超过建议的 1000ppm 上限"))
    return issues


def check_hot_waits(path: Path, functions: list) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        name = func.name
        body = func.body
        if not HOT_FUNC_RE.search(name):
            continue
        for match in HOT_WAIT_RE.finditer(body):
            issues.append(make_issue(
                path,
                func.line + body[:match.start()].count("\n"),
                "C27.4",
                "P1",
                f"{name} 按 drift/PTS 差值阻塞等待，应改为 drop/repeat/resample/resync",
            ))
        for match in FOREVER_WAIT_RE.finditer(body):
            issues.append(make_issue(
                path,
                func.line + body[:match.start()].count("\n"),
                "C27.4",
                "P1",
                f"{name} 在 jitter/sync 热路径使用 portMAX_DELAY",
            ))
    return issues


def check_recovery_path(path: Path, functions: list, code: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    has_recovery_code = re.search(r"(underrun|overrun)", code, re.IGNORECASE) is not None
    for func in functions:
        name = func.name
        body = func.body
        if not RECOVERY_FUNC_RE.search(name):
            continue
        for match in ALLOC_LOG_RE.finditer(body):
            issues.append(make_issue(
                path,
                func.line + body[:match.start()].count("\n"),
                "C27.5",
                "P1",
                f"{name} underrun/overrun/jitter handler 中出现 {match.group(0).rstrip('(')}",
            ))
    if has_recovery_code and not COMPENSATION_RE.search(code):
        issues.append(make_issue(path, 1, "C27.5", "P1", "underrun/overrun 缺少 silence/repeat/drop/insert/resync 补偿策略"))
    return issues


def check_telemetry(path: Path, code: str) -> list[dict[str, str]]:
    if re.search(r"(av_sync|jitter|drift|underrun|overrun)", code, re.IGNORECASE) and not TELEMETRY_RE.search(code):
        return [make_issue(path, 1, "C27.6", "P2", "A/V clock/jitter 代码缺少 drift/jitter/underrun/drop/resync 遥测")]
    return []


def check_file(path: Path) -> list[dict[str, str]]:
    result = read_file(path)
    if result is None:
        return []
    _lines, text = result

    code = strip_comments(text)
    if not is_av_clock_file(code):
        return []

    defines = parse_defines(code)
    functions = extract_functions(code)
    issues: list[dict[str, str]] = []
    issues.extend(check_clock_source(path, code))
    issues.extend(check_jitter_watermarks(path, defines, code))
    issues.extend(check_drift_clamp(path, defines, code))
    issues.extend(check_hot_waits(path, functions))
    issues.extend(check_recovery_path(path, functions, code))
    issues.extend(check_telemetry(path, code))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C27 A/V clock jitter checker", ("C27",)))
