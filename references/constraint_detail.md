# 铁律细粒度约束矩阵（L2+ 按需加载）

Agent 在 L2 Code Review、Crash 诊断、L3 架构输出时读取本文件。每条约束有唯一 **ID**（`C#.#`），违规报告与 checklist 须引用 ID。

> C1–C45（含 C22 OTA），45 个约束域，248 条规则。

总纲摘要 → [core_rules.md](core_rules.md)

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

## C7 — 内存分配与优化（通用）

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C7.1 | 缩池 / 缩栈 / 关模块**前**须记录基线（堆最低水位、任务 stack watermark、Flash/RAM）；无基线禁止给具体数值建议 | P0 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.2 | 优化顺序：**先**修泄漏与所有权（C2/C3）→ 关未用模块（C6）→ 缩 LwIP/TLS/LVGL 池 → **最后**缩任务栈 | P1 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.3 | 大 buffer（>256B）、证书链、JSON 解析树**禁止**放栈上；须堆分配或静态/对象池 | P0 | 人工 | — | — |
| C7.4 | 长连接 / 高频路径优先固定块或对象池；禁止每帧 / 每包 `malloc` [HEAP_ALLOC]+`free` [HEAP_FREE] | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.5 | WSS/TLS 任务栈须按握手峰值实测，**不得低于 4096 bytes**（建议 6144–8192） | P0 | `stack_calculator.py` + 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |
| C7.6 | 缩 LwIP / mbedTLS / LVGL 池**每步**须冒烟 WiFi + WSS + 业务闭环 | P1 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.7 | 主工程只链入**一个** TLS 栈（mbedtls / wolfssl / psa 择一） | P1 | 人工 | — | — |
| C7.8 | ISR / DMA / 实时路径缓冲须在 SRAM（或平台文档允许的 fast RAM）；禁止无依据默认放 PSRAM / 外部慢速区 | P1 | 人工 | `platforms/bk.md` 等 | — |
| C7.9 | 重连 / 错误恢复禁止 tight loop 反复 TLS 握手；须指数退避（cap 建议 60s） | P1 | 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |
| C7.10 | 普通堆申请在平台支持外部 RAM/PSRAM 且对象非 DMA/ISR/实时热路径时，须**优先外部 RAM**，失败再回退 internal SRAM；allocator family / heap kind 须可追踪以保证 matched free | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | 大缓存默认占用 internal SRAM |
| C7.11 | 跨模块 / 跨任务对象须经项目级统一 allocator/free 封装，统一处理 external-first、DMA/internal 分类、heap kind 记录、失败日志和 matched free；业务模块禁止散落直接调用多族 allocator | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | 业务代码混用 `malloc` / `psram_malloc` / `heap_caps_malloc` [HEAP_ALLOC] |
| C7.12 | 内存遥测须按 heap kind 采集 free、minimum free、largest free block、alloc fail 计数；仅记录总 free heap 不足以判断碎片和可分配性 | P1 | 人工 | [l2_memory_analysis.md](../workflows/l2_memory_analysis.md) | 只打印 `xPortGetFreeHeapSize()` |
| C7.13 | 高频 / 固定尺寸对象须使用启动期预分配固定块池或 ring buffer，O(1) alloc/free，满时明确 drop/backpressure；禁止运行期扩容或每帧动态分配 | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | 每包 `malloc/free`，队列满后临时扩容 |

---

## C8 — 启动顺序 / 阻塞 / 看门狗

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C8.1 | Queue + Presenter Looper **须**在注册 WiFi/WSS/网络事件回调之前创建并就绪 | P0 | 人工 | [good_boot_sequence.c](../examples/good_boot_sequence.c) | `bad_wss_blocking.c` |
| C8.2 | WSS/TLS **须**在 WiFi 获 IP 之后；证书校验 **须** SNTP 同步完成 | P0 | 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |
| C8.3 | Presenter `xQueueReceive` [QUEUE_RECV] **禁止**默认 `portMAX_DELAY` [TIMEOUT_FOREVER]；须有限 timeout + 循环 | P1 | 人工 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) | — |
| C8.4 | LVGL 任务 `lv_timer_handler` 循环内**禁止**网络/TLS/长 mutex/除固定 tick 外的阻塞 | P0 | 人工 | [good_mvp_pattern.c](../examples/good_mvp_pattern.c) | `bad_wss_blocking.c` |
| C8.5 | 模块 reconnect **须**幂等：同任务禁止重复 `xTaskCreate` [TASK_CREATE]；用句柄 + 状态机/Notify | P1 | 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | — |
| C8.6 | main/init 路径**禁止**同步 TLS 握手、大 Parse、超长 delay 链（防 Task WDT） | P0 | 人工 | [good_boot_sequence.c](../examples/good_boot_sequence.c) | `bad_wss_blocking.c` |

---

## C9 — 密钥 / 凭证 / 仓库卫生

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C9.1 | `CONFIG_*SECRET*` / `*PASSWORD*` / `*TOKEN*` / `*API_KEY*` **禁止**非空值写入入库 config | P0 | `secret_scan_checker.py` | `config.secrets` + `config.secrets.example` | 明文 sdkconfig |
| C9.2 | Git remote URL **禁止**内嵌 `user:pass@` / token | P0 | `secret_scan_checker.py --git-remotes` | SSH remote | HTTPS + token |
| C9.3 | 运行时日志**禁止**打印 WiFi 密码、RTC token、完整鉴权头 | P1 | 人工 + grep | 脱敏日志 | 明文 LOGI |
| C9.4 | 密钥文件须 `.gitignore`（`config.secrets`、`config.local`、`.env`） | P1 | 人工 | 项目 `.gitignore` | — |
| C9.5 | 构建须支持 `config.secrets` 本地覆盖（`CONFIG_SUBSTITUTE_FILE` 或等价） | P2 | 流程 | `merge_config_secrets.sh` | 仅 menuconfig 手填 |
| C9.6 | L2 工程审查须扫描 `projects/**/config` 与 `--git-remotes` | P2 | `run_review.py --scan-secrets` | — | — |

---

