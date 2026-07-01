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
| Guru Meditation + network/UI | C1.1, C1.5 | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | 完整版 `examples/bad_lvgl_cross_thread.c` |
| HardFault @ Presenter / 随机复现 | C2.1, C2.2 | [memory_ownership.txt](../prompts/memory_ownership.txt) | 完整版 `examples/bad_queue_stack_pointer.c` · `queue_ownership_checker.py` |
| 界面 frozen | C1.5, C1.6, C2.7 | [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | — |
| I2S 卡顿 / 爆音 | C4.1–C4.4 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | 完整版 `examples/bad_isr_blocking.c` |
| 音画不同步 / lip-sync drift / 画面慢半拍 | C25.1–C25.3, C25.6, C27.1, C27.3 | [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) · [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) | 完整版 `examples/bad_av_pipeline_blocking.c` · 完整版 `examples/bad_av_clock_jitter.c` · `av_pipeline_checker.py` · `av_clock_jitter_checker.py` |
| camera preview 卡顿 / 掉帧 / UI 刷新拖慢音频 | C25.3–C25.5, C23.3 | [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) · [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) | 完整版 `examples/bad_av_pipeline_blocking.c` · `av_pipeline_checker.py` |
| ASR 空 / AEC 异常 / 音频变速 / Opus 编码失败 | C26.1, C26.2, C26.5 | [av_codec_format.txt](../prompts/av_codec_format.txt) | 完整版 `examples/bad_media_format_mismatch.c` · `media_format_checker.py` |
| RGB565 花屏 / 行错位 / 视频画面倾斜 | C26.3, C23.6 | [av_codec_format.txt](../prompts/av_codec_format.txt) · [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) | 完整版 `examples/bad_media_format_mismatch.c` · `media_format_checker.py` |
| DMA 后读到旧 PCM / Camera 旧帧 / LCD flush 局部错乱 | C28.1–C28.5, C4.8, C23.4 | [av_dma_buffer_lifecycle.txt](../prompts/av_dma_buffer_lifecycle.txt) · [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | 完整版 `examples/bad_av_dma_buffer_lifecycle.c` · `av_dma_buffer_checker.py` |
| 网络抖动后爆音 / 音频 underrun / 恢复慢 | C27.2, C27.4, C27.5, C20.1 | [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) · [network_resilience.txt](../prompts/network_resilience.txt) | 完整版 `examples/bad_av_clock_jitter.c` · `av_clock_jitter_checker.py` |
| heap 持续下降 | C3.1–C3.5, **C7.2** | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) · [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | `cjson_leak_checker.py` |
| 缩池 / 关模块后异常 | **C7.6** | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| TLS 握手 fail / 反复断线 | C1.5 | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) | 完整版 `examples/bad_wss_blocking.c` → 完整版 `examples/good_wss_reconnect.c` |
| WSS 断线后异步 reconnect HardFault / use-after-free | C2.3, C1.6 | [crash_log_decode.txt](../prompts/crash_log_decode.txt) · [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) | 平台专档 WSS 生命周期节（如 BK `vc_start`） |
| Assert `prvNotifyQueueSetContainer` | C2.3 | [crash_log_decode.txt](../prompts/crash_log_decode.txt) | 先排除堆损坏 / WSS 竞态；BK 见 `platforms/bk.md` |
| WDT / task watchdog | **C8.3–C8.6**, C1.5, C4.7 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) · [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | 完整版 `examples/bad_wss_blocking.c` |
| 假死但无 crash / stop 卡住 | **C31.1–C31.4**, C30.4 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | `blocking_wait_checker.py` |
| 现场无法复盘 / 日志没有状态和错误码 | **C32.1–C32.5**, C14.7, C14.8 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) · [logging_management_constraints.md](../references/logging_management_constraints.md) | — |
| stop/start 多次后崩溃或泄漏 | **C33.1–C33.5**, C12.4, C24.1 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) · [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) | — |
| 周期性延迟尖峰 / callback 卡顿 | **C34.1–C34.5**, C4.3, C25.4 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | media checkers + 人工 |
| 启动/联网/音视频/UI 某阶段偶发超时 | **C35.1–C35.5**, C31, C32 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 阶段 max time / timeout counter |
| 内存抖动、旧帧、DMA 数据错 | **C36.1–C36.5**, C2, C28, C42 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | media/DMA checkers + 人工 |
| 偶发死锁、WDT、网络差时 UI/音视频抖动 | **C43.1–C43.5**, C15, C31, C34, C37 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | `lock_budget_checker.py` + 人工 |
| 队列满后延迟堆积或系统假死 | **C37.1–C37.5**, C30, C31 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | `blocking_wait_checker.py` + 水位计数 |
| 断网/外设异常后只能重启恢复 | **C38.1–C38.5**, C20, C24, C33 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | health counter / retry counter |
| 某配置或某板才崩溃 | **C39.1–C39.5**, C42 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | profile/config matrix |
| 无法复现用户现场问题 | **C40.1–C40.5**, C14, C41 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | build/flash/log/decode 命令 |
| 录音失效 / ASR 空 / 「没听清」 | **C10.1–C10.5** | [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) | 完整版 `examples/good_voice_prompt_uplink.c` |
| 唤醒叮后第二轮麦幅骤降 | **C10.1, C10.2** | [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) | — |
| AI 键打断 TTS 后不上传 / speaker stop 后 MIC 失效 | **C10.1, C10.5, C24.4** | [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) · [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) | 完整版 `examples/good_voice_prompt_uplink.c` |

## Step 3 — 修复与验证（Lite）

按 [core_rules.md](../references/core_rules.md) 自主实施模式修改源码，编译至通过。
执行 [lite_manual_checklist.md](../references/lite_manual_checklist.md) 完成人工审查。

## Step 4 — 输出

```markdown
## 结论
## 日志提取（PC/LR/Backtrace）
## 定位（addr2line / 反例对照）
## 修复（MVP 合规）
## 验证
```
