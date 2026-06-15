#!/usr/bin/env python3
"""
FreeRTOS 任务堆栈深度 (usStackDepth) 估算器。

根据任务描述自动推荐合理的堆栈大小，防止栈溢出。
usStackDepth 单位为字 (word)，在 32 位平台上 1 word = 4 字节。

用法:
    python tools/stack_calculator.py --describe "WSS握手 + mbedTLS + cJSON解析"
    python tools/stack_calculator.py --tasks wss,audio,lvgl,presenter
"""

from __future__ import annotations

import argparse
import re
import sys

# 基础开销 (words, 32-bit)
BASE_STACK_WORDS = 256  # 局部变量、调用帧、中断嵌套余量

# 关键词 → 额外堆栈 (words)
KEYWORD_WEIGHTS: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"mbed\s*tls|tls|ssl|握手", re.I), 768, "mbedTLS 握手/会话"),
    (re.compile(r"wss|websocket|web\s*socket", re.I), 512, "WebSocket 协议栈"),
    (re.compile(r"https?|http", re.I), 384, "HTTP 客户端"),
    (re.compile(r"lwip|socket|tcp|udp", re.I), 256, "LwIP Socket 层"),
    (re.compile(r"cjson|json\s*parse|json\s*解析", re.I), 192, "cJSON 解析树"),
    (re.compile(r"jsmn|流式", re.I), 64, "jsmn 轻量解析"),
    (re.compile(r"lvgl|ui|界面|刷新", re.I), 512, "LVGL 渲染"),
    (re.compile(r"opus|mp3|aac|编解码|codec", re.I), 384, "音频编解码"),
    (re.compile(r"i2s|dma|audio|音频|mic|pdm", re.I), 256, "I2S/DMA 音频"),
    (re.compile(r"mqtt", re.I), 256, "MQTT 客户端"),
    (re.compile(r"ota|固件升级", re.I), 512, "OTA 下载/校验"),
    (re.compile(r"简单|light|minimal|仅", re.I), -128, "轻量任务折扣"),
    (re.compile(r"复杂|full|完整|深度", re.I), 256, "复杂业务加成"),
]

# 预置任务 profile (words)
PRESET_PROFILES: dict[str, int] = {
    "audio": 768,
    "wss": 1536,
    "network": 1024,
    "lvgl": 1536,
    "presenter": 512,
    "model": 384,
    "idle": 128,
}


def estimate_from_description(description: str) -> tuple[int, list[str]]:
    """根据自然语言描述估算堆栈深度 (words)。"""
    total = BASE_STACK_WORDS
    reasons: list[str] = [f"基础开销: {BASE_STACK_WORDS} words"]

    for pattern, weight, label in KEYWORD_WEIGHTS:
        if pattern.search(description):
            total += weight
            sign = "+" if weight >= 0 else ""
            reasons.append(f"{sign}{weight} words — {label}")

    # 安全余量 25%，向上取整到 64 words
    total = int(total * 1.25)
    total = ((total + 63) // 64) * 64

    # 下限 384 words (1536 bytes)，上限 8192 words
    total = max(384, min(total, 8192))
    return total, reasons


def estimate_from_presets(task_names: list[str]) -> list[tuple[str, int]]:
    """根据预置任务名返回推荐值。"""
    results = []
    for name in task_names:
        key = name.strip().lower()
        words = PRESET_PROFILES.get(key, BASE_STACK_WORDS)
        results.append((key, words))
    return results


def words_to_bytes(words: int, bits: int = 32) -> int:
    return words * (bits // 8)


def main() -> int:
    parser = argparse.ArgumentParser(description="FreeRTOS 堆栈深度估算器")
    parser.add_argument(
        "--describe", "-d",
        type=str,
        help="任务自然语言描述，如 'WSS握手 + cJSON解析'",
    )
    parser.add_argument(
        "--tasks", "-t",
        type=str,
        help="逗号分隔的预置任务名: audio,wss,lvgl,presenter,model",
    )
    parser.add_argument(
        "--bits", "-b",
        type=int,
        default=32,
        choices=[16, 32, 64],
        help="平台字长 (默认 32)",
    )
    args = parser.parse_args()

    if not args.describe and not args.tasks:
        parser.print_help()
        return 1

    print("=" * 60)
    print("FreeRTOS usStackDepth 推荐值")
    print("=" * 60)

    if args.describe:
        words, reasons = estimate_from_description(args.describe)
        bytes_val = words_to_bytes(words, args.bits)
        print(f"\n描述: {args.describe}")
        print(f"\n推荐 usStackDepth: {words} words ({bytes_val} bytes @ {args.bits}-bit)")
        print("\n估算明细:")
        for r in reasons:
            print(f"  • {r}")
        print(f"\n代码示例:")
        print(f"  xTaskCreate(task_fn, \"Task\", {words}, NULL, prio, &handle);")
        print(f"\n⚠️  建议开启 configCHECK_FOR_STACK_OVERFLOW 并在开发阶段用 uxTaskGetStackHighWaterMark() 实测。")

    if args.tasks:
        tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
        print(f"\n预置任务 profile:")
        print(f"{'任务':<12} {'words':>8} {'bytes':>10}")
        print("-" * 32)
        for name, words in estimate_from_presets(tasks):
            print(f"{name:<12} {words:>8} {words_to_bytes(words, args.bits):>10}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