## C10 — 语音采集 / 云端 ASR / Uplink（共享引擎）

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C10.1 | Mic+Spk+AEC 共用 engine 时，prompt/TTS **结束须 detach** 播放路径（**stop** 与 **FINISHED** 双路径） | P0 | 人工 + 日志 | [good_voice_prompt_uplink.c](../examples/good_voice_prompt_uplink.c) | 仅 stop detach，FINISHED 泄漏 |
| C10.2 | 开 uplink tap / capture **前**须 AEC settle（典型 80–150ms）+ `wait_mic_capture_ready` | P0 | peak 对比 + 日志 | 同上 | prompt 刚停即 start uplink |
| C10.3 | 诊断「录音失效」须先看 **peak / SD 字节 / uplink**，区分无 PCM vs ASR 空 | P1 | 日志 checklist | [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) | 未看日志即换 Mic 驱动 |
| C10.4 | prompt tone 与云端 uplink **串行**：本地播放 **FINISHED+detach** 后再 start capture | P1 | 时序日志 | 同上 | 并发 play + capture |
| C10.5 | 语音会话 **generation** 丢弃 stale 的 FINISHED、timer、TTS chunk、interrupt 回调 | P1 | 代码审查 | 同上 | cancel 后旧回调仍 capture / 旧 TTS 重启 speaker |
| C10.6 | 播放 slot/handle id 来自配置/对象字段，**禁止** hardcode magic number | P2 | grep hardcoded id | `prompt->playback_slot_id` | `#define PLAYBACK_SLOT 1` 散落 |

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

## 严重度定义

| 级别 | 含义 | 处理 |
|------|------|------|
| P0 | 必崩 / 必泄漏 / 必死锁 | 阻塞合并，须附修复 diff 或范例引用 |
| P1 | 高概率量产问题 | 本迭代必须修复或登记风险 |
| P2 | 可维护性 / 可测试性 | 建议修复，可排期 |

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

## C18 — 外设驱动安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C18.1 | GPIO 方向必须在使用前配置（gpio_config 先于 gpio_set_level） | P0 | `peripheral_driver_checker.py` | `gpio_config()` [GPIO_CONFIG] → `gpio_set_level()` [GPIO_SET] | 未 config 直接 set_level |
| C18.2 | I2C 设备地址必须来自 datasheet，禁止硬编码猜测 | P1 | `peripheral_driver_checker.py` | `#define OLED_ADDR 0x3C /* datasheet */` | `#define OLED_ADDR 0x60` 无依据 |
| C18.3 | SPI 时钟模式（CPOL/CPHA）必须匹配从设备 datasheet | P1 | 人工 | `.mode = 0` 与 Flash 匹配 | `.mode = 2` 与 Flash 不匹配 |
| C18.4 | DMA 通道分配须文档化，同一通道不可被两个外设同时使用 | P1 | 人工 | DMA 通道分配表 | I2S 和 SPI 共享 DMA 通道 |
| C18.5 | ADC 引脚必须配置为模拟输入模式，禁用上拉/下拉 | P2 | 人工 | `adc1_config_channel_atten()` | ADC 引脚同时配置为数字输出 |
| C18.6 | PWM 频率与分辨率互斥，须根据应用选择 | P2 | 人工 | 5kHz/13-bit（电机） | 100kHz/7-bit（亮度不够） |

---

## C19 — Flash / NVS / 状态持久化

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C19.1 | NVS 写入后必须 `nvs_commit()` [NVS_COMMIT] + 检查返回值 | P0 | `flash_nvs_checker.py` | `nvs_set_str` [NVS_WRITE] → `nvs_commit` [NVS_COMMIT] → `nvs_close` | 不 commit 不检查返回值 |
| C19.2 | Flash 擦写期间禁止读取同分区 | P1 | 人工 | 擦写前关闭读句柄 | 同时 erase + read NVS |
| C19.3 | OTA 首次启动必须调用 `mark_valid_cancel_rollback` [OTA_MARK_VALID] | P1 | 人工 | `app_main` 中调用 | 未调用，重启后回滚 |
| C19.4 | OTA 产品分区表须含 `ota_0` + `ota_1`；NVS 分区不可删除 | P1 | 人工 | `partitions.csv` 含 ota_0/ota_1 | 缺 ota_1 分区 |
| C19.5 | Flash 高频写入场景须做磨损均衡（NVS blob API / 缓冲写入） | P2 | 人工 | 每 5 分钟批量写入 | 每秒写 NVS |

---

## C20 — 网络韧性

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C20.1 | WiFi/WSS 断线重连必须有指数退避（1s→2s→…→60s cap） | P0 | `network_resilience_checker.py` | `WIFI_RECONNECT_BASE_MS * (1 << retry)` | 立即 `esp_wifi_connect()` tight loop |
| C20.2 | 所有阻塞网络操作（recv [SOCKET_RECV]/send [SOCKET_SEND]/connect [SOCKET_CONNECT]）必须有有限超时 | P0 | `network_resilience_checker.py` | `setsockopt(SO_RCVTIMEO, 10s)` | `recv(sock, buf, len, 0)` [SOCKET_RECV] 无超时 |
| C20.3 | DNS 解析失败必须处理，不可直接崩溃 | P1 | 人工 | `getaddrinfo` 返回值检查 + 重试 | `getaddrinfo` 失败直接 HardFault |
| C20.4 | TLS 握手失败须区分错误类型（证书无效 vs 超时 vs 服务端拒绝） | P1 | 人工 | 按 mbedTLS 错误码分类处理 | 所有 TLS 错误统一重试 |
| C20.5 | 网络断线时业务必须有降级策略（离线模式） | P1 | 人工 | `NET_MODE_OFFLINE` + 本地功能继续 | 断线后产品完全不可用 |

---

## C21 — 低功耗管理

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C21.1 | 深度睡眠前必须保存运行状态到 NVS/Flash（`nvs_commit` [NVS_COMMIT] + 检查返回值） | P0 | `low_power_checker.py` | `nvs_set_u8` [NVS_WRITE] → `nvs_commit` [NVS_COMMIT] → `esp_deep_sleep_start` [DEEP_SLEEP] | 直接 `esp_deep_sleep_start` [DEEP_SLEEP] 丢失状态 |
| C21.2 | 唤醒后须检查 `wakeup_cause`，恢复状态而非重新初始化 | P1 | 人工 | `esp_sleep_get_wakeup_cause()` 分支处理 | 唤醒后无条件 full_init |
| C21.3 | Tickless Idle 配置须确认高频任务不受唤醒延迟影响 | P1 | 人工 | `CONFIG_FREERTOS_USE_TICKLESS_IDLE=y` + 高频任务用独立定时器 | 盲开 tickless 导致音频 tick 漂移 |
| C21.4 | 深度睡眠前必须逐个关闭外设电源（LCD 背光/音频 DAC/WiFi/PSRAM） | P1 | `low_power_checker.py` | `power_down_peripherals()` 逐个关闭 | 仅 `esp_deep_sleep_start` 不关外设 |
| C21.5 | 多唤醒源（timer/ext0/ext1/PIR）同时配置时须确认 GPIO 无冲突 | P2 | 人工 | 唤醒源分配表 + GPIO 唯一性检查 | 同一 GPIO 配 ext0 + ext1 冲突 |

