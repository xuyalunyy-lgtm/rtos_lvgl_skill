#!/usr/bin/env python3
"""
C26 Audio/Video codec / media format consistency heuristic checker.

Checks:
  C26.1 — audio sample rate / channels / bit depth end-to-end consistency
  C26.2 — frame_ms and frame_samples formula consistency
  C26.3 — video pixel format and stride consistency
  C26.4 — convert/resample/encode/decode hot path must not use malloc/free/printf/LOG_*
  C26.5 — codec handle must not be created/opened/initialized per frame
  C26.6 — codec/format files should retain mismatch/error/size telemetry

Usage:
    python tools/media_format_checker.py <file.c> [file2.c ...]
    python tools/media_format_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")


DEFINE_RE = re.compile(r"^\s*#define\s+([A-Za-z_]\w*)\s+\(?([0-9]+)U?\)?", re.MULTILINE)

MEDIA_KEYWORDS = (
    "audio", "pcm", "i2s", "aec", "asr", "opus", "aac", "codec",
    "video", "camera", "pixel", "rgb", "yuv", "stride", "jpeg", "h264",
)
AUDIO_PREFIX_RE = re.compile(r"(AUDIO|PCM|I2S|AEC|ASR|OPUS|AAC|SPEEX|ENCODER|DECODER|MEDIA)")
RATE_RE = re.compile(r"(?:SAMPLE_RATE|RATE_HZ)")
CHANNEL_RE = re.compile(r"(?:CHANNELS|CHANNEL_COUNT)")
BITS_RE = re.compile(r"(?:BITS_PER_SAMPLE|BIT_DEPTH)")
FRAME_MS_RE = re.compile(r"(?:FRAME_MS|FRAME_DURATION_MS)")
FRAME_SAMPLES_RE = re.compile(r"(?:FRAME_SAMPLES|SAMPLES_PER_FRAME)")
HOT_FUNC_RE = re.compile(r"(?:encode|decode|convert|resample|scale|process).*frame|process.*pcm", re.IGNORECASE)
_alloc_free_apis = lookup.get_all_apis("HEAP_ALLOC", "HEAP_FREE")
_log_apis = lookup.get_all_apis("LOG_WRITE", "PRINTF")
ALLOC_LOG_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(a) for a in _alloc_free_apis + _log_apis) + r")\s*\("
)
CODEC_CREATE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(a) for a in lookup.get_apis("CODEC_OPEN")) + r")\s*\(",
    re.IGNORECASE,
)
TELEMETRY_RE = re.compile(r"(?:format_mismatch|codec_error|last_frame_size|max_encode|max_decode|mismatch_count)")


def parse_defines(code: str) -> dict[str, int]:
    return {name: int(value) for name, value in DEFINE_RE.findall(code)}


def is_media_file(code: str) -> bool:
    lower = code.lower()
    return any(keyword in lower for keyword in MEDIA_KEYWORDS)


def audio_defines(defines: dict[str, int], pattern: re.Pattern[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, value in defines.items():
        upper = name.upper()
        if AUDIO_PREFIX_RE.search(upper) and pattern.search(upper):
            out[name] = value
    return out


def check_audio_format(path: Path, defines: dict[str, int], code: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    converters_present = re.search(r"(resample|sample_rate_convert|channel_mix|downmix|bit_depth_convert)", code, re.IGNORECASE)
    checks = [
        ("sample rate", audio_defines(defines, RATE_RE)),
        ("channels", audio_defines(defines, CHANNEL_RE)),
        ("bit depth", audio_defines(defines, BITS_RE)),
    ]
    for label, values in checks:
        unique = sorted(set(values.values()))
        if len(unique) > 1 and not converters_present:
            joined = ", ".join(f"{name}={value}" for name, value in sorted(values.items()))
            issues.append(make_issue(
                path,
                1,
                "C26.1",
                "P0",
                f"Audio {label} has multiple configurations and no explicit converter found: {joined}",
            ))
    return issues


def check_frame_size(path: Path, defines: dict[str, int]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    rates = audio_defines(defines, RATE_RE)
    frame_ms = audio_defines(defines, FRAME_MS_RE)
    frame_samples = audio_defines(defines, FRAME_SAMPLES_RE)
    channels = audio_defines(defines, CHANNEL_RE)

    if not rates or not frame_ms or not frame_samples:
        return issues

    rate = next(iter(rates.values()))
    ms = next(iter(frame_ms.values()))
    samples_name, samples = next(iter(frame_samples.items()))
    channel_count = 1
    if len(set(channels.values())) == 1:
        channel_count = next(iter(channels.values()))

    expected = rate * ms * channel_count // 1000
    if expected != samples:
        issues.append(make_issue(
            path,
            1,
            "C26.2",
            "P0",
            f"{samples_name}={samples} inconsistent with derived value {expected} from {rate}Hz/{ms}ms/{channel_count}ch",
        ))
    if "OPUS_FRAME_MS" in defines and defines["OPUS_FRAME_MS"] not in {5, 10, 20, 40, 60}:
        issues.append(make_issue(
            path,
            1,
            "C26.2",
            "P0",
            f"OPUS_FRAME_MS={defines['OPUS_FRAME_MS']} not in common valid set {5, 10, 20, 40, 60}ms",
        ))
    return issues


def infer_bpp(defines: dict[str, int], code: str) -> int | None:
    upper = code.upper()
    if "RGB565" in upper or "YUV422" in upper:
        return 2
    if "RGB888" in upper:
        return 3
    if "GRAY8" in upper or "L8" in upper:
        return 1
    if "VIDEO_BYTES_PER_PIXEL" in defines:
        return defines["VIDEO_BYTES_PER_PIXEL"]
    return None


def check_video_stride(path: Path, defines: dict[str, int], code: str) -> list[dict[str, str]]:
    width = (
        defines.get("VIDEO_WIDTH")
        or defines.get("CAMERA_WIDTH")
        or defines.get("LCD_WIDTH")
    )
    stride = (
        defines.get("VIDEO_STRIDE_BYTES")
        or defines.get("CAMERA_STRIDE_BYTES")
        or defines.get("LCD_STRIDE_BYTES")
        or defines.get("STRIDE_BYTES")
    )
    bpp = infer_bpp(defines, code)
    if width and stride and bpp and stride < width * bpp:
        return [make_issue(
            path,
            1,
            "C26.3",
            "P1",
            f"Video stride={stride} is less than width*bpp={width * bpp}, pixel format/stride inconsistent",
        )]
    return []


def check_hot_path(path: Path, functions) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        if not HOT_FUNC_RE.search(func.name):
            continue
        for match in ALLOC_LOG_RE.finditer(func.body):
            issues.append(make_issue(
                path,
                func.line + func.body[:match.start()].count("\n"),
                "C26.4",
                "P1",
                f"{func.name} hot path contains {match.group(0).rstrip('(')}",
            ))
        for match in CODEC_CREATE_RE.finditer(func.body):
            issues.append(make_issue(
                path,
                func.line + func.body[:match.start()].count("\n"),
                "C26.5",
                "P0",
                f"{func.name} creates/initializes codec in per-frame path: {match.group(0).rstrip('(')}",
            ))
    return issues


def check_telemetry(path: Path, code: str) -> list[dict[str, str]]:
    if re.search(r"(codec|opus|aac|jpeg|h264|format)", code, re.IGNORECASE) and not TELEMETRY_RE.search(code):
        return [make_issue(path, 1, "C26.6", "P2", "Media format/codec file missing mismatch/error/last_frame_size telemetry")]
    return []


def check_file(path: Path) -> list[dict[str, str]]:
    result = read_file(path)
    if result is None:
        return []
    _lines, text = result

    code = strip_comments(text)
    if not is_media_file(code):
        return []

    defines = parse_defines(code)
    functions = extract_functions(code)
    issues: list[dict[str, str]] = []
    issues.extend(check_audio_format(path, defines, code))
    issues.extend(check_frame_size(path, defines))
    issues.extend(check_video_stride(path, defines, code))
    issues.extend(check_hot_path(path, functions))
    issues.extend(check_telemetry(path, code))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C26 Audio/Video Codec / Media Format Consistency Checker", ("C26",), {".c", ".cpp", ".h"}))
