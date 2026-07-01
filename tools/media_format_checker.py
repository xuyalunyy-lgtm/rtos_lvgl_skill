#!/usr/bin/env python3
"""
C26 音视频编解码 / 媒体格式一致性启发式检查器。

检查项:
  C26.1 — audio sample rate / channels / bit depth 端到端一致
  C26.2 — frame_ms 与 frame_samples 公式一致
  C26.3 — video pixel format 与 stride 一致
  C26.4 — convert/resample/encode/decode 热路径禁 malloc/free/printf/LOG_*
  C26.5 — codec handle 禁止每帧 create/open/init
  C26.6 — codec/format 文件建议保留 mismatch/error/size 遥测

用法:
    python tools/media_format_checker.py <file.c> [file2.c ...]
    python tools/media_format_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments


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
ALLOC_LOG_RE = re.compile(
    r"\b(?:malloc|calloc|free|pvPortMalloc|vPortFree|heap_caps_malloc|heap_caps_calloc|"
    r"printf|puts|LOG_[A-Z]+|ESP_LOG[IEWD])\s*\("
)
CODEC_CREATE_RE = re.compile(
    r"\b(?:opus_encoder_create|opus_decoder_create|codec_open|codec_init|jpeg_decoder_init|h264_decoder_init|"
    r"aac_encoder_open|aac_decoder_open)\s*\(",
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
                f"音频 {label} 存在多套配置且未找到显式转换器: {joined}",
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
            f"{samples_name}={samples} 与 {rate}Hz/{ms}ms/{channel_count}ch 推导值 {expected} 不一致",
        ))
    if "OPUS_FRAME_MS" in defines and defines["OPUS_FRAME_MS"] not in {5, 10, 20, 40, 60}:
        issues.append(make_issue(
            path,
            1,
            "C26.2",
            "P0",
            f"OPUS_FRAME_MS={defines['OPUS_FRAME_MS']} 不在 5/10/20/40/60ms 常用合法集合",
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
            f"视频 stride={stride} 小于 width*bpp={width * bpp}，像素格式/stride 不一致",
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
                f"{func.name} 热路径中出现 {match.group(0).rstrip('(')}",
            ))
        for match in CODEC_CREATE_RE.finditer(func.body):
            issues.append(make_issue(
                path,
                func.line + func.body[:match.start()].count("\n"),
                "C26.5",
                "P0",
                f"{func.name} 每帧路径中创建/初始化 codec: {match.group(0).rstrip('(')}",
            ))
    return issues


def check_telemetry(path: Path, code: str) -> list[dict[str, str]]:
    if re.search(r"(codec|opus|aac|jpeg|h264|format)", code, re.IGNORECASE) and not TELEMETRY_RE.search(code):
        return [make_issue(path, 1, "C26.6", "P2", "媒体格式/codec 文件缺少 mismatch/error/last_frame_size 等遥测")]
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
    raise SystemExit(run_checker(check_file, "C26 音视频编解码 / 媒体格式一致性检查器", ("C26",), {".c", ".cpp", ".h"}))