---

## C22 — OTA / 固件升级安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C22.1 | OTA 镜像必须经过签名验证后才能写入 Flash；版本降级必须拒绝 | P0 | `ota_safety_checker.py` | [good_ota_update.c](../examples/good_ota_update.c) | [bad_ota_no_rollback.c](../examples/bad_ota_no_rollback.c) |
| C22.2 | OTA 升级后首次启动必须调用 `mark_valid_cancel_rollback()` [OTA_MARK_VALID]；失败必须可回滚到旧固件 | P0 | `ota_safety_checker.py` | 同上 | 同上 |
| C22.3 | OTA 产品分区表必须含 `ota_0` + `ota_1`；NVS 分区不可删除 | P1 | 人工 | [ota_update_safety.txt](../prompts/ota_update_safety.txt) | — |
| C22.4 | OTA 断电恢复：新固件写入非活动分区，断电后旧固件仍可运行；禁止擦除当前运行分区 | P0 | 人工 | 同上 | 同上 |
| C22.5 | OTA HTTP 下载必须有连接超时和读取超时；重试必须有上限和退避 | P1 | `ota_safety_checker.py` | 同上 | 同上 |
| C22.6 | 差分升级必须校验 patch 完整性，失败必须能回退到全量升级 | P2 | 人工 | — | — |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| OTA 后设备变砖 | C22.1 未验证签名，C22.4 覆盖了当前分区 |
| OTA 后重启回滚到旧固件 | C22.2 未调用 mark_valid_cancel_rollback |
| OTA 下载卡死不超时 | C22.5 HTTP 无超时配置 |
| OTA 反复重试不放弃 | C22.5 重试无上限 |
| 分区表缺少 ota_1 | C22.3 分区表不完整 |

---

## C23 — 显示驱动安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C23.1 | LCD 初始化时序必须严格遵循 datasheet（复位脉宽≥10ms、复位后等待≥120ms、Sleep Out 后等待≥120ms） | P0 | 人工 | [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) | 复位后立即发命令 |
| C23.2 | 背光控制必须用 PWM（非 GPIO 开关），支持亮度调节和渐变；低功耗时关闭背光电源 | P1 | 人工 | `ledc_set_duty` + `gpio_set_level(BL_EN, 0)` | `gpio_set_level(BL_PIN, 1)` 仅开/关 |
| C23.3 | `lv_timer_handler` [TIMER_HANDLER] 调用频率必须匹配面板刷新率（60Hz→16ms，30Hz→33ms）；禁止过快调用浪费 CPU | P1 | 人工 | `vTaskDelay(1000/REFRESH_RATE)` [TASK_DELAY] | `vTaskDelay(1)` [TASK_DELAY] 1ms 调用 |
| C23.4 | 显示刷新必须有撕裂防护（TE 信号同步 / 双缓冲 / 直接模式）；禁止单缓冲无同步写入 | P1 | 人工 | `esp_lcd_panel_io_tx_param(0x35)` TE 信号 | 单缓冲直接写入 |
| C23.5 | 帧缓冲大小必须根据 RAM 可用性选择：PSRAM 可用→全屏双缓冲；RAM 不足→部分刷新（1/5 或 1/10 屏）；分配失败必须检查 | P0 | `display_driver_checker.py` | `heap_caps_malloc` [HEAP_ALLOC] 返回值检查 | 未检查 `malloc` [HEAP_ALLOC] 返回 |
| C23.6 | `lv_disp_drv_t` 注册必须设置 `hor_res`、`ver_res`、`draw_buf`、`flush_cb`；禁止遗漏必要字段 | P1 | `display_driver_checker.py` | 完整 `lv_disp_drv_init` + 字段赋值 | 缺少 `hor_res`/`ver_res` |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| LCD 白屏 / 无显示 | C23.1 初始化时序错误 |
| 画面撕裂 | C23.4 无 TE 同步 |
| UI 渲染区域错误 | C23.6 `hor_res`/`ver_res` 未设置 |
| 背光无法调节 | C23.2 GPIO 直接控制无 PWM |
| 内存不足崩溃 | C23.5 帧缓冲分配失败 |

---

## C24 — 外设关闭安全（硬件收尾）

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C24.1 | 异常退出路径必须与正常完成路径调用相同的收尾函数（goto cleanup） | P0 | 人工 | [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) | 异常 return 跳过收尾 |
| C24.2 | 外设 stop 函数必须可重入（有状态检查） | P1 | 人工 | `if (!s_enabled) return;` | 无状态检查重复关闭 |
| C24.3 | abort/timeout/skip 路径必须释放所有硬件资源 | P0 | 人工 | `goto cleanup` 统一收尾 | 超时直接 return |
| C24.4 | 外设 stop/deinit 前必须等待 DMA/任务 idle；音频/媒体链路须区分 `idle` 与 `deinit/free` | P1 | 人工 | `while (dma_is_busy())` / `stop_playback` 只进 idle | DMA 传输中关闭 / speaker stop 释放 capture backend |
| C24.5 | 执行器停止后必须关闭加热/电源门控/外设使能 | P0 | 人工 | `actuator_stop_motion()` → `peripheral_power_disable()` | 只停执行器不关电源 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 执行器停转但加热/电源门控仍开启 | C24.5 收尾不完整 |
| 异常后外设未关闭 | C24.1 异常路径未收尾 |
| 重复调用 stop 出错 | C24.2 不可重入 |
| 超时后硬件仍在运行 | C24.3 超时路径未释放 |
| 关闭时 DMA 报错 | C24.4 未等待 DMA 完成 |
| 停 speaker 后 MIC 不工作 | C24.4 shared backend 被错误 deinit/free |

---

