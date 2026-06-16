# Workflow: Bug 诊断 / Crash 日志

**触发：** HardFault、Guru Meditation、死机 dump、栈溢出、WDT、界面 frozen、WSS 握手 fail。

<thinking>
1. 先日志后改代码
2. 提取 PC/LR/Backtrace → addr2line
3. 对照反例与 scene prompt
4. 若用户要求修复：**自主实施模式** — 改代码至编译通过，无需逐步确认
</thinking>

## Step 1 — 日志解读

读取 [crash_log_decode.txt](../prompts/crash_log_decode.txt) + 对应 `platforms/xxx.md` Crash/addr2line 节。

## Step 2 — 症状路由（只加载下表对应 prompt + 反例；输出引用 `C#.#`）

| 症状 | 优先 ID | 只加载 | 反例 / 工具 |
|------|---------|--------|-------------|
| STACK OVERFLOW / WssTask | C4.5, **C7.5** | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) · [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | `stack_calculator.py` |
| Guru Meditation + network/UI | C1.1, C1.5 | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | [bad_lvgl_cross_thread.c](../examples/bad_lvgl_cross_thread.c) |
| HardFault @ Presenter / 随机复现 | C2.1, C2.2 | [memory_ownership.txt](../prompts/memory_ownership.txt) | [bad_queue_stack_pointer.c](../examples/bad_queue_stack_pointer.c) · `queue_ownership_checker.py` |
| 界面 frozen | C1.5, C1.6, C2.7 | [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | — |
| I2S 卡顿 / 爆音 | C4.1–C4.4 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | [bad_isr_blocking.c](../examples/bad_isr_blocking.c) |
| heap 持续下降 | C3.1–C3.5, **C7.2** | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) · [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | `cjson_leak_checker.py` |
| 缩池 / 关模块后异常 | **C7.6** | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| TLS 握手 fail / 反复断线 | C1.5 | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) | [bad_wss_blocking.c](../examples/bad_wss_blocking.c) → [good_wss_reconnect.c](../examples/good_wss_reconnect.c) |
| WDT / task watchdog | **C8.3–C8.6**, C1.5, C4.7 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) · [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | [bad_wss_blocking.c](../examples/bad_wss_blocking.c) |

## Step 3 — 修复与验证（完整版）

**自主实施（默认）：** 按 [core_rules.md](../references/core_rules.md) 自主实施模式修改源码，编译至通过。

```bash
python tools/run_review.py --dir ./src --platform xxx
# 编译 — 见 platforms/xxx.md
```

## Step 4 — 输出

```markdown
## 结论
## 日志提取（PC/LR/Backtrace）
## 定位（addr2line / 反例对照）
## 修复（MVP 合规）
## 验证
```
