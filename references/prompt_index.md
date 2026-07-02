# Prompt Index — 场景 Prompt 索引

> 按需加载。workflow Step 2 指定 1-3 个 prompt 时参考本文件。

## 软件架构
- [software_architecture_design](../prompts/software_architecture_design.txt)

## LVGL/线程安全
- [lvgl_thread_safety](../prompts/lvgl_thread_safety.txt)

## 所有权/IPC
- [memory_ownership](../prompts/memory_ownership.txt)
- [inter_task_communication](../prompts/inter_task_communication.txt)

## JSON/错误/风格/日志
- [cjson_safe_parse](../prompts/cjson_safe_parse.txt)
- [error_handling](../prompts/error_handling.txt)
- [coding_style](../prompts/coding_style.txt)
- [logging_debug](../prompts/logging_debug.txt)

## ISR/DMA/音视频
- [audio_dma_pingpong](../prompts/audio_dma_pingpong.txt)
- [lcd_display_driver](../prompts/lcd_display_driver.txt)
- [voice_asr_uplink](../prompts/voice_asr_uplink.txt)
- [av_pipeline_sync](../prompts/av_pipeline_sync.txt)
- [av_codec_format](../prompts/av_codec_format.txt)
- [av_clock_jitter](../prompts/av_clock_jitter.txt)
- [av_dma_buffer_lifecycle](../prompts/av_dma_buffer_lifecycle.txt)

## 网络/WSS 现场
- [mbedtls_wss_memory](../prompts/mbedtls_wss_memory.txt)
- [peripheral_shutdown_safety](../prompts/peripheral_shutdown_safety.txt)
- [network_resilience](../prompts/network_resilience.txt)

## 启动/配置/安全
- [boot_wdt_lifecycle](../prompts/boot_wdt_lifecycle.txt)
- [secrets_kconfig](../prompts/secrets_kconfig.txt)
- [flash_nvs_safety](../prompts/flash_nvs_safety.txt)
- [ota_update_safety](../prompts/ota_update_safety.txt)

## 运行时模式
- [state_machine_patterns](../prompts/state_machine_patterns.txt)
- [timer_management](../prompts/timer_management.txt)
- [multi_core_ipc](../prompts/multi_core_ipc.txt)

## 鲁棒性
- [memory_alloc_optimize](../prompts/memory_alloc_optimize.txt)
- [low_power_management](../prompts/low_power_management.txt)
- [peripheral_driver_safety](../prompts/peripheral_driver_safety.txt)

## 效率契约
- [runtime_efficiency_contracts](../prompts/runtime_efficiency_contracts.txt)

## Zephyr RTOS
- [device_tree_contract](../prompts/rtos_device_tree_contract.txt)
- [kconfig_contract](../prompts/rtos_kconfig_contract.txt)
- [thread_bootstrap](../prompts/rtos_thread_bootstrap.txt)
- [rtos_bootstrap_zephyr](../prompts/rtos_bootstrap_zephyr.txt)