## C25 — 音视频管线 / A/V Sync

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C25.1 | A/V 同步必须以 audio sample clock / I2S DMA timestamp / audio PTS 为 master clock；视频只能追帧、丢帧、重复帧或轻微调整 | P0 | `av_pipeline_checker.py` + 人工 | [good_av_pipeline_sync.c](../examples/good_av_pipeline_sync.c) | [bad_av_pipeline_blocking.c](../examples/bad_av_pipeline_blocking.c) |
| C25.2 | audio/video frame 结构必须包含 `pts_ms`/`timestamp_ms`、`seq`、`duration_ms` 或 `sample_count`，并标注 owner | P0 | `av_pipeline_checker.py` | 同上 | 同上 |
| C25.3 | 音视频队列必须有界并定义背压；video queue 满时默认 drop-oldest，audio hot path 不得被 video/UI 阻塞 | P1 | `av_pipeline_checker.py` + 人工 | 同上 | 同上 |
| C25.4 | per-frame 热路径（process/render/decode/callback）禁止 `malloc` [HEAP_ALLOC]/`free` [HEAP_FREE]/`pvPortMalloc` [HEAP_ALLOC]/`printf` [PRINTF]/`LOG_*` [LOG_WRITE]，使用 pool/ring + 低频统计日志 | P1 | `av_pipeline_checker.py` | 同上 | 同上 |
| C25.5 | camera/LCD/DMA callback 只允许 notify/enqueue/置 flag；禁止直接跑 LVGL 对象更新、codec、cJSON、网络收发 | P0 | `av_pipeline_checker.py` | 同上 | 同上 |
| C25.6 | 必须保留 `av_drift_ms`、`dropped_frames`、`late_frames`、`audio_underrun/overrun` 等现场诊断计数 | P2 | 人工 + checker 提醒 | 同上 | — |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 音画不同步 / lip-sync drift | C25.1 主时钟错误，C25.2 缺 PTS/seq |
| preview 卡顿 / 视频掉帧 | C25.3 无背压或 queue 阻塞，C25.4 热路径分配/日志 |
| camera 回调后 UI 花屏 / HardFault | C25.5 callback 直接碰 UI/codec/network |
| 只看平均帧率正常但现场仍漂移 | C25.6 缺 drift/late/drop 遥测 |

---

## C26 — 音视频编解码 / 媒体格式一致性

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C26.1 | I2S / AEC / ASR / encoder / uplink 的 sample rate、channels、bit depth、endianness 必须一致；若不同必须有显式转换器 | P0 | `media_format_checker.py` + 人工 | [good_media_format_contract.c](../examples/good_media_format_contract.c) | [bad_media_format_mismatch.c](../examples/bad_media_format_mismatch.c) |
| C26.2 | `frame_samples = sample_rate_hz * frame_ms / 1000 * channels`；DMA half-buffer、encoder input、Queue payload 必须同公式推导 | P0 | `media_format_checker.py` | 同上 | 同上 |
| C26.3 | video frame 必须声明 width/height/pixel_format/stride_bytes；RGB565 stride ≥ width*2，RGB888 stride ≥ width*3 | P1 | `media_format_checker.py` | 同上 | 同上 |
| C26.4 | resample / channel mix / colorspace convert / encode / decode 热路径禁止 `malloc` [HEAP_ALLOC]/`free` [HEAP_FREE]/`printf` [PRINTF]/`LOG_*` [LOG_WRITE]，使用预分配 workspace | P1 | `media_format_checker.py` | 同上 | 同上 |
| C26.5 | codec handle 必须在 open/start 阶段创建、stop/cleanup 阶段释放；禁止每帧 create/init/open | P0 | `media_format_checker.py` | 同上 | 同上 |
| C26.6 | 必须保留 negotiated format、format_mismatch_count、codec_error_count、max encode/decode time、last_frame_size 等遥测 | P2 | 人工 + checker 提醒 | 同上 | — |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| ASR 空、AEC 发散、音频快慢不对 | C26.1 sample rate/channels/bit depth 不一致 |
| Opus/AAC 编码失败或声音周期性破碎 | C26.2 frame_samples 与 frame_ms 不匹配 |
| RGB565 花屏、行错位、画面倾斜 | C26.3 stride 或 pixel format 错 |
| 编码延迟尖峰、heap 抖动 | C26.4 热路径分配/日志，C26.5 每帧创建 codec |

---

## C27 — 音视频时钟漂移 / Jitter Buffer

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C27.1 | A/V sync 必须声明唯一 master clock，默认以 audio sample clock / I2S DMA timestamp / audio PTS 为准；frame PTS 必须单调 | P0 | `av_clock_jitter_checker.py` + 人工 | [good_av_clock_jitter.c](../examples/good_av_clock_jitter.c) | [bad_av_clock_jitter.c](../examples/bad_av_clock_jitter.c) |
| C27.2 | jitter buffer 必须定义 capacity、low watermark、high watermark、target delay 与满水位策略 | P0 | `av_clock_jitter_checker.py` | 同上 | 同上 |
| C27.3 | drift correction 必须有 ppm 上限；禁止无界 resample ratio、playback delay 或每帧 reset codec | P1 | `av_clock_jitter_checker.py` + 人工 | 同上 | 同上 |
| C27.4 | render/playback/sync 热路径禁止按 drift/PTS `vTaskDelay` [TASK_DELAY] 或 `portMAX_DELAY` [TIMEOUT_FOREVER] 硬等；用 drop/repeat/resample/resync | P1 | `av_clock_jitter_checker.py` | 同上 | 同上 |
| C27.5 | underrun/overrun handler 只允许插静音、重复/冻结帧、丢帧或低频 resync；禁止 `malloc` [HEAP_ALLOC]/`free` [HEAP_FREE]/`printf` [PRINTF]/`LOG_*` [LOG_WRITE] | P1 | `av_clock_jitter_checker.py` | 同上 | 同上 |
| C27.6 | 必须保留 drift_ms/drift_ppm、jitter_depth、水位、underrun/overrun、late/drop/insert、resync_count 遥测 | P2 | 人工 + checker 提醒 | 同上 | — |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 播放 5–10 分钟后 lip-sync 慢慢漂 | C27.1 主时钟错误，C27.3 漂移校正无上限 |
| 网络抖动后爆音 / 断续 / 恢复慢 | C27.2 jitter buffer 无水位，C27.5 underrun/overrun 路径不可预测 |
| 视频偶发卡一下但平均帧率正常 | C27.4 用 delay 硬等 PTS，C25.3 队列背压错误 |
| 现场无法判断是漂移还是丢包 | C27.6 缺 drift/jitter/drop/insert 遥测 |

---

