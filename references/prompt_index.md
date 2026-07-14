# Prompt Index — 场景 Prompt 索引

> 按需加载。workflow Step 2 指定 1-3 个 prompt 时参考本文件。
> context_router.py 根据 workflow/platform/constraints 自动选择，无需手动全加载。

## 音视频管线（C25-C28）

| Prompt | 典型场景 |
|--------|----------|
| [av_pipeline_sync](../prompts/av_pipeline_sync.txt) | 音画不同步、掉帧、lip-sync |
| [av_codec_format](../prompts/av_codec_format.txt) | sample rate/channels/RGB565/Opus |
| [av_clock_jitter](../prompts/av_clock_jitter.txt) | drift/jitter buffer/clock recovery |
| [av_dma_buffer_lifecycle](../prompts/av_dma_buffer_lifecycle.txt) | DMA buffer/cache/zero-copy/旧帧花屏 |
| [audio_dma_pingpong](../prompts/audio_dma_pingpong.txt) | I2S DMA ping-pong/音频卡顿 |

## 内存安全（C3, C7, C28）

| Prompt | 典型场景 |
|--------|----------|
| [memory_ownership](../prompts/memory_ownership.txt) | 所有权转移/use-after-free/队列传指针 |
| [memory_alloc_optimize](../prompts/memory_alloc_optimize.txt) | 堆持续下降/池缩容/OOM |
| [flash_nvs_safety](../prompts/flash_nvs_safety.txt) | NVS/Flash 写入安全 |

## 并发安全（C1, C4, C8, C15）

| Prompt | 典型场景 |
|--------|----------|
| [lvgl_thread_safety](../prompts/lvgl_thread_safety.txt) | 跨线程 LVGL 操作/Guru Meditation |
| [deadlock_lock_order](../prompts/deadlock_lock_order.txt) | 死锁/锁序/UI 冻结 |
| [freertos_sync_primitives](../prompts/freertos_sync_primitives.txt) | semaphore/mutex/event group 选型 |
| [inter_task_communication](../prompts/inter_task_communication.txt) | queue/stream buffer 通信模式 |

## 启动与生命周期（C8, C33）

| Prompt | 典型场景 |
|--------|----------|
| [boot_wdt_lifecycle](../prompts/boot_wdt_lifecycle.txt) | WDT 超时/init 顺序/portMAX_DELAY |

## 外设管理（C10, C18, C23, C24）

| Prompt | 典型场景 |
|--------|----------|
| [lcd_display_driver](../prompts/lcd_display_driver.txt) | LCD/OLED 驱动/刷新/花屏 |
| [peripheral_driver_safety](../prompts/peripheral_driver_safety.txt) | 外设驱动安全模式 |
| [peripheral_shutdown_safety](../prompts/peripheral_shutdown_safety.txt) | stop/deinit/TTS 打断/共享 handle |
| [voice_asr_uplink](../prompts/voice_asr_uplink.txt) | 语音上行/ASR 空/AEC 异常 |

## 网络与 WSS（C1, C9, C20）

| Prompt | 典型场景 |
|--------|----------|
| [mbedtls_wss_memory](../prompts/mbedtls_wss_memory.txt) | WSS 栈溢出/TLS 握手/重连 |
| [network_resilience](../prompts/network_resilience.txt) | 网络恢复/断线重连策略 |
| [ota_update_safety](../prompts/ota_update_safety.txt) | OTA 升级/回滚/分区安全 |

## 错误处理与日志（C12, C14）

| Prompt | 典型场景 |
|--------|----------|
| [error_handling](../prompts/error_handling.txt) | 未检查返回值/NULL 解引用 |
| [logging_debug](../prompts/logging_debug.txt) | 裸 printf/ISR 日志/脱敏 |
| [crash_log_decode](../prompts/crash_log_decode.txt) | crash dump 解码/addr2line |

## 编码规范与架构

| Prompt | 典型场景 |
|--------|----------|
| [coding_style](../prompts/coding_style.txt) | 函数过长/命名不规范 |
| [software_architecture_design](../prompts/software_architecture_design.txt) | 模块划分/分层架构 |
| [state_machine_patterns](../prompts/state_machine_patterns.txt) | 状态机设计模式 |

## 运行时效率（C29-C44）

| Prompt | 典型场景 |
|--------|----------|
| [module_contract_topology](../prompts/module_contract_topology.txt) | 模块契约/task 拓扑 |
| [timeout_lifecycle_observability](../prompts/timeout_lifecycle_observability.txt) | 超时预算/可观测/生命周期 |
| [hotpath_critical_budget](../prompts/hotpath_critical_budget.txt) | 热路径/关键路径/数据拷贝 |
| [backpressure_recovery_config](../prompts/backpressure_recovery_config.txt) | 背压降级/故障恢复/配置矩阵 |
| [runtime_efficiency_contracts](../prompts/runtime_efficiency_contracts.txt) | 板级资源/锁预算/临界区/传感器集成 |

## RTOS 平台

| Prompt | 典型场景 |
|--------|----------|
| [rtos_thread_bootstrap](../prompts/rtos_thread_bootstrap.txt) | FreeRTOS 线程创建模板 |
| [rtos_bootstrap_zephyr](../prompts/rtos_bootstrap_zephyr.txt) | Zephyr 线程创建模板 |
| [rtos_device_tree_contract](../prompts/rtos_device_tree_contract.txt) | Zephyr devicetree 契约 |
| [rtos_kconfig_contract](../prompts/rtos_kconfig_contract.txt) | Zephyr Kconfig 契约 |

## LVGL 专项

| Prompt | 典型场景 |
|--------|----------|
| [lvgl_v8_v9_diff](../prompts/lvgl_v8_v9_diff.txt) | LVGL v8→v9 迁移差异 |

## 配置与构建

| Prompt | 典型场景 |
|--------|----------|
| [secrets_kconfig](../prompts/secrets_kconfig.txt) | 密钥/Kconfig 安全 |
| [sdk_trim_prune](../prompts/sdk_trim_prune.txt) | SDK 裁剪策略 |
| [test_mode_macro](../prompts/test_mode_macro.txt) | 测试模式宏定义 |

## 会话管理

| Prompt | 典型场景 |
|--------|----------|
| [session_strict_mode](../prompts/session_strict_mode.txt) | 严格模式会话控制 |

## 效率与功耗

| Prompt | 典型场景 |
|--------|----------|
| [timer_management](../prompts/timer_management.txt) | 软件定时器选型/精度 |
| [multi_core_ipc](../prompts/multi_core_ipc.txt) | 多核 IPC 通信 |
| [low_power_management](../prompts/low_power_management.txt) | 低功耗模式/唤醒策略 |

## 使用规则

1. **禁止全加载** — 每次最多加载 1-3 个 prompt
2. **按 workflow 选** — workflow Step 2 指定哪些就加载哪些
3. **按症状选** — debug_crash 的 symptom table 指定哪些就加载哪些
4. **有 C 号时优先微分片** — `references/micro_C*.md` 优先于完整 prompt
