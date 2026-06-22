#!/usr/bin/env python3
"""
C28 媒体 DMA/cache/零拷贝 buffer 生命周期启发式检查器。

检查项:
  C28.1 — 媒体 DMA buffer 必须对齐且位于 DMA-capable 内存
  C28.2 — DMA RX 后 CPU 读前 invalidate；CPU 写 TX/LCD 前 clean
  C28.3 — 零拷贝/帧池必须有 owner/state/generation/release 生命周期
  C28.4 — Queue 传 buffer index/handle/descriptor，禁止裸 DMA 指针所有权不清
  C28.5 — cache clean/invalidate 范围按 cache line 对齐并覆盖完整 frame
  C28.6 — 保留 cache/buffer/stale/reuse/overrun 遥测

用法:
    python tools/av_dma_buffer_checker.py <file.c> [file2.c ...]
    python tools/av_dma_buffer_checker.py --dir src/
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

MEDIA_DMA_RE = re.compile(
    r"(dma|cache|zero[_-]?copy|dma_buf|frame_pool|buffer_pool|MALLOC_CAP_DMA|DMA_ATTR|"
    r"DMA_ALIGNED|DCache|esp_cache_msync|dma_sync)",
    re.IGNORECASE,
)
DMA_ALLOC_RE = re.compile(
    r"(?P<stmt>[^;\n]*(?:malloc|calloc|pvPortMalloc|heap_caps_malloc|heap_caps_calloc)\s*\([^;]*;)",
    re.IGNORECASE,
)
DMA_ARRAY_RE = re.compile(
    r"^\s*(?P<decl>static\s+(?:[A-Z_]+\s+)*"
    r"(?:uint8_t|int16_t|uint16_t|uint32_t)\s+"
    r"[A-Za-z_]\w*(?:dma|buf|buffer|frame|pool|pcm|camera|lcd)[A-Za-z_0-9]*\s*\[[^;]+;)",
    re.IGNORECASE | re.MULTILINE,
)
DMA_CAPABLE_RE = re.compile(r"(MALLOC_CAP_DMA|DMA_ATTR|DMA_ALIGNED|DMA_CAPABLE|__attribute__\s*\(\(.*aligned)", re.IGNORECASE)
RX_RE = re.compile(r"(rx|receive|capture|camera|i2s.*rx|dma.*(?:done|cplt|complete)|HAL_.*Rx.*Callback)", re.IGNORECASE)
TX_RE = re.compile(r"(tx|transmit|playback|lcd|display|flush|i2s.*tx|dma_start|dma_submit|panel.*draw)", re.IGNORECASE)
CACHE_INVALIDATE_RE = re.compile(r"(InvalidateDCache|cache_?invalidate|MSYNC_FLAG_INVALIDATE|dma_sync_for_cpu)", re.IGNORECASE)
CACHE_CLEAN_RE = re.compile(r"(CleanDCache|cache_?clean|MSYNC_FLAG_CLEAN|MSYNC_FLAG_DIR_C2M|dma_sync_for_device)", re.IGNORECASE)
CACHE_OP_RE = re.compile(r"(InvalidateDCache|CleanDCache|cache_?(?:invalidate|clean)|esp_cache_msync|dma_sync_for_)", re.IGNORECASE)
CACHE_ALIGN_RE = re.compile(r"(CACHE_LINE|ALIGN_DOWN|ALIGN_UP|cache_align|align_down|align_up|DMA_ALIGNED)", re.IGNORECASE)
CACHE_CONTEXT_RE = re.compile(
    r"(cache|DCache|dma_buf|dma_buffer|s_dma_buf|MALLOC_CAP|DMA_ALIGNED|DMA_ATTR|"
    r"frame_pool|buffer_pool|zero[_-]?copy|SCB_)",
    re.IGNORECASE,
)
LIFECYCLE_RE = re.compile(r"(owner|state|refcount|generation|gen|release|free_list|in_use)", re.IGNORECASE)
ZERO_COPY_RE = re.compile(r"(zero[_-]?copy|frame_pool|dma_pool|buffer_pool|pool_count|ring)", re.IGNORECASE)
QUEUE_RAW_PTR_RE = re.compile(
    r"\bxQueue(?:Send|SendToBack|Overwrite)\s*\([^;]*&\s*"
    r"(?:s_|g_)?[A-Za-z_0-9]*(?:dma|buf|buffer|frame|pcm)[A-Za-z_0-9]*",
    re.IGNORECASE | re.DOTALL,
)
TELEMETRY_RE = re.compile(
    r"(cache_(?:clean|invalidate|error)|stale_frame|reuse_before_release|buffer_(?:underrun|overrun)|"
    r"dma_(?:overrun|underrun)|dropped_frame|late_frame)",
    re.IGNORECASE,
)
CALLBACK_RE = re.compile(r"(callback|cplt|done|isr)", re.IGNORECASE)
DMA_START_RE = re.compile(r"\b(?:dma_start|camera_dma_start|lcd_dma_start|i2s_dma_start)\s*\(", re.IGNORECASE)


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


def issue(path: Path, line: int | str, cid: str, severity: str, msg: str) -> dict[str, str]:
    loc = f"{path}:{line}" if isinstance(line, int) else str(path)
    return {"id": cid, "file": loc, "severity": severity, "issue": msg}


def is_media_dma_file(code: str) -> bool:
    return MEDIA_DMA_RE.search(code) is not None


def check_dma_memory(path: Path, code: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    for match in DMA_ALLOC_RE.finditer(code):
        stmt = match.group("stmt")
        lower = stmt.lower()
        mediaish = re.search(r"(dma|camera|lcd|audio|video|frame|pcm|i2s|buf|buffer)", lower)
        if "heap_caps_" in lower:
            if mediaish and "MALLOC_CAP_DMA" not in stmt:
                issues.append(issue(path, line_at(code, match.start()), "C28.1", "P0", "媒体 DMA heap_caps_malloc 缺少 MALLOC_CAP_DMA"))
        elif mediaish:
            issues.append(issue(path, line_at(code, match.start()), "C28.1", "P0", "媒体 DMA buffer 使用普通 malloc/pvPortMalloc，需 DMA-capable pool/section"))

    for match in DMA_ARRAY_RE.finditer(code):
        decl = match.group("decl")
        prefix_start = max(0, match.start() - 80)
        prefix = code[prefix_start:match.start()]
        if not DMA_CAPABLE_RE.search(prefix + decl):
            issues.append(issue(path, line_at(code, match.start()), "C28.1", "P1", "静态媒体 DMA buffer 缺少对齐或 DMA-capable 标注"))

    return issues


def check_cache_direction(path: Path, code: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not CACHE_CONTEXT_RE.search(code):
        return issues

    has_rx = RX_RE.search(code) is not None
    has_tx = TX_RE.search(code) is not None

    if has_rx and not CACHE_INVALIDATE_RE.search(code):
        issues.append(issue(path, 1, "C28.2", "P0", "DMA RX/camera capture 后 CPU 读前缺少 cache invalidate"))
    if has_tx and not CACHE_CLEAN_RE.search(code):
        issues.append(issue(path, 1, "C28.2", "P0", "CPU 写后提交给 DMA TX/LCD 前缺少 cache clean"))
    return issues


def check_lifecycle(path: Path, code: str, functions: list[dict[str, object]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if ZERO_COPY_RE.search(code) and not LIFECYCLE_RE.search(code):
        issues.append(issue(path, 1, "C28.3", "P0", "零拷贝/帧池缺少 owner/state/generation/release 生命周期字段"))

    for func in functions:
        name = str(func["name"])
        body = str(func["body"])
        if CALLBACK_RE.search(name) and DMA_START_RE.search(body) and "release" not in body.lower():
            issues.append(issue(
                path,
                int(func["line"]),
                "C28.3",
                "P0",
                f"{name} 回调内直接重启 DMA，未看到 consumer release/generation 防复用",
            ))
    return issues


def check_queue_payload(path: Path, code: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for match in QUEUE_RAW_PTR_RE.finditer(code):
        stmt = match.group(0)
        if re.search(r"(index|idx|handle|descriptor|desc|id)\b", stmt, re.IGNORECASE):
            continue
        issues.append(issue(path, line_at(code, match.start()), "C28.4", "P1", "Queue 传递裸 DMA/frame 指针，建议传 index/handle/descriptor 并声明所有权"))
    return issues


def check_cache_range_alignment(path: Path, code: str) -> list[dict[str, str]]:
    if CACHE_OP_RE.search(code) and not CACHE_ALIGN_RE.search(code):
        return [issue(path, 1, "C28.5", "P1", "cache clean/invalidate 缺少 cache-line 对齐范围处理")]
    return []


def check_telemetry(path: Path, code: str) -> list[dict[str, str]]:
    if is_media_dma_file(code) and re.search(r"(dma|cache|zero[_-]?copy|camera|lcd|i2s)", code, re.IGNORECASE):
        if not TELEMETRY_RE.search(code):
            return [issue(path, 1, "C28.6", "P2", "媒体 DMA/cache 代码缺少 cache/buffer/stale/reuse/overrun 遥测")]
    return []


def check_file(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    code = strip_comments(text)
    if not is_media_dma_file(code):
        return []

    functions = extract_functions(code)
    issues: list[dict[str, str]] = []
    issues.extend(check_dma_memory(path, code))
    issues.extend(check_cache_direction(path, code))
    issues.extend(check_lifecycle(path, code, functions))
    issues.extend(check_queue_payload(path, code))
    issues.extend(check_cache_range_alignment(path, code))
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
    parser = argparse.ArgumentParser(description="C28 媒体 DMA/cache/零拷贝 buffer 生命周期检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c/.cpp 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    args = parser.parse_args()

    targets = collect_targets(args.files, args.dir)
    if not targets:
        print("[av_dma_buffer_checker] 无文件可检查")
        return 0

    all_issues: list[dict[str, str]] = []
    for path in targets:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[av_dma_buffer_checker] 已检查 {len(targets)} 个文件，未发现 C28 违规")
        return 0

    print(f"[av_dma_buffer_checker] 已检查 {len(targets)} 个文件，发现 {len(all_issues)} 个 C28 告警:\n")
    for item in all_issues:
        print(f"  [{item['severity']}] {item['id']} — {item['file']} — {item['issue']}")

    print(f"\nSummary: {len(all_issues)} C28 media DMA buffer warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