## C28 — 媒体 DMA / Cache / 零拷贝 Buffer 生命周期

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C28.1 | Camera/I2S/LCD/codec DMA buffer 必须位于 DMA-capable 内存，并满足 cache line 或 DMA 控制器对齐；禁止普通 `malloc`/`pvPortMalloc` [HEAP_ALLOC] 作为媒体 DMA buffer | P0 | `av_dma_buffer_checker.py` + 人工 | [good_av_dma_buffer_lifecycle.c](../examples/good_av_dma_buffer_lifecycle.c) | [bad_av_dma_buffer_lifecycle.c](../examples/bad_av_dma_buffer_lifecycle.c) |
| C28.2 | DMA 写、CPU 读前必须 invalidate；CPU 写、DMA/LCD/codec 读前必须 clean；方向错等同坏帧风险 | P0 | `av_dma_buffer_checker.py` | 同上 | 同上 |
| C28.3 | 零拷贝 frame pool 必须有 owner/state/generation/release；consumer 未 release 前禁止 producer 复用 | P0 | `av_dma_buffer_checker.py` + 人工 | 同上 | 同上 |
| C28.4 | 跨任务 Queue 推荐传 buffer index/handle/descriptor；禁止裸 DMA 指针跨任务后 producer 侧继续读写或复用 | P1 | `av_dma_buffer_checker.py` + 人工 | 同上 | 同上 |
| C28.5 | cache clean/invalidate 起始地址向下 cache-line 对齐，长度向上覆盖完整 frame/stride/DMA half-buffer | P1 | `av_dma_buffer_checker.py` | 同上 | 同上 |
| C28.6 | 保留 cache_clean/cache_invalidate、stale_frame、reuse_before_release、buffer_overrun/underrun 等遥测，低频输出 | P2 | 人工 + checker 提醒 | 同上 | — |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| Camera preview 偶发旧帧 / 花屏 | C28.2 invalidate 缺失或 C28.5 范围未覆盖 stride |
| LCD flush 后颜色错乱 / 局部撕裂 | C28.2 clean 缺失，C28.1 buffer 不在 DMA-capable 区域 |
| 零拷贝帧偶发被覆盖 | C28.3 owner/generation 缺失，consumer 未 release 前复用 |
| Queue 满后坏帧或 use-after-free | C28.4 裸指针所有权不清，C2.4 失败路径未释放 |

---

## C29 — 模块契约

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C29.1 | 模块公开 API 必须声明可调用上下文：task / ISR / timer callback / LVGL thread；ISR 可调用路径必须单独命名或注释 | P0 | 人工 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | API 文档未说明上下文 |
| C29.2 | 模块 API 必须声明阻塞语义、最大等待时间、是否可重入；默认不得假设调用者知道内部等待点 | P0 | 人工 + `blocking_wait_checker.py` | 同上 | `module_read()` 内部无限等 Queue |
| C29.3 | 模块必须声明入参、出参、Queue payload、callback user_data 的所有权与释放方 | P1 | 人工 | 同上 | callback 传裸指针但未说明生命周期 |
| C29.4 | 模块必须声明 `init/start/stop/deinit` 合法顺序、重复调用行为和半初始化清理策略 | P1 | 人工 | 同上 | `stop()` 未说明 init 失败后能否调用 |
| C29.5 | 模块必须声明错误码语义：timeout/resource/config/bug 等分类，以及哪些错误可恢复 | P2 | 人工 | 同上 | 全部返回 `-1` |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 新人接手要 grep 半天才敢调用 API | C29.1/C29.2 缺上下文和阻塞契约 |
| Queue payload 泄漏或双 free | C29.3 契约缺所有权，联动 C2 |
| 偶发 stop 后不能再 start | C29.4 生命周期顺序不清，联动 C33 |

---

## C30 — 任务 / 队列拓扑表

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C30.1 | 多任务模块必须输出 task、priority、stack、queue、producer、consumer、timeout、backpressure、exit 的拓扑表 | P0 | 人工 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 只给散落 `xTaskCreate` [TASK_CREATE] |
| C30.2 | 每条 Queue 必须声明元素类型、payload 所有权、生产者和消费者；跨核/跨线程路径须注明边界 | P0 | 人工 | 同上 | 只看到 `xQueueCreate(8, sizeof(void*))` [QUEUE_CREATE] |
| C30.3 | 每条 Queue 必须声明深度、发送/接收 timeout 和满队列策略：drop-oldest/drop-newest/backpressure/overwrite | P1 | 人工 | 同上 | 满队列时无限等 |
| C30.4 | 每个 task 必须有退出条件、stop flag 或通知路径；禁止只能通过 reboot 终止 | P1 | 人工 | 同上 | while(1) 无退出和状态 |
| C30.5 | 拓扑表必须保留 queue high-water、drop、timeout 或 overflow 观测点 | P2 | 人工 | 同上 | 队列满无法复盘 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 队列满但不知道谁堵住 | C30.1-C30.3 缺拓扑与背压 |
| stop/deinit 卡住某任务 | C30.4 任务无退出条件 |
| 现场只知道“丢消息”不知道水位 | C30.5 缺队列观测 |

---

## C31 — 超时预算

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C31.1 | `xQueueReceive` [QUEUE_RECV]/`xQueueSend` [QUEUE_SEND]/`xSemaphoreTake` [SEM_TAKE]/`rtos_*` 等阻塞等待默认必须有限 timeout；禁止裸 `portMAX_DELAY` [TIMEOUT_FOREVER]/`WAIT_FOREVER` [TIMEOUT_FOREVER] | P0 | `blocking_wait_checker.py` + 人工 | `pdMS_TO_TICKS(20)` + 失败处理 | `xQueueReceive(..., portMAX_DELAY)` [QUEUE_RECV/TIMEOUT_FOREVER] |
| C31.2 | 网络、TLS、DNS、文件 IO 等等待必须有 deadline、错误分类和失败恢复路径 | P0 | 人工 | [network_resilience.txt](../prompts/network_resilience.txt) | `recv()` [SOCKET_RECV] 无超时 |
| C31.3 | mutex/semaphore 等待必须声明持锁路径和超时处理；持锁时禁止再做长 IO | P1 | `blocking_wait_checker.py` + 人工 | timeout 后统计并降级 | 持锁 TLS handshake [TLS_HANDSHAKE] |
| C31.4 | 永久等待只允许 dedicated idle/daemon consumer；必须注释说明不会持锁、不会阻塞 stop/deinit，并有 health counter | P1 | 人工 | `/* allowed C31.4: idle consumer */` | 普通业务任务永久等 |
| C31.5 | timeout/drop/retry 必须保留低频遥测计数，避免只靠临时日志判断 | P2 | 人工 | `stats.rx_timeout++` | timeout 后 silent continue |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 假死但 WDT 未复位 | C31.1/C31.4 永久等待或无 health counter |
| 断网后业务线程卡住 | C31.2 网络等待无 deadline |
| 偶发锁死 | C31.3 持锁路径无 timeout 或嵌套长 IO |

---

