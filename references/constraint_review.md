# 铁律约束分片：代码审查与通用规范（Review）

本文件包含 LVGL 线程安全、Queue 所有权、cJSON 防泄漏、ISR/DMA、测试宏、SDK 裁剪、编码规范、错误处理、状态机、日志规范、任务优先级、定时器管理等约束，以及严重度定义、症状快查表、约束冲突权衡矩阵。

> 对应约束 ID：C1–C6, C11–C16
> 其他分片：[constraint_memory.md](constraint_memory.md) | [constraint_rtos.md](constraint_rtos.md) | [constraint_platform.md](constraint_platform.md) | [constraint_media.md](constraint_media.md) | [constraint_ota.md](constraint_ota.md) | [constraint_recover.md](constraint_recover.md) | [constraint_bluetooth_protocol.md](constraint_bluetooth_protocol.md)

---

## 严重度定义

| 级别 | 含义 | 处理 |
|------|------|------|
| P0 | 必崩 / 必泄漏 / 必死锁 | 阻塞合并，须附修复 diff 或范例引用 |
| P1 | 高概率量产问题 | 本迭代必须修复或登记风险 |
| P2 | 可维护性 / 可测试性 | 建议修复，可排期 |

---

## C1 — LVGL 线程安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C1.1 | Model / 网络 / 音频 / Presenter **禁止**直接调用 `lv_obj_*`[OBJ_CREATE/OBJ_SET]、`lv_label_*`[OBJ_CREATE/OBJ_SET]、`lv_bar_*` 等 UI API | P0 | `lvgl_thread_checker.py` | `good_presenter_consumer.c` `view_post_set_text` | `bad_lvgl_cross_thread.c` |
| C1.2 | UI 修改**仅**在运行 `lv_timer_handler()` [TIMER_HANDLER] 的 LVGL 任务，或 `lv_async_call` [ASYNC_CALL] 回调内 | P0 | 人工 + checker | `good_mvp_pattern.c` | — |
| C1.3 | `lv_async_call` [ASYNC_CALL] 的 `user_data` 须堆分配，**仅在回调内** `vPortFree` [HEAP_FREE]；投递后调用方不得再读写 | P0 | 人工 | `good_mvp_pattern.c` | — |
| C1.4 | 互斥锁方案：`xSemaphoreTake` [SEM_TAKE] **必须**带超时并检查返回值；禁止 `portMAX_DELAY` [TIMEOUT_FOREVER] | P1 | 人工 | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | — |
| C1.5 | 持 `g_lvgl_mutex` 期间禁止 `vTaskDelay` [TASK_DELAY]、`xQueueReceive(..., portMAX_DELAY)` [QUEUE_RECV/TIMEOUT_FOREVER]、阻塞网络 IO | P0 | 人工 + [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | — | `bad_wss_blocking.c`（持锁 recv） |
| C1.6 | 锁顺序：若同时需要网络锁与 LVGL 锁，**先网络后 LVGL**（L2→L3） | P1 | 人工 | [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | — |
| C1.7 | 高频 UI 刷新（波形/进度）须节流，避免 `lv_async_call` 队列撑爆 | P2 | 人工 | — | — |

---

## C2 — Queue payload 所有权

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C2.1 | Queue **禁止**传递 `cJSON *` 或含 `cJSON *` 字段的 struct | P0 | `queue_ownership_checker.py` | `good_wss_json_parse.c` | `bad_queue_stack_pointer.c` |
| C2.2 | Queue **禁止**传递栈上 buffer 指针（`&local_buf`、栈数组地址） | P0 | 同上 | `good_wss_json_parse.c` heap payload | `bad_queue_stack_pointer.c` |
| C2.3 | 堆 payload：Model `pvPortMalloc` [HEAP_ALLOC] → Presenter 消费后 `vPortFree` [HEAP_FREE]；**禁止**双重 free | P0 | 同上 + 人工 | `good_presenter_consumer.c` | — |
| C2.4 | `xQueueSend` [QUEUE_SEND] 失败时 Model **仍拥有** payload，必须 `vPortFree` [HEAP_FREE] | P0 | 人工 | [memory_ownership.txt](../prompts/memory_ownership.txt) | — |
| C2.5 | `xQueueSend` [QUEUE_SEND] 成功后 Model **禁止**再访问或释放 payload | P1 | 人工 | `good_wss_json_parse.c` | — |
| C2.6 | 所有权转移须在代码或注释标明「谁 alloc / 谁 free」 | P2 | 人工 | `good_presenter_consumer.c` | — |
| C2.7 | Queue 深度与满队列策略（丢帧/非阻塞/Overwrite）须在架构文档写明，禁止 magic number | P1 | 人工 | [queue_event_bus.txt](../prompts/queue_event_bus.txt) | — |
| C2.8 | 禁止传 `lv_obj_t *` 进 Queue（生命周期绑定 UI 任务） | P0 | 人工 | `lv_async_call` 传文本副本 | — |

---

## C3 — cJSON 防泄漏

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C3.1 | 每个 `cJSON_Parse` [PARSE] 在**同一函数**内有且仅有一个 `cJSON_Delete` [DELETE] 出口 | P0 | `cjson_leak_checker.py` | `good_wss_json_parse.c` | `bad_cjson_leak.c` |
| C3.2 | 多出口解析须用 `goto cleanup` 或 `do { } while(0)` 统一 Delete [DELETE] | P0 | 同上 | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) | `bad_cjson_leak.c` early return |
| C3.3 | 进 Queue 前必须 `cJSON_Delete(root)` [DELETE]，仅传 plain heap buffer | P0 | checker + 人工 | `good_wss_json_parse.c` | — |
| C3.4 | 循环内 Parse [PARSE] 每次迭代必须 Delete [DELETE]；禁止高频 Parse+Delete 无节流 | P1 | checker | — | `bad_cjson_leak.c` 循环 |
| C3.5 | `strdup` / `pvPortMalloc` [HEAP_ALLOC] 失败路径不得泄漏已 Parse [PARSE] 的 root | P1 | checker | — | `bad_cjson_leak.c` |
| C3.6 | L2+ 审查须运行 `python tools/cjson_leak_checker.py <file>` 或 `--dir ./src` | P2 | 流程 | — | — |

---

## C4 — ISR / DMA / 音频

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C4.1 | ISR / `HAL_*Callback` 内**仅** `*FromISR` 后缀 FreeRTOS API | P0 | `isr_safety_checker.py` | `fixtures/good_isr.c` | `bad_isr_blocking.c` |
| C4.2 | ISR 须声明 `BaseType_t xHigherPriorityTaskWoken = pdFALSE` 并在末尾 `portYIELD_FROM_ISR` [IRQ_YIELD] | P0 | 同上 | `fixtures/good_isr.c` | — |
| C4.3 | ISR 禁止：`vTaskDelay` [TASK_DELAY]、`xSemaphoreTake/Give` [SEM_TAKE/SEM_GIVE]（非 FromISR）、`printf` [PRINTF]、`malloc`/`pvPortMalloc` [HEAP_ALLOC]、`cJSON_Parse` [PARSE] | P0 | 同上 | — | `bad_isr_blocking.c` |
| C4.4 | I2S Mic/Spk 须 Ping-Pong 双缓冲，缓冲区 4 字节对齐 | P1 | 人工 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | — |
| C4.5 | 音频任务相对优先级 **高于** LVGL 与 WSS（见 core_rules 优先级表） | P1 | `stack_calculator.py` + 平台档 | — | — |
| C4.6 | 音频处理结果经 Queue 送 Presenter，**禁止** ISR/音频任务直接改 UI | P0 | 人工 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | — |
| C4.7 | ISR 禁止获取 mutex（`xSemaphoreTake` [SEM_TAKE] 任何变体） | P0 | checker | — | — |
| C4.8 | 带 Cache 的 SoC：DMA 写完成后 CPU 读前须 **invalidate**；CPU 写后 DMA 读前须 **clean**；缓冲须 DMA-capable 区域 | P1 | 人工 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | — |
| C4.9 | STM32 `HAL_*Callback` / `*IRQHandler` 中禁止 `HAL_Delay`；中断后续工作须转交 task/queue | P0 | `run_review.py --platform stm32` | callback 仅 `*FromISR` 通知 | callback 内 `HAL_Delay(10)` |

---

## C5 — 测试宏 `APP_TEST_MODE_*`

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C5.1 | 每个业务大模块（网络/LVGL/音频/Presenter）须有独立 `APP_TEST_MODE_<MODULE>` | P1 | 人工 | [test_mode_macro.txt](../prompts/test_mode_macro.txt) | — |
| C5.2 | 测试宏须在 `app_test_config.h` 集中定义，禁止散落 magic `#ifdef` | P2 | 人工 | — | — |
| C5.3 | `APP_TEST_MODE_*` 开启时模块可独立编译运行，不依赖完整产品链路 | P2 | 人工 | — | — |

---

## C6 — SDK 需求驱动裁剪

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C6.1 | **先**产品问卷 / 功能清单，**后**裁剪建议；禁止未问卷给固定删除清单 | P0 | 流程 | [sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt) | — |
| C6.2 | JL/BK 裁剪前须扫描 SDK 模块地图并标注 SDK tag / 版本 | P1 | 人工 | `platforms/jl.md` / `platforms/bk.md` | — |
| C6.3 | 每条删除建议须对应「不用的功能点」，禁止「可能用不到」式猜测 | P1 | 人工 | — | — |
| C6.4 | 裁剪输出含回滚方案（保留备份 / git tag / 可逆 Makefile 开关） | P2 | 人工 | — | — |
| C6.5 | 产品层 `main/CMakeLists.txt` 与 Kconfig、init 链一致；未 init / `#if 0` 悬空模块不得编入 | P1 | 人工 | [l2_project_review.md](../workflows/l2_project_review.md) Step 4b · `platforms/bk.md` | — |

---

## C11 — 编码规范

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C11.1 | 文件名 `模块_功能.c/h`，禁止中文名/空格 | P2 | grep | `network_wss.c` | `MyFile.c`、`new file.c` |
| C11.2 | 函数名 `模块_动作_对象()`，≤30 字符 | P2 | 人工 | `presenter_handle_message()` | `doIt()`、>30 字符名 |
| C11.3 | 宏全大写 `MODULE_FEATURE_VALUE`，常量优于 enum | P2 | grep | `WSS_MAX_RETRY_COUNT` | `maxRetry`、`#define MAX 100` |
| C11.4 | 结构体名 `模块_xxx_t` | P2 | 人工 | `app_event_t` | `Event`（大驼峰无前缀） |
| C11.5 | 单函数 ≤80 行，超限须拆分 | P1 | `function_length_checker.py` | `app_main()` 调子函数 | 300 行上帝函数 |
| C11.6 | 每个 .c/.h 须有模块说明文件头注释 | P2 | 人工 | `@file @brief 栈大小 MVP层` | 无注释直接写代码 |

---

## C12 — 错误处理

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C12.1 | FreeRTOS API（`xTaskCreate` [TASK_CREATE]/`xQueueCreate` [QUEUE_CREATE]/`pvPortMalloc` [HEAP_ALLOC]）返回值必须检查 | P0 | `return_check_checker.py` | `error_handling.txt` 模板 | [bad_unchecked_return.c](../examples/bad_unchecked_return.c) |
| C12.2 | malloc [HEAP_ALLOC] 失败须有 fallback，禁止 NULL 解引用 | P0 | 同上 | 同上 | NULL 直接 memcpy → HardFault |
| C12.3 | 统一错误码枚举 `MODULE_ERR_*`，禁止 magic number 返回 | P1 | 人工 | `app_err_t` 枚举 | `return -1`、`return 99` |
| C12.4 | 多资源函数用 `goto cleanup` 统一释放 | P0 | 人工 + checker | `error_handling.txt` cleanup 模板 | 散落 early return 不释放 |
| C12.5 | `configASSERT` 仅用于不可恢复错误（硬件/初始化） | P1 | 人工 | `configASSERT(mutex != NULL)` | `configASSERT(cJSON_Parse(json))` |

---

## C13 — 状态机

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C13.1 | 长生命周期任务须有显式 `enum xxx_state` | P1 | 人工 | `wss_state_t` 枚举 | `static int state = 3` |
| C13.2 | 超过 5 个状态的机须有状态转换表注释 | P2 | 人工 | `state_machine_patterns.txt` 表格 | 无文档的 switch |
| C13.3 | switch-default 处理非法状态（log + reset） | P1 | `state_machine_checker.py` | default: LOG_E + reset to IDLE | 无 default 或 default: break |
| C13.4 | 需断电恢复的状态持久化到 NVS/Flash | P2 | 人工 | `nvs_set_u8("wifi_state", st)` | 只存 RAM |

---

## C14 — 日志规范

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C14.1 | 分级日志 + TAG，禁止裸 `printf` | P1 | `logging_checker.py` | `LOG_E(TAG, "err: %d", err)` | [bad_isr_printf.c](../examples/bad_isr_printf.c) |
| C14.2 | 日志级别可 Kconfig 配置 | P2 | 人工 | `CONFIG_LOG_NETWORK_LEVEL` | 硬编码 if debug |
| C14.3 | ISR / DMA / LVGL timer 内禁止日志 | P0 | 人工 + `isr_safety_checker.py` | 无日志 | ISR 中 `printf("DMA done\n")` |
| C14.4 | 日志禁止打印密码/token 明文 | P1 | `secret_scan_checker.py` + grep | `LOG_I(TAG, "token: %.4s****")` | `LOG_I(TAG, "token: %s", token)` |
| C14.5 | HardFault handler 须采集 PC/LR/寄存器 | P1 | 人工 | `logging_debug.txt` 模板 | 空 HardFault handler |
| C14.6 | 高频 / 周期 / per-frame 日志必须限频、状态变化触发或计数聚合；禁止日志洪水占用 CPU/UART/flash | P1 | `logging_checker.py` + 人工 | `LOG_RATE_LIMIT_MS(1000)` / counter | 循环内每 5ms `LOG_D` |
| C14.7 | 关键链路日志须结构化：包含 event_id、module/TAG、state、err、seq/generation、tick/task；禁止只写不可检索的自然语言 | P2 | 人工 | `EVT_WSS_CONNECT_FAIL state=... err=...` | `LOG_E(TAG, "failed")` |
| C14.8 | 最近日志 ring buffer 须有界、可 crash dump，写入不得阻塞；持久化/上传只能在任务上下文批量执行 | P1 | 人工 | ring dump 32 条 + 后台 flush | ISR 中写 flash / 阻塞上传 |
| C14.9 | Debug / Release / Production 日志 profile 必须明确；量产默认 WARN/ERROR，关闭 verbose 与敏感字段，远程日志需限额与开关 | P1 | 人工 | `CONFIG_LOG_PROFILE_PROD` | 量产默认 DEBUG + 上传全量日志 |

---

## C15 — 任务优先级与通信

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C15.1 | 相邻任务优先级差 ≥2 | P1 | 人工 | `PRIO_WSS = MAX-3, PRIO_LVGL = MAX-5` | `PRIO_WSS=5, PRIO_LVGL=6` |
| C15.2 | 共享资源用 mutex（优先级继承），禁止 binary semaphore 保护 | P1 | 人工 | `xSemaphoreCreateMutex()` [MUTEX_CREATE] | `xSemaphoreCreateBinary()` [SEM_CREATE] 保护共享变量 |
| C15.3 | 禁止运行时 `vTaskPrioritySet`（需文档说明原因和恢复条件） | P2 | grep | 初始化时设定 | 运行时无注释改优先级 |

---

## C16 — 定时器管理

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C16.1 | 软件定时器回调禁止阻塞（daemon 共享，阻塞=所有 timer 停） | P0 | `timer_checker.py` | `timer_management.txt` 发事件模板 | timer 回调中 `tls_handshake()` |
| C16.2 | 动态创建的 timer 须有 stop + delete 路径 | P1 | `timer_checker.py` | `heartbeat_stop()` 含 delete | 创建后无释放 |
| C16.3 | 周期 `pdTRUE` / 单次 `pdFALSE` 须区分 | P2 | 人工 | 按需选择 auto-reload | 全用 pdTRUE 不区分 |

---

## 症状 → 约束 ID 快查（Crash workflow 用）

| 症状 | 优先核查 ID |
|------|-------------|
| Guru Meditation + network/UI | C1.1, C1.5, C1.6 |
| HardFault @ Presenter / 随机 | C2.1, C2.2, C2.3 |
| STACK OVERFLOW / WssTask | C4.5 + 平台栈表 |
| 界面 frozen | C1.5, C1.6, C2.7 |
| I2S 卡顿 / 爆音 | C4.1–C4.4 |
| 音画不同步 / lip-sync drift | **C25.1, C25.2, C25.6** + [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) |
| 视频掉帧 / preview 卡顿 | **C25.3, C25.4**, C23.3–C23.5 |
| camera 回调后 HardFault / 花屏 | **C25.5**, C1.1, C4.1 |
| 音频爆音 + UI 卡顿共振 | **C25.3**, C4.5, C15.1 |
| ASR 空 / AEC 异常 / 音频变速 | **C26.1, C26.2** + [av_codec_format.txt](../prompts/av_codec_format.txt) |
| RGB565 花屏 / 行错位 / 视频画面倾斜 | **C26.3**, C23.6 |
| 编码延迟周期性尖峰 | **C26.4, C26.5**, C25.4 |
| 跑几分钟后音画逐渐漂移 | **C27.1, C27.3, C27.6** + [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) |
| 网络抖动后爆音 / 卡顿 / 恢复慢 | **C27.2, C27.5**, C20.1 |
| 只靠 delay 对齐导致 WDT 或卡顿 | **C27.4**, C25.3, C8.3 |
| Camera/LCD 花屏 / 偶发旧帧 / 图像撕裂 | **C28.1–C28.5**, C23.4, C26.3 |
| I2S 爆音 / PCM 坏块 / DMA 后读到旧数据 | **C28.2, C28.5**, C4.8, C26.2 |
| 零拷贝 preview 偶发 use-after-free | **C28.3, C28.4**, C2.3, C25.3 |
| heap 持续下降 | C3.1–C3.5, C2.4, **C7.2**（先修泄漏再缩池） |
| internal SRAM 紧张但 PSRAM/外部 RAM 空闲 | **C7.10**, C7.8, C28.1 + [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) |
| malloc fail 但总 free heap 看似足够 | **C7.12** largest free block + [l2_memory_analysis.md](../workflows/l2_memory_analysis.md) |
| 跨堆释放 / allocator family 混用 | **C7.10, C7.11** + [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) |
| 每帧 / 每包 malloc/free 抖动 | **C7.4, C7.13**, C25.4, C26.4 |
| TLS 握手 fail / 反复断线 | C8.2, C7.5–C7.12 + [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) |
| WDT / task watchdog | **C8.3–C8.6**, C1.5, C4.7 + [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) |
| 启动后首包丢失 / Queue 满 | **C8.1** |
| 缩池 / 关模块后功能异常 | **C7.6** + [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) |
| 优化建议无数据支撑 | **C7.1** |
| 仓库含明文密钥 / token 泄露 | **C9.1–C9.4** + `secret_scan_checker.py` |
| 录音失效 / ASR 空 / 第二轮听不见 | **C10.1–C10.5** + [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) |
| 唤醒叮后麦幅骤降 / tap peak 塌陷 | **C10.1, C10.2** |
| AI 键打断 TTS 后不再上传 / speaker stop 后 MIC 失效 | **C10.1, C10.5, C24.4** + [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) + [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) |
| NULL 解引用 / HardFault @ malloc | **C12.1, C12.2** + [error_handling.txt](../prompts/error_handling.txt) |
| 资源泄漏（socket/fd 未释放） | **C12.4**（early return 不 cleanup） |
| 裸 printf / 日志洪水 | **C14.1, C14.3, C14.6** + [logging_debug.txt](../prompts/logging_debug.txt) + [logging_management_constraints.md](logging_management_constraints.md) |
| 日志含明文密码/token | **C14.4, C9.3** |
| 现场日志无法复盘 / 缺少关联 ID | **C14.7, C14.8** + [logging_management_constraints.md](logging_management_constraints.md) |
| 量产性能差 / 串口刷屏 / flash 磨损 | **C14.6, C14.8, C14.9** |
| timer 全停 / daemon 卡死 | **C16.1**（timer 回调阻塞）
| 跨核数据竞争 / mailbox 队列满 | **C17.1, C17.2** + [multi_core_ipc.txt](../prompts/multi_core_ipc.txt) |
| 唤醒后状态丢失 / 重新初始化 | **C21.1, C21.2** + [low_power_management.txt](../prompts/low_power_management.txt) |
| 睡眠后功耗不降 / 外设漏电 | **C21.4**（外设未断电） |
| OTA 后设备变砖 / 回滚失败 | **C22.1, C22.2, C22.4** + [ota_update_safety.txt](../prompts/ota_update_safety.txt) |
| OTA 下载卡死 / 反复重试 | **C22.5** |
| tickless idle 后音频卡顿 | **C21.3**（高频任务受影响） |
| 接手模块需反复追调用上下文 / 所有权 | **C29.1–C29.5** + [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) |
| 队列满但不知道谁生产/谁消费 | **C30.1–C30.5**, C2.7 |
| 假死 / 长时间卡在等待点 | **C31.1–C31.4**, C8.3, C20.2 + `blocking_wait_checker.py` |
| 现场日志无法判断状态、错误或资源水位 | **C32.1–C32.5**, C14.7, C14.8 |
| stop 后重启失败 / deinit 后崩溃 / 资源泄漏 | **C33.1–C33.5**, C12.4, C24.1 |
| 周期性延迟尖峰 / 控制环抖动 / callback 卡顿 | **C34.1–C34.5**, C4.3, C14.3, C25.4 |
| 启动/联网/音视频/UI 关键路径反复超时 | **C35.1–C35.5**, C31, C32 |
| 帧/包/事件路径拷贝过多、DMA cache 问题 | **C36.1–C36.5**, C2, C28 |
| 队列满后卡死、延迟堆积、降级不可控 | **C37.1–C37.5**, C30, C31 |
| 断网/外设异常后只能重启恢复 | **C38.1–C38.5**, C20, C24 |
| `#ifdef` 散落导致配置组合不可测 | **C39.1–C39.5**, C6, C9 |
| 新人无法一键复现 build/flash/log/decode | **C40.1–C40.5**, C8, C14 |
| 修复没有 good/bad 样本，后续又回归 | **C41.1–C41.5**, checker self-test |
| GPIO/DMA/IRQ/cache/heap 冲突到板上才暴露 | **C42.1–C42.5**, C4, C7, C28 |
| 偶发死锁、WDT、网络差时 UI/音视频抖动 | **C43.1–C43.5**, C15, C31, C34, C37 |
| 音频爆音、视频掉帧、周期性延迟尖峰 | **C44.1–C44.5**, C4, C34, C35 |
| 传感器读数漂移、偶发 I2C/SPI 卡死、采样时间轴对不上 | **C45.1–C45.5**, C18, C31, C32, C34, C42 |

---

## 约束冲突与权衡矩阵

以下场景中两条或多条约束可能互相矛盾，Agent 需要**权衡决策**并记录理由。

| 冲突场景 | 约束 A | 约束 B | 权衡方案 |
|----------|--------|--------|----------|
| **init 需同步时间** | C8.6 init 禁同步 TLS/大 Parse | C8.2 TLS 握手前须 SNTP 同步 | SNTP 用异步 `esp_netif_sntp_init()` + 回调通知，不在 main 阻塞等待 |
| **LVGL 锁序 vs SDK 锁序** | C1.6 双锁顺序：先网络后 LVGL | ESP32 `esp_lvgl_port` 内部锁序可能相反 | 以 SDK 内部锁序为准；若冲突则用 `lv_async_call` [ASYNC_CALL] 替代 mutex（避免锁序问题） |
| **WSS 栈 vs 内存受限** | C7.5 WSS 栈 ≥4096 bytes | 设备总 RAM < 200KB | 优先关闭未用模块（C6）释放 RAM；若仍不足则缩 LwIP/mbedTLS 池（C7.6），**不缩 WSS 栈** |
| **音频优先级 vs LVGL** | C4.5 音频优先级 > LVGL | C15.1 相邻优先级差 ≥2 | 音频 = MAX-1, WSS = MAX-3, LVGL = MAX-5（满足两条约束） |
| **日志调试 vs ISR 安全** | C14.1 需要日志排查 | C4.3/C14.3 ISR 禁止日志 | ISR 中用 flag/event 记录状态，退出 ISR 后在任务中打印 |
| **测试宏 vs 代码体积** | C5.1 每模块 APP_TEST_MODE_* | C6 量产须关闭减小体积 | 测试宏默认 `#define ... 0`（编译器优化掉）；量产前确认全部为 0 |
| **密钥安全 vs 调试便利** | C9.1 密钥不入库 | 开发阶段需要频繁烧写 | 用 `config.secrets.example`（占位）+ `config.secrets`（gitignore）；调试板用 UART 临时注入 |
| **跨核通信 vs 延迟** | C17.1 跨核须 IPC | IPC 增加延迟 | 高频小数据用共享内存 + 硬件信号量（C17.3）；低频用 mailbox 队列 |
| **函数长度 vs 错误处理** | C11.5 单函数 ≤80 行 | C12.4 goto cleanup 模板增加行数 | cleanup 标签后的释放代码不计入业务逻辑行数；若仍超限则提取 cleanup 为独立函数 |
| **timer 回调 vs 业务逻辑** | C16.1 timer 回调禁阻塞 | 业务需要在 timer 中发事件 | timer 回调仅 `xQueueSend` [QUEUE_SEND] 或 `xTaskNotify` [TASK_NOTIFY_GIVE]，处理逻辑移到专用任务 |
| **低功耗 vs 网络保持** | C21.4 睡眠前关 WiFi | C20.5 网络断线须降级 | 深睡眠前主动断开 WSS + 通知云端；唤醒后走完整重连流程（C20.1 指数退避） |
| **低功耗 vs 语音实时** | C21.3 Tickless Idle | C4.5 音频优先级最高 | 语音活跃期禁用 tickless idle；空闲时启用；或用独立硬件定时器驱动 I2S |
| **音频主时钟 vs 显示平滑** | C25.1 audio clock master | C23.3 帧率匹配 | 音频为主，视频按 PTS 丢帧/重复帧，禁止用固定 `vTaskDelay` [TASK_DELAY] 反向拖音频 |
| **视频不丢帧 vs 内存受限** | C25.3 有界 video queue | C7.13 固定块池 | 预分配短 ring，满时 drop-oldest + 释放 frame，禁止扩容或阻塞 audio |
| **格式转换 vs 实时性** | C26.1 格式一致或显式转换 | C25.4 热路径禁分配 | 转换器在 start 阶段预分配 workspace，运行期只处理固定块 |
| **编码质量 vs 延迟** | C26.5 codec 生命周期 | C4.5 音频优先级最高 | codec 参数启动时协商，运行期禁止重建 codec；格式变化走 reset/flush |
| **漂移校正 vs 音质** | C27.3 drift correction 有上限 | C26.5 codec 生命周期 | 小漂移做 bounded resample，大漂移触发 resync；禁止每帧重建 codec |
| **jitter buffer 深度 vs 低延迟** | C27.2 有界水位 | C25.3 队列有界低阻塞 | 设 target delay 和 high watermark；超水位 drop-oldest/补静音，不扩容阻塞 |
| **零拷贝省拷贝 vs 生命周期复杂度** | C28.3 owner/generation | C25.3 有界队列 | 零拷贝只传 index/handle，release 后复用；压力大时 drop-oldest 而不是复用未释放 buffer |
| **PSRAM 容量 vs DMA/cache 一致性** | C28.1 DMA-capable | C7.10 外部 RAM 优先 | DMA 热路径优先 internal/DMA SRAM；外部 RAM 只放普通/低频/非 DMA 对象，或经显式 copy/cache 同步的冷数据 |
| **cache 操作开销 vs 实时性** | C28.2/C28.5 clean/invalidate | C4.5 音频优先级最高 | 按 frame/half-buffer 批量同步，范围对齐且最小化；禁止每 sample 做 cache 操作 |
| **永久等待 vs 简化代码** | C31.1 有限 timeout | dedicated consumer 等待事件 | 仅 idle/daemon consumer 可永久等待，须满足 C31.4 注释、无持锁、无 stop/deinit 阻塞 |
| **现场可观测 vs 热路径实时性** | C32.5 现场 dump | C34.2 hot path 禁日志/IO | 热路径只计数或写有界 ring，普通任务低频脱敏 dump |
| **完整 cleanup vs 函数长度** | C33.3 lifecycle cleanup | C11.5 函数 ≤80 行 | 优先保证 release 对称；复杂 cleanup 提取 helper |
| **热路径零分配 vs RAM 占用** | C34.2 hot path 禁分配 | C7.13 固定块池 | 启动期预分配固定块池；满时 drop/backpressure，不运行期扩容 |
| **锁保护 vs 实时性** | C43.1/C43.2 锁预算 | C34.1/C37 热路径与背压 | 临界区只读写状态和引用计数；复制快照后解锁，再做 IO/解析/降级处理 |
| **关中断原子性 vs 实时性** | C44.1/C44.2 临界区预算 | C4/C34 ISR 与热路径实时性 | 关中断只覆盖寄存器/flag/counter；复杂一致性用 mutex/队列/双缓冲转移到 task |
| **传感器精度 vs 实时性** | C45.4/C45.5 校准与单位元数据 | C34/C35 热路径预算 | 校准、补偿表和自检放 start/低频任务；采样热路径只做定长换算并附带 timestamp/scale |

---

## L2 输出引用格式

违规项须写：`C2.2` — `file:line` — 问题 — 修复（引用 good 范例）

```markdown
- C1.1 — network_wss.c:142 — WSS 回调直接 lv_label_set_text [OBJ_SET] — 改 Queue → lv_async_call [ASYNC_CALL]（见 good_mvp_pattern.c）
```
