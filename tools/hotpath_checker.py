#!/usr/bin/env python3
"""
C34 热路径禁区启发式扫描器。

检查项:
  C34.1 — hot path 中禁止 malloc/free/pvPortMalloc/vPortFree
  C34.2 — hot path 中禁止 printf/LOG_* 高频打印
  C34.3 — hot path 中禁止 portMAX_DELAY 无界等待
  C34.4 — hot path 中禁止 cJSON parse / codec create / TLS handshake

Hot path 上下文:
  - ISR / DMA callback / HAL complete callback
  - LVGL flush / timer callback
  - audio/video frame process / encode / decode / render
  - 控制环、采样循环、网络收包回调

用法:
    python tools/hotpath_checker.py <file.c> [file2.c ...]
    python tools/hotpath_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

_ALL_PLATFORMS = ["esp32", "stm32", "jl", "bk", "zephyr"]
_lookup = SdkLookup(_ALL_PLATFORMS)

# ── Hot path 函数定义检测 ──

ISR_FUNC_DEF = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?(?:void|int|BaseType_t)\s+"
    r"(\w*(?:IRQHandler|Callback|_ISR|_Isr|_isr|DMA_|dma_)\w*)\s*\([^;]*\)\s*\{?\s*$"
)

LVGL_FUNC_DEF = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?(?:void|int)\s+"
    r"(\w*(?:flush|lv_flush|lv_timer|anim_cb|draw_cb|event_cb|lv_event)\w*)\s*\([^;]*\)\s*\{?\s*$"
)

AV_FUNC_DEF = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?(?:void|int|BaseType_t)\s+"
    r"(\w*(?:frame_cb|audio_cb|video_cb|decode_cb|encode_cb|render_cb|capture_cb|playback_cb)\w*)\s*\([^;]*\)\s*\{?\s*$"
)

NET_FUNC_DEF = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?(?:void|int)\s+"
    r"(\w*(?:recv_cb|rx_cb|data_cb|message_cb|on_data|on_message)\w*)\s*\([^;]*\)\s*\{?\s*$"
)

HOTPATH_FUNC_PATTERNS = [ISR_FUNC_DEF, LVGL_FUNC_DEF, AV_FUNC_DEF, NET_FUNC_DEF]
ISR_ATTR = re.compile(r"__attribute__\s*\(\s*\(\s*interrupt")

# ── 禁止操作模式 ──

HEAP_ALLOC_APIS = _lookup.get_apis("HEAP_ALLOC")
MALLOC_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(a) for a in HEAP_ALLOC_APIS) + r")\s*\("
)

PRINTF_APIS = _lookup.get_apis("PRINTF")
PRINTF_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(a) for a in PRINTF_APIS) + r")\s*\("
)
LOG_PATTERN = re.compile(r"\b(?:ESP_LOG[VDIWEF]|LOG_[VDIWEF]|printf|puts|fprintf)\s*\(")

FOREVER_PATTERN = re.compile(r"\b(?:portMAX_DELAY|WAIT_FOREVER|0xFFFFFFFF|0xffffffff)\b")

HEAVY_OPS = re.compile(
    r"\b(?:cJSON_Parse|cJSON_CreateObject|cJSON_CreateArray|"
    r"mbedtls_ssl_handshake|tls_handshake|"
    r"codec_create|codec_open|avcodec_open)\s*\("
)


def _strip_comments(line: str) -> str:
    in_string = False
    in_char = False
    i = 0
    result = []
    while i < len(line):
        c = line[i]
        if in_string:
            result.append(c)
            if c == '"' and (i == 0 or line[i - 1] != '\\'):
                in_string = False
        elif in_char:
            result.append(c)
            if c == "'" and (i == 0 or line[i - 1] != '\\'):
                in_char = False
        elif c == '"' and not in_char:
            in_string = True
            result.append(c)
        elif c == "'" and not in_string:
            in_char = True
            result.append(c)
        elif c == '/' and i + 1 < len(line) and line[i + 1] == '/':
            break
        elif c == '/' and i + 1 < len(line) and line[i + 1] == '*':
            end = line.find('*/', i + 2)
            if end >= 0:
                i = end + 2
                continue
            else:
                break
        else:
            result.append(c)
        i += 1
    return ''.join(result)


def is_hotpath_function_start(line: str) -> tuple[bool, str]:
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("/*"):
        return False, ""
    code_part = _strip_comments(line).strip()
    if not code_part:
        return False, ""
    if ISR_ATTR.search(code_part):
        return True, "ISR"
    if ISR_FUNC_DEF.match(code_part):
        return True, "ISR/callback"
    if LVGL_FUNC_DEF.match(code_part):
        return True, "LVGL callback"
    if AV_FUNC_DEF.match(code_part):
        return True, "A/V callback"
    if NET_FUNC_DEF.match(code_part):
        return True, "network callback"
    return False, ""


def find_function_name(lines: list[str], line_idx: int) -> str:
    pat = re.compile(r"(?:static\s+)?(?:void|int|BaseType_t)\s+(\w+)\s*\(")
    for i in range(line_idx, max(line_idx - 30, -1), -1):
        m = pat.search(lines[i])
        if m:
            return m.group(1)
    return "unknown"


def extract_function_body(lines: list[str], start: int) -> tuple[str, int, int]:
    func_name = find_function_name(lines, start)
    brace = 0
    body_start = start
    for i in range(start, len(lines)):
        code = _strip_comments(lines[i])
        brace += code.count("{")
        if brace > 0:
            body_start = i
            break
    if brace == 0:
        return func_name, start, min(start + 40, len(lines))
    for i in range(body_start, len(lines)):
        code = _strip_comments(lines[i])
        brace += code.count("{") - code.count("}")
        if brace <= 0 and i > body_start:
            return func_name, body_start, i + 1
    return func_name, body_start, len(lines)


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    lines, text = result
    issues: list[dict] = []

    i = 0
    while i < len(lines):
        is_hot, ctx_type = is_hotpath_function_start(lines[i])
        if is_hot:
            func_name, body_start, body_end = extract_function_body(lines, i)
            body_lines = lines[body_start:body_end]

            for j, bline in enumerate(body_lines):
                code = _strip_comments(bline).strip()
                if not code or code.startswith("//") or code.startswith("/*"):
                    continue

                # C34.1 — 动态分配
                if MALLOC_PATTERN.search(code):
                    if "FromISR" not in code:
                        issues.append(make_issue(
                            path, body_start + j + 1, "C34.1", "P0",
                            f"[{func_name}/{ctx_type}] hotpath malloc/free: {code[:80]}",
                        ))

                # C34.2 — 重日志
                if PRINTF_PATTERN.search(code) or LOG_PATTERN.search(code):
                    issues.append(make_issue(
                        path, body_start + j + 1, "C34.2", "P1",
                        f"[{func_name}/{ctx_type}] hotpath printf/log: {code[:80]}",
                    ))

                # C34.3 — 无界等待
                if FOREVER_PATTERN.search(code):
                    issues.append(make_issue(
                        path, body_start + j + 1, "C34.3", "P0",
                        f"[{func_name}/{ctx_type}] hotpath portMAX_DELAY: {code[:80]}",
                    ))

                # C34.4 — 重型操作
                if HEAVY_OPS.search(code):
                    issues.append(make_issue(
                        path, body_start + j + 1, "C34.4", "P0",
                        f"[{func_name}/{ctx_type}] hotpath heavy op: {code[:80]}",
                    ))
        i += 1

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C34 hotpath review", ("C34",)))