## C32 — 可观测性优先

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C32.1 | 关键模块必须暴露 `state`、`last_error`、`last_error_line` 或等价字段 | P1 | 人工 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 只打自然语言日志 |
| C32.2 | 关键链路必须计数 timeout/drop/retry/reconnect/overflow/underrun 等现场指标 | P1 | 人工 | 同上 | 只有平均成功率 |
| C32.3 | 任务必须可采集 stack high-water、queue high-water、heap free/min/largest 等资源水位 | P1 | 人工 + `stack_calculator.py` | 同上 | 只看总 free heap |
| C32.4 | init/connect/handshake/decode/render/flush 等阶段必须保留 max time 或最近耗时 | P2 | 人工 | 同上 | 性能尖峰不可定位 |
| C32.5 | 现场 dump 必须能还原最近关键事件，且脱敏、限频、可关闭 | P2 | 人工 | `logging_management_constraints.md` | 量产 DEBUG 全开或完全无日志 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 现场复现不了，也无法判断处于哪个状态 | C32.1 缺 state/last_error |
| “偶发丢包/爆音/掉帧”只有用户描述 | C32.2 缺计数器 |
| 资源问题无法判断是栈、水位还是碎片 | C32.3 缺资源水位 |

---

## C33 — 生命周期对称

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C33.1 | `init/open/start/enable/power_on/clock_enable/dma_start` 必须有对应 `stop/disable/close/deinit/power_off/clock_disable/dma_stop` | P0 | 人工 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | init 后无 deinit |
| C33.2 | `alloc/create/register/attach/subscribe` 必须有对应 `free/delete/unregister/detach/unsubscribe` | P0 | 人工 | 同上 | 注册回调后 never unregister |
| C33.3 | 多资源函数必须统一 `cleanup:`；异常路径和正常路径复用同一批 release helper | P1 | 人工 | [error_handling.txt](../prompts/error_handling.txt) | early return 泄漏 socket/timer |
| C33.4 | `stop/deinit` 必须可重入，并能处理半初始化状态；重复调用不得崩溃 | P1 | 人工 | [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) | deinit 未判空直接 free |
| C33.5 | lifecycle 状态与 release 结果必须低频可观测，便于定位 stop/start 竞态 | P2 | 人工 | `state=STOPPING release_ok=...` | stop 静默失败 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| start/stop 多次后泄漏或崩溃 | C33.1/C33.2 acquire/release 不对称 |
| init 中途失败后 deinit HardFault | C33.4 半初始化路径未处理 |
| 断线重连后重复回调 | C33.2 未 unregister/unsubscribe |

---

## C34 — 热路径禁区

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C34.1 | ISR/DMA callback/LVGL flush/audio/video hot path/control loop 禁止阻塞等待、无界 IO、`portMAX_DELAY` [TIMEOUT_FOREVER] | P0 | `isr_safety_checker.py` / media checkers + 人工 | notify/enqueue | callback 内 `xQueueSend(..., portMAX_DELAY)` [QUEUE_SEND/TIMEOUT_FOREVER] |
| C34.2 | hot path 禁止 `malloc` [HEAP_ALLOC]/`free` [HEAP_FREE]/`pvPortMalloc` [HEAP_ALLOC]/`vPortFree` [HEAP_FREE]/`printf` [PRINTF]/`LOG_*` [LOG_WRITE] 高频打印、file IO | P1 | `logging_checker.py` / media checkers + 人工 | counter + 低频 dump | 每帧 malloc + LOG |
| C34.3 | hot path 禁止 `cJSON_Parse` [PARSE]、codec create/open、TLS handshake [TLS_HANDSHAKE]、复杂协议解析 | P1 | 人工 | 任务上下文异步处理 | 收包回调直接 parse 大 JSON |
| C34.4 | hot path 只允许 `notify/enqueue/set flag/increment counter` 等 O(1) 轻量操作 | P1 | 人工 | `xTaskNotifyFromISR` [TASK_NOTIFY_GIVE] | callback 直接调 UI/网络/FS |
| C34.5 | hot path 必须声明预算、峰值耗时与丢弃计数，便于判断是否超过实时窗口 | P2 | 人工 | `max_process_us/drop_count` | 只有平均耗时 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 周期性延迟尖峰 / 音频爆音 | C34.1/C34.2 hot path 阻塞或分配 |
| 收包后 UI 卡顿 | C34.3/C34.4 回调内重活太多 |
| 平均耗时正常但偶发超时 | C34.5 缺峰值耗时和 drop 计数 |

---

## C35 — 关键路径预算表
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C35.1 | 启动、联网、音频、视频、UI、OTA、低功耗唤醒等关键路径必须声明 stage budget | P0 | 人工 | `boot: fs<=120ms, net<=2s` | 只写“尽快初始化” |
| C35.2 | 每个关键阶段必须声明 owner、timeout、fallback 和 metric | P0 | 人工 | `owner=net_task timeout=3s fallback=offline metric=net_connect_max_ms` | timeout 后 silent fail |
| C35.3 | 关键路径禁止无证据串行长 IO；必须评估并行化、异步化或延迟加载 | P1 | 人工 | UI 先显示，云连接异步 | boot 阶段同步 TLS + 文件扫描 |
| C35.4 | 关键路径必须记录 max time、timeout/drop/retry counter | P1 | 人工 | `stats.boot_net_max_ms` | 只看平均耗时 |
| C35.5 | 预算表必须随需求、配置、板级差异变化同步更新 | P2 | 人工 | profile 中记录板级预算差异 | 换板后仍沿用旧预算 |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| boot 偶发慢但日志看不出卡在哪 | C35.1/C35.4 缺 stage budget 和 max time |
| 加一个功能后启动慢 3 秒 | C35.3 长 IO 未异步化 |
| A 板正常，B 板超时 | C35.5 预算未随板级差异更新 |

---

## C36 — 数据拷贝预算
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C36.1 | 跨 task、跨核、DMA、网络、音视频 frame 必须声明数据移动策略 | P0 | 人工 | Queue 传 frame handle | Queue 传整帧结构体 |
| C36.2 | 大 payload 默认传 descriptor/index/handle，禁止无理由传大结构体进 Queue | P0 | `efficiency_budget_checker.py` + 人工 + C2 | `frame_id` + pool owner | `xQueueSend(q, &frame, ...)` |
| C36.3 | 每条数据路径必须声明 copy count、buffer owner 和 release 方 | P1 | `efficiency_budget_checker.py` + 人工 | `copy=1 producer alloc consumer release` | 多处 memcpy 不知道谁释放 |
| C36.4 | DMA/cache 路径必须声明 clean/invalidate、对齐和 ownership transfer | P1 | 人工 + C28 | cache line aligned clean before TX | DMA 读 cache 脏数据 |
| C36.5 | buffer pool 满时必须有 drop/backpressure/retry 策略和计数 | P2 | `efficiency_budget_checker.py` + 人工 | `pool_full_drop++` | 满池后 malloc 扩容 |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| 音视频延迟随时间增加 | C36.2/C36.5 拷贝过多或满池无策略 |
| DMA 花屏/旧帧 | C36.4 cache/owner 未声明 |
| 堆碎片越来越严重 | C36.1/C36.3 运行期拷贝和分配无预算 |

