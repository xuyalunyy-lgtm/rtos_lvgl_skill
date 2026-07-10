# Workflow: Bug Diagnosis / Crash Log

**Trigger:** HardFault, Guru Meditation, crash dump, stack overflow, WDT, UI frozen, WSS handshake failure.

<thinking>
1. Log first, then code changes
2. Extract PC/LR/Backtrace → addr2line
3. Cross-reference with negative examples and scene prompts
4. If user requests fix: **Autonomous Implementation Mode** — modify code until compilation passes, no step-by-step confirmation needed
</thinking>

## Step 1 — Log Interpretation

Read [crash_log_decode.txt](../prompts/crash_log_decode.txt) + corresponding `platforms/xxx.md` Crash/addr2line section.

## Step 2 — Symptom Routing (load only the corresponding prompt + negative examples from the table below; output references `C#.#`)

| Symptom | Priority ID | Load Only | Negative Examples / Tools |
|------|---------|--------|-------------|
| STACK OVERFLOW / WssTask | C4.5, **C7.5** | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) · [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | `stack_calculator.py` |
| Guru Meditation + network/UI | C1.1, C1.5 | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | [bad_lvgl_cross_thread.c](../examples/bad_lvgl_cross_thread.c) |
| HardFault @ Presenter / Random Reproduction | C2.1, C2.2 | [memory_ownership.txt](../prompts/memory_ownership.txt) | [bad_queue_stack_pointer.c](../examples/bad_queue_stack_pointer.c) · `queue_ownership_checker.py` |
| UI Frozen | C1.5, C1.6, C2.7 | [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | — |
| I2S Stutter / Audio Popping | C4.1–C4.4 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | [bad_isr_blocking.c](../examples/bad_isr_blocking.c) |
| A/V Desync / Lip-sync Drift / Video Lagging | C25.1–C25.3, C25.6, C27.1, C27.3 | [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) · [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) | [bad_av_pipeline_blocking.c](../examples/bad_av_pipeline_blocking.c) · [bad_av_clock_jitter.c](../examples/bad_av_clock_jitter.c) · `av_pipeline_checker.py` · `av_clock_jitter_checker.py` |
| Camera Preview Stutter / Frame Drop / UI Slows Audio | C25.3–C25.5, C23.3 | [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) · [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) | [bad_av_pipeline_blocking.c](../examples/bad_av_pipeline_blocking.c) · `av_pipeline_checker.py` |
| ASR Empty / AEC Abnormal / Audio Speed Change / Opus Encode Failure | C26.1, C26.2, C26.5 | [av_codec_format.txt](../prompts/av_codec_format.txt) | [bad_media_format_mismatch.c](../examples/bad_media_format_mismatch.c) · `media_format_checker.py` |
| RGB565 Corruption / Row Misalignment / Video Tilt | C26.3, C23.6 | [av_codec_format.txt](../prompts/av_codec_format.txt) · [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) | [bad_media_format_mismatch.c](../examples/bad_media_format_mismatch.c) · `media_format_checker.py` |
| Stale PCM after DMA / Stale Camera Frame / LCD Flush Corruption | C28.1–C28.5, C4.8, C23.4 | [av_dma_buffer_lifecycle.txt](../prompts/av_dma_buffer_lifecycle.txt) · [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | [bad_av_dma_buffer_lifecycle.c](../examples/bad_av_dma_buffer_lifecycle.c) · `av_dma_buffer_checker.py` |
| Audio Popping after Jitter / Audio Underrun / Slow Recovery | C27.2, C27.4, C27.5, C20.1 | [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) · [network_resilience.txt](../prompts/network_resilience.txt) | [bad_av_clock_jitter.c](../examples/bad_av_clock_jitter.c) · `av_clock_jitter_checker.py` |
| Heap Continuously Decreasing | C3.1–C3.5, **C7.2** | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) · [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | `cjson_leak_checker.py` |
| Abnormality after Pool Shrink / Module Disable | **C7.6** | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| TLS Handshake Failure / Repeated Disconnections | C1.5 | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) | [bad_wss_blocking.c](../examples/bad_wss_blocking.c) → [good_wss_reconnect.c](../examples/good_wss_reconnect.c) |
| Async Reconnect HardFault after WSS Disconnect / Use-after-free | C2.3, C1.6 | [crash_log_decode.txt](../prompts/crash_log_decode.txt) · [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) | Platform doc WSS lifecycle section (e.g. BK `vc_start`) |
| Assert `prvNotifyQueueSetContainer` | C2.3 | [crash_log_decode.txt](../prompts/crash_log_decode.txt) | Rule out heap corruption / WSS race first; BK see `platforms/bk.md` |
| WDT / Task Watchdog | **C8.3–C8.6**, C1.5, C4.7 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) · [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | [bad_wss_blocking.c](../examples/bad_wss_blocking.c) |
| Hang without Crash / Stop Stuck | **C31.1–C31.4**, C30.4 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | `blocking_wait_checker.py` |
| Cannot Replay Field Issue / Logs Missing State and Error Codes | **C32.1–C32.5**, C14.7, C14.8 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) · [logging_management_constraints.md](../references/logging_management_constraints.md) | — |
| Crash or Leak after Multiple Stop/Start | **C33.1–C33.5**, C12.4, C24.1 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) · [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) | — |
| Periodic Latency Spikes / Callback Stutter | **C34.1–C34.5**, C4.3, C25.4 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | media checkers + manual |
| Intermittent Timeout at Boot/Network/Audio/Video/UI Stage | **C35.1–C35.5**, C31, C32 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | stage max time / timeout counter |
| Memory Jitter, Stale Frames, DMA Data Error | **C36.1–C36.5**, C2, C28, C42 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | media/DMA checkers + manual |
| Intermittent Deadlock, WDT, UI/Audio/Video Jitter under Poor Network | **C43.1–C43.5**, C15, C31, C34, C37 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | `lock_budget_checker.py` + manual |
| Audio Popping, Video Frame Drop, Periodic ISR Latency Spikes | **C44.1–C44.5**, C4, C34, C35 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | `critical_section_checker.py` + manual |
| Sensor Drift, I2C/SPI Hang, Sampling Timeline Corruption | **C45.1–C45.5**, C18, C31, C32, C34, C42 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | `sensor_integration_checker.py` + manual |
| Queue Full Causes Latency Buildup or System Hang | **C37.1–C37.5**, C30, C31 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | `blocking_wait_checker.py` + watermark counter |
| Only Reboot Recovers after Network/Peripheral Failure | **C38.1–C38.5**, C20, C24, C33 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | health counter / retry counter |
| Crash Only on Specific Config or Board | **C39.1–C39.5**, C42 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | profile/config matrix |
| Cannot Reproduce User Field Issue | **C40.1–C40.5**, C14, C41 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | build/flash/log/decode commands |
| Recording Failure / ASR Empty / "Didn't Catch That" | **C10.1–C10.5** | [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) | [good_voice_prompt_uplink.c](../examples/good_voice_prompt_uplink.c) |
| Second-round Mic Amplitude Drop after Wake Chime | **C10.1, C10.2** | [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) | — |
| No Upload after AI Key Interrupts TTS / MIC Failure after Speaker Stop | **C10.1, C10.5, C24.4** | [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) · [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) | [good_voice_prompt_uplink.c](../examples/good_voice_prompt_uplink.c) |

## Step 3 — Fix and Verify (Full Version)

**Autonomous Implementation (Default):** Modify source code per [core_rules.md](../references/core_rules.md) autonomous implementation mode, compile until passing.

```bash
python tools/run_review.py --dir ./src --platform xxx
# Compile — see platforms/xxx.md
```

## Step 4 — Output

```markdown
## Conclusion
## Log Extraction (PC/LR/Backtrace)
## Localization (addr2line / Negative Example Cross-reference)
## Fix (MVP Compliance)
## Verification
```
