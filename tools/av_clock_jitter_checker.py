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

用法:
    python tools/av_clock_jitter_checker.py <file.c> [file2.c ...]
    python tools/av_clock_jitter_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
DEFINE_RE = re.compile(r"^\s*#define\s+([A-Za-z_]\w*)\s+\(?(-?[0-9]+)U?\)?", re.MULTILINE)
FUNC_DEF_RE = re.compile(
    r"(?:^|[\n;])\s*"
    r"(?:static\s+)?(?:inline\s+)?"
    r"(?:[A-Za-z_][\w\s\*]*\s+)+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.MULTILINE,
)

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


def strip_comments(text: str) -> str:
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


def parse_defines(code: str) -> dict[str, int]:
    return {name: int(value) for name, value in DEFINE_RE.findall(code)}


def issue(path: Path, line: int | str, cid: str, severity: str, msg: str) -> dict[str, str]:
    loc = f"{path}:{line}" if isinstance(line, int) else str(path)
    return {"id": cid, "file": loc, "severity": severity, "issue": msg}


def is_av_clock_file(code: str) -> bool:
    return MEDIA_RE.search(code) is not None


def check_clock_source(path: Path, code: str) -> list[dict[str, str]]:
    has_audio = AUDIO_RE.search(code) is not None
    has_video = VIDEO_RE.search(code) is not None
    has_sync = re.search(r"(av_sync|lip|drift|jitter)", code, re.IGNORECASE) is not None
    issues: list[dict[str, str]] = []
    if (has_audio and has_video and has_sync) and not CLOCK_RE.search(code):
        issues.append(issue(path, 1, "C27.1", "P0", "A/V sync 缺少唯一 master clock / audio_clock / sample_clock"))
    tick_match = TICK_AS_MEDIA_TIME_RE.search(code)
    if tick_match and not (CLOCK_RE.search(code) and PTS_RE.search(code)):
        issues.append(issue(path, line_at(code, tick_match.start()), "C27.1", "P0", "使用系统 tick 作为媒体时间戳，缺少单调 PTS/audio clock"))
    return issues


def check_jitter_watermarks(path: Path, defines: dict[str, int], code: str) -> list[dict[str, str]]:
    if not JITTER_RE.search(code):
        return []
    names = "\n".join(defines)
    has_capacity = CAPACITY_RE.search(names) is not None
    has_watermarks = WATERMARK_RE.search(names) is not None
    issues: list[dict[str, str]] = []
    if not has_capacity:
        issues.append(issue(path, 1, "C27.2", "P0", "jitter buffer 缺少 capacity/depth/ring size 上限"))
    if not has_watermarks:
        issues.append(issue(path, 1, "C27.2", "P0", "jitter buffer 缺少 low/high watermark 或 target delay"))
    return issues


def check_drift_clamp(path: Path, defines: dict[str, int], code: str) -> list[dict[str, str]]:
    if not DRIFT_RE.search(code):
        return []
    issues: list[dict[str, str]] = []
    if not CLAMP_RE.search(code):
        issues.append(issue(path, 1, "C27.3", "P1", "drift correction 存在但未找到 clamp/limit/ppm 上限"))
    for name, value in defines.items():
        upper = name.upper()
        if ("DRIFT" in upper or "PPM" in upper) and "LIMIT" in upper and abs(value) > 1000:
            issues.append(issue(path, 1, "C27.3", "P1", f"{name}={value} 超过建议的 1000ppm 上限"))
    return issues


def check_hot_waits(path: Path, functions: list[dict[str, object]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        name = str(func["name"])
        body = str(func["body"])
        if not HOT_FUNC_RE.search(name):
            continue
        for match in HOT_WAIT_RE.finditer(body):
            issues.append(issue(
                path,
                int(func["line"]) + body[:match.start()].count("\n"),
                "C27.4",
                "P1",
                f"{name} 按 drift/PTS 差值阻塞等待，应改为 drop/repeat/resample/resync",
            ))
        for match in FOREVER_WAIT_RE.finditer(body):
            issues.append(issue(
                path,
                int(func["line"]) + body[:match.start()].count("\n"),
                "C27.4",
                "P1",
                f"{name} 在 jitter/sync 热路径使用 portMAX_DELAY",
            ))
    return issues


def check_recovery_path(path: Path, functions: list[dict[str, object]], code: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    has_recovery_code = re.search(r"(underrun|overrun)", code, re.IGNORECASE) is not None
    for func in functions:
        name = str(func["name"])
        body = str(func["body"])
        if not RECOVERY_FUNC_RE.search(name):
            continue
        for match in ALLOC_LOG_RE.finditer(body):
            issues.append(issue(
                path,
                int(func["line"]) + body[:match.start()].count("\n"),
                "C27.5",
                "P1",
                f"{name} underrun/overrun/jitter handler 中出现 {match.group(0).rstrip('(')}",
            ))
    if has_recovery_code and not COMPENSATION_RE.search(code):
        issues.append(issue(path, 1, "C27.5", "P1", "underrun/overrun 缺少 silence/repeat/drop/insert/resync 补偿策略"))
    return issues


def check_telemetry(path: Path, code: str) -> list[dict[str, str]]:
    if re.search(r"(av_sync|jitter|drift|underrun|overrun)", code, re.IGNORECASE) and not TELEMETRY_RE.search(code):
        return [issue(path, 1, "C27.6", "P2", "A/V clock/jitter 代码缺少 drift/jitter/underrun/drop/resync 遥测")]
    return []


def check_file(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

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
    parser = argparse.ArgumentParser(description="C27 音视频时钟漂移 / Jitter Buffer 检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c/.cpp 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    args = parser.parse_args()

    targets = collect_targets(args.files, args.dir)
    if not targets:
        print("[av_clock_jitter_checker] 无文件可检查")
        return 0

    all_issues: list[dict[str, str]] = []
    for path in targets:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[av_clock_jitter_checker] 已检查 {len(targets)} 个文件，未发现 C27 违规")
        return 0

    print(f"[av_clock_jitter_checker] 已检查 {len(targets)} 个文件，发现 {len(all_issues)} 个 C27 告警:\n")
    for item in all_issues:
        print(f"  [{item['severity']}] {item['id']} — {item['file']} — {item['issue']}")

    print(f"\nSummary: {len(all_issues)} C27 A/V clock-jitter warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