---

## C37 — 背压与降级策略
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C37.1 | 高频 producer、网络、音视频、日志、UI 队列必须声明背压策略 | P0 | 人工 | `drop-oldest + count` | 满队列无限等 |
| C37.2 | 满队列禁止无限等待，必须选择 drop/coalesce/overwrite/backpressure | P0 | `blocking_wait_checker.py` + `efficiency_budget_checker.py` + 人工 | `xQueueOverwrite` [QUEUE_OVERWRITE] 状态类事件 | `portMAX_DELAY` [TIMEOUT_FOREVER] 等消费 |
| C37.3 | 降采样、降帧率、降码率、暂停非关键任务必须有触发条件 | P1 | 人工 | queue high-water > 80% 降帧 | 卡顿时临时改 delay |
| C37.4 | retry 必须 bounded，并带 backoff 或 circuit breaker | P1 | `efficiency_budget_checker.py` + 人工 | `retry<=5, backoff<=60s` | while retry forever |
| C37.5 | 背压、降级、恢复必须有低频 telemetry | P2 | 人工 | `degrade_enter_count` | 降级后现场不可见 |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| 队列满后系统假死 | C37.1/C37.2 背压策略缺失 |
| 网络差时 CPU 被 retry 打满 | C37.4 retry 无上限 |
| 降级发生但没人知道 | C37.5 缺 telemetry |

---

## C38 — 故障隔离与自动恢复
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C38.1 | 关键模块必须声明 task/driver/protocol/cloud/UI 故障域 | P0 | 人工 | WSS 断链不影响 LVGL task | 一个错误全局 reset |
| C38.2 | 错误必须分类 recoverable/fatal，并声明恢复动作 | P0 | 人工 | timeout reconnect, config fatal | 全部返回 `-1` |
| C38.3 | retry/backoff/max retry/circuit open time 必须有上限 | P1 | 人工 | exponential backoff capped | 无限重连 |
| C38.4 | supervisor/watchdog/health counter 必须能发现卡死或半死 | P1 | 人工 | task heartbeat + stale detect | 任务还活着但不处理事件 |
| C38.5 | 恢复失败必须进入降级模式或安全停机，而非静默失败 | P2 | 人工 | offline mode + UI status | 失败后继续假装在线 |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| 外设异常后只能整机重启 | C38.1/C38.2 故障域和恢复动作不清 |
| 任务未死但业务不动 | C38.4 缺 health counter |
| 重连风暴 | C38.3 缺 backoff/circuit breaker |

---

## C39 — 配置矩阵约束
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C39.1 | Kconfig、feature flag、board、SDK 差异必须进入配置矩阵 | P0 | 人工 | `feature -> dependency -> resource` 表 | 宏散落在业务代码 |
| C39.2 | 每个 feature 必须声明 dependency、resource、default、test mode | P0 | 人工 | camera 依赖 DMA+PSRAM | 打开宏后才发现缺资源 |
| C39.3 | `#ifdef` 必须归类 platform/board/feature/debug，禁止无名散落 | P1 | 人工 | `CONFIG_FEATURE_AUDIO` | `#ifdef TEMP_FIX` |
| C39.4 | 配置变化必须同步 bring-up checklist、profile 和回归样本 | P1 | 人工 | 新 feature 同步 profile | 改宏不改测试 |
| C39.5 | 无效配置组合必须在 build 或初始化阶段 fail fast | P2 | 人工 | `#error` / init config check | 运行到一半崩溃 |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| 某配置组合没人敢改 | C39.1/C39.2 缺矩阵 |
| `#ifdef` 越写越多 | C39.3 未归类 |
| 新板编译过但运行崩 | C39.5 无效组合未 fail fast |

---

## C40 — 一键复现闭环
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C40.1 | 新模块、bring-up、复杂 bug 必须提供 build/flash/monitor 命令 | P0 | 人工 | `idf.py build flash monitor` 模板 | 只说“本地能跑” |
| C40.2 | crash/core dump 解码必须声明 symbol path、工具和输入日志 | P0 | 人工 | `addr2line -e build/app.elf ...` | 只有截图 |
| C40.3 | 最小配置、测试入口、预期输出必须可复制执行 | P1 | 人工 | test mode + expected log | 需要口头步骤 |
| C40.4 | 失败日志保存位置、脱敏规则和保留时间必须明确 | P1 | 人工 + C14 | `logs/failure_xxx.txt` | 日志散在聊天里 |
| C40.5 | 复现命令必须随平台脚本或 SDK 版本变化更新 | P2 | 人工 | SDK 升级同步脚本 | 命令过期无人发现 |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| 新人半天跑不起来 | C40.1/C40.3 缺一键复现 |
| crash 地址没人能解 | C40.2 缺 symbol/decode |
| 现场日志无法复盘 | C40.4 缺保存和脱敏规则 |

---

## C41 — 回归样本优先
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C41.1 | 新约束、新 checker、新 bugfix 必须优先沉淀 bad 样本 | P0 | 人工/自测 | `bad_timeout_budget.c` | 只改规则无样本 |
| C41.2 | 每个 bad 样本必须有对应 good 样本或推荐修复模式 | P0 | 人工/自测 | good/bad 成对 | 只知道错不知道怎么改 |
| C41.3 | 样本必须通用化，不包含产品名、客户名、密钥或私有路径 | P1 | residue scan | generic fixture | 带客户业务名 |
| C41.4 | checker/self-test/manual checklist 必须引用样本并说明预期结果 | P1 | `run_review.py --self-test` | expected exit 1 | 样本未纳入验证 |
| C41.5 | 样本覆盖失败路径、边界条件和恢复路径，不只覆盖 happy path | P2 | 人工 | timeout + recovery | 只测成功路径 |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| 同类 bug 反复出现 | C41.1/C41.2 缺回归样本 |
| checker 改坏没人发现 | C41.4 未纳入 self-test |
| 样本不能公开复用 | C41.3 未通用化 |

---

## C42 — 板级资源契约
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C42.1 | GPIO、DMA、clock、IRQ、cache、heap、PSRAM 资源必须声明 owner | P0 | 人工 | `i2s0 owned by audio` | 两模块抢 DMA |
| C42.2 | 板级资源冲突必须有检查方式或审查表 | P0 | 人工 | pinmux/resource table | 到板上才发现冲突 |
| C42.3 | DMA/cache/heap capability 必须声明对齐、cacheability 和分配域 | P1 | 人工 + C28 | DMA buffer internal aligned | PSRAM buffer 给 DMA |
| C42.4 | IRQ priority、ISR-safe API、跨核访问边界必须明确 | P1 | 人工 + C4/C17 | ISR only notify | ISR 调非安全 API |
| C42.5 | clock/power domain 生命周期与低功耗约束必须进入 platform/profile | P2 | 人工 | sleep 前关 clock | 低功耗后外设不恢复 |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| 换板后 GPIO/DMA 冲突 | C42.1/C42.2 缺 resource owner |
| DMA 偶发数据错 | C42.3 cache/heap capability 不清 |
| 低功耗唤醒后外设异常 | C42.5 clock/power domain 未建模 |

---

## C43 — 锁预算与优先级反转防护
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C43.1 | mutex/recursive mutex 等锁等待必须有限 timeout 或声明 dedicated daemon 例外 | P0 | `lock_budget_checker.py` + 人工 | `xSemaphoreTake(m, pdMS_TO_TICKS(2))` [SEM_TAKE] | `xSemaphoreTake(m, portMAX_DELAY)` [SEM_TAKE/TIMEOUT_FOREVER] |
| C43.2 | 持锁期间禁止网络/TLS/Flash/file IO/cJSON parse/delay/codec open 等阻塞或重活 | P0 | `lock_budget_checker.py` + 人工 | 先复制状态再解锁做 IO | 持锁调用 `mbedtls_ssl_read()` [TLS_READ] |
| C43.3 | 保护共享资源必须使用带优先级继承的 mutex，禁止 binary semaphore 伪装 mutex | P1 | `lock_budget_checker.py` + 人工 | `xSemaphoreCreateMutex()` [MUTEX_CREATE] | `xSemaphoreCreateBinary()` [SEM_CREATE] 保护 shared state |
| C43.4 | 多锁嵌套必须声明 `lock_order` / `lock_rank` 并保持全局一致 | P1 | `lock_budget_checker.py` + 人工 | `lock_order: NET -> STATE` | 函数内连续拿两个锁无顺序说明 |
| C43.5 | ISR/callback/LVGL flush/audio/video hot path 禁止拿 mutex | P0 | `lock_budget_checker.py` + C4/C34 | ISR 只 notify | callback 中 `xSemaphoreTake()` [SEM_TAKE] |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| 偶发死锁、WDT、UI 卡死但平均耗时正常 | C43.1/C43.2/C43.4 |
| 高优先级音频/视频任务被低优先级后台拖住 | C43.3/C43.5 + C15 |
| 网络差时系统整体抖动 | C43.2 + C31/C37 |

---

## C44 — 临界区/关中断预算
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C44.1 | `taskENTER_CRITICAL`、`portDISABLE_INTERRUPTS` [CRITICAL_ENTER]、`__disable_irq` [CRITICAL_ENTER] 等区域必须短小并声明 `irq_off` / critical budget | P1 | `critical_section_checker.py` + 人工 | `critical_budget: max_irq_off_us=3` | 大段业务逻辑包在 critical section |
| C44.2 | 临界区/关中断期间禁止阻塞、分配、日志、`memcpy`、Flash/file IO、cJSON parse、codec open 等重活 | P0 | `critical_section_checker.py` + 人工 | 只改寄存器/flag/counter | 关中断后 `printf` [PRINTF] / `pvPortMalloc` [HEAP_ALLOC] / `memcpy` |
| C44.3 | 每个 enter/disable 路径必须保证 exit/enable，禁止提前 return 泄漏关中断状态 | P0 | `critical_section_checker.py` + 人工 | `cleanup:` 统一恢复 IRQ | critical section 内 `return -1` |
| C44.4 | 临界区/关中断期间禁止 busy loop / poll loop | P1 | `critical_section_checker.py` + 人工 | 设置状态后退出，由 task 等待 | `while (!ready) {}` |
| C44.5 | ISR/callback/LVGL flush/audio/video hot path 禁止制造长临界区或再次关中断 | P0 | `critical_section_checker.py` + C4/C34 | ISR 只 notify/counter | callback 中 `__disable_irq()` [CRITICAL_ENTER] 包业务 |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| 音频爆音、视频掉帧、控制环 jitter | C44.1/C44.2/C44.4 + C34 |
| WDT 但任务栈和 heap 都正常 | C44.3/C44.5 |
| 偶发中断丢失或外设超时 | C44.1/C44.5 + C4 |

---

## C45 — 传感器集成契约
| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C45.1 | 传感器 `init/probe` 必须有 datasheet/register map 依据，并校验 `WHO_AM_I` / `chip_id` / `device_id` | P0 | `sensor_integration_checker.py` + 人工 | [good_sensor_integration.c](../tools/fixtures/good_sensor_integration.c) | [bad_sensor_integration.c](../tools/fixtures/bad_sensor_integration.c) |
| C45.2 | I2C/SPI 传感器事务必须有有限 timeout、retry/backoff 和错误分类；禁止默认永久等待或 silent fail | P0 | `sensor_integration_checker.py` + C31 | 同上 | 同上 |
| C45.3 | data-ready/DRDY/status/fifo 等待必须事件驱动或有界轮询；禁止 tight poll / magic delay | P1 | `sensor_integration_checker.py` + 人工 | `xTaskNotifyWait(..., pdMS_TO_TICKS(20))` [TASK_NOTIFY_TAKE] | `while (!(status & READY)) { read_reg(); }` |
| C45.4 | sample 输出必须携带 timestamp、单位、量程、scale/offset 或校准版本；禁止 raw register value 直接跨模块传播 | P1 | `sensor_integration_checker.py` + C32 | `value_milli_unit + timestamp_ms + scale_ppm` | `out->raw_value = raw16` |
| C45.5 | calibration/self-test/warm-up 必须有生命周期与失效策略，不得放在采样 hot path | P2 | `sensor_integration_checker.py` + C33/C34 | start 前校准，配置变更后失效重做 | 每次 read 都 `calibrate_sensor_offsets()` |

**症状表**：
| 症状 | 可能约束 |
|------|----------|
| I2C/SPI 偶发卡死或 WDT | C45.2 + C31/C44 |
| 传感器读数跳变、单位混乱、融合结果漂移 | C45.1/C45.4 |
| 采样周期抖动、控制环 jitter | C45.3/C45.5 + C34 |

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
