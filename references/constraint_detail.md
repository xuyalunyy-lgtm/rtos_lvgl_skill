# 铁律细粒度约束矩阵（L2+ 按需加载）

Agent 在 L2 Code Review、Crash 诊断、L3 架构输出时读取本文件。每条约束有唯一 **ID**（`C#.#`），违规报告与 checklist 须引用 ID。

> C1–C25，24 个约束域，131 条规则。

总纲摘要 → [core_rules.md](core_rules.md)

---

## C1 — LVGL 线程安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C1.1 | Model / 网络 / 音频 / Presenter **禁止**直接调用 `lv_obj_*`、`lv_label_*`、`lv_bar_*` 等 UI API | P0 | `lvgl_thread_checker.py` | `good_presenter_consumer.c` `view_post_set_text` | `bad_lvgl_cross_thread.c` |
| C1.2 | UI 修改**仅**在运行 `lv_timer_handler()` 的 LVGL 任务，或 `lv_async_call` 回调内 | P0 | 人工 + checker | `good_mvp_pattern.c` | — |
| C1.3 | `lv_async_call` 的 `user_data` 须堆分配，**仅在回调内** `vPortFree`；投递后调用方不得再读写 | P0 | 人工 | `good_mvp_pattern.c` | — |
| C1.4 | 互斥锁方案：`xSemaphoreTake` **必须**带超时并检查返回值；禁止 `portMAX_DELAY` | P1 | 人工 | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | — |
| C1.5 | 持 `g_lvgl_mutex` 期间禁止 `vTaskDelay`、`xQueueReceive(..., portMAX_DELAY)`、阻塞网络 IO | P0 | 人工 + [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | — | `bad_wss_blocking.c`（持锁 recv） |
| C1.6 | 锁顺序：若同时需要网络锁与 LVGL 锁，**先网络后 LVGL**（L2→L3） | P1 | 人工 | [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) | — |
| C1.7 | 高频 UI 刷新（波形/进度）须节流，避免 `lv_async_call` 队列撑爆 | P2 | 人工 | — | — |

---

## C2 — Queue payload 所有权

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C2.1 | Queue **禁止**传递 `cJSON *` 或含 `cJSON *` 字段的 struct | P0 | `queue_ownership_checker.py` | `good_wss_json_parse.c` | `bad_queue_stack_pointer.c` |
| C2.2 | Queue **禁止**传递栈上 buffer 指针（`&local_buf`、栈数组地址） | P0 | 同上 | `good_wss_json_parse.c` heap payload | `bad_queue_stack_pointer.c` |
| C2.3 | 堆 payload：Model `pvPortMalloc` → Presenter 消费后 `vPortFree`；**禁止**双重 free | P0 | 同上 + 人工 | `good_presenter_consumer.c` | — |
| C2.4 | `xQueueSend` 失败时 Model **仍拥有** payload，必须 `vPortFree` | P0 | 人工 | [memory_ownership.txt](../prompts/memory_ownership.txt) | — |
| C2.5 | `xQueueSend` 成功后 Model **禁止**再访问或释放 payload | P1 | 人工 | `good_wss_json_parse.c` | — |
| C2.6 | 所有权转移须在代码或注释标明「谁 alloc / 谁 free」 | P2 | 人工 | `good_presenter_consumer.c` | — |
| C2.7 | Queue 深度与满队列策略（丢帧/非阻塞/Overwrite）须在架构文档写明，禁止 magic number | P1 | 人工 | [queue_event_bus.txt](../prompts/queue_event_bus.txt) | — |
| C2.8 | 禁止传 `lv_obj_t *` 进 Queue（生命周期绑定 UI 任务） | P0 | 人工 | `lv_async_call` 传文本副本 | — |

---

## C3 — cJSON 防泄漏

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C3.1 | 每个 `cJSON_Parse` 在**同一函数**内有且仅有一个 `cJSON_Delete` 出口 | P0 | `cjson_leak_checker.py` | `good_wss_json_parse.c` | `bad_cjson_leak.c` |
| C3.2 | 多出口解析须用 `goto cleanup` 或 `do { } while(0)` 统一 Delete | P0 | 同上 | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) | `bad_cjson_leak.c` early return |
| C3.3 | 进 Queue 前必须 `cJSON_Delete(root)`，仅传 plain heap buffer | P0 | checker + 人工 | `good_wss_json_parse.c` | — |
| C3.4 | 循环内 Parse 每次迭代必须 Delete；禁止高频 Parse+Delete 无节流 | P1 | checker | — | `bad_cjson_leak.c` 循环 |
| C3.5 | `strdup` / `pvPortMalloc` 失败路径不得泄漏已 Parse 的 root | P1 | checker | — | `bad_cjson_leak.c` |
| C3.6 | L2+ 审查须运行 `python tools/cjson_leak_checker.py <file>` 或 `--dir ./src` | P2 | 流程 | — | — |

---

## C4 — ISR / DMA / 音频

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C4.1 | ISR / `HAL_*Callback` 内**仅** `*FromISR` 后缀 FreeRTOS API | P0 | `isr_safety_checker.py` | `fixtures/good_isr.c` | `bad_isr_blocking.c` |
| C4.2 | ISR 须声明 `BaseType_t xHigherPriorityTaskWoken = pdFALSE` 并在末尾 `portYIELD_FROM_ISR` | P0 | 同上 | `fixtures/good_isr.c` | — |
| C4.3 | ISR 禁止：`vTaskDelay`、`xSemaphoreTake/Give`（非 FromISR）、`printf`、`malloc`/`pvPortMalloc`、`cJSON_Parse` | P0 | 同上 | — | `bad_isr_blocking.c` |
| C4.4 | I2S Mic/Spk 须 Ping-Pong 双缓冲，缓冲区 4 字节对齐 | P1 | 人工 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | — |
| C4.5 | 音频任务相对优先级 **高于** LVGL 与 WSS（见 core_rules 优先级表） | P1 | `stack_calculator.py` + 平台档 | — | — |
| C4.6 | 音频处理结果经 Queue 送 Presenter，**禁止** ISR/音频任务直接改 UI | P0 | 人工 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | — |
| C4.7 | ISR 禁止获取 mutex（`xSemaphoreTake` 任何变体） | P0 | checker | — | — |
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
| C7.4 | 长连接 / 高频路径优先固定块或对象池；禁止每帧 / 每包 `malloc`+`free` | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.5 | WSS/TLS 任务栈须按握手峰值实测，**不得低于 4096 bytes**（建议 6144–8192） | P0 | `stack_calculator.py` + 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |
| C7.6 | 缩 LwIP / mbedTLS / LVGL 池**每步**须冒烟 WiFi + WSS + 业务闭环 | P1 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.7 | 主工程只链入**一个** TLS 栈（mbedtls / wolfssl / psa 择一） | P1 | 人工 | — | — |
| C7.8 | ISR / DMA / 实时路径缓冲须在 SRAM（或平台文档允许的 fast RAM）；禁止无依据默认放 PSRAM / 外部慢速区 | P1 | 人工 | `platforms/bk.md` 等 | — |
| C7.9 | 重连 / 错误恢复禁止 tight loop 反复 TLS 握手；须指数退避（cap 建议 60s） | P1 | 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |

---

## C8 — 启动顺序 / 阻塞 / 看门狗

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C8.1 | Queue + Presenter Looper **须**在注册 WiFi/WSS/网络事件回调之前创建并就绪 | P0 | 人工 | [good_boot_sequence.c](../examples/good_boot_sequence.c) | `bad_wss_blocking.c` |
| C8.2 | WSS/TLS **须**在 WiFi 获 IP 之后；证书校验 **须** SNTP 同步完成 | P0 | 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |
| C8.3 | Presenter `xQueueReceive` **禁止**默认 `portMAX_DELAY`；须有限 timeout + 循环 | P1 | 人工 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) | — |
| C8.4 | LVGL 任务 `lv_timer_handler` 循环内**禁止**网络/TLS/长 mutex/除固定 tick 外的阻塞 | P0 | 人工 | [good_mvp_pattern.c](../examples/good_mvp_pattern.c) | `bad_wss_blocking.c` |
| C8.5 | 模块 reconnect **须**幂等：同任务禁止重复 `xTaskCreate`；用句柄 + 状态机/Notify | P1 | 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | — |
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
| C10.5 | 语音会话 **generation** 丢弃 stale 的 FINISHED、timer 回调 | P1 | 代码审查 | 同上 | cancel 后旧回调仍 capture |
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
| C12.1 | FreeRTOS API（`xTaskCreate`/`xQueueCreate`/`pvPortMalloc`）返回值必须检查 | P0 | `return_check_checker.py` | `error_handling.txt` 模板 | [bad_unchecked_return.c](../examples/bad_unchecked_return.c) |
| C12.2 | malloc 失败须有 fallback，禁止 NULL 解引用 | P0 | 同上 | 同上 | NULL 直接 memcpy → HardFault |
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

---

## C15 — 任务优先级与通信

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C15.1 | 相邻任务优先级差 ≥2 | P1 | 人工 | `PRIO_WSS = MAX-3, PRIO_LVGL = MAX-5` | `PRIO_WSS=5, PRIO_LVGL=6` |
| C15.2 | 共享资源用 mutex（优先级继承），禁止 binary semaphore 保护 | P1 | 人工 | `xSemaphoreCreateMutex()` | `xSemaphoreCreateBinary()` 保护共享变量 |
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
| heap 持续下降 | C3.1–C3.5, C2.4, **C7.2**（先修泄漏再缩池） |
| TLS 握手 fail / 反复断线 | C8.2, C7.5–C7.9 + [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) |
| WDT / task watchdog | **C8.3–C8.6**, C1.5, C4.7 + [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) |
| 启动后首包丢失 / Queue 满 | **C8.1** |
| 缩池 / 关模块后功能异常 | **C7.6** + [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) |
| 优化建议无数据支撑 | **C7.1** |
| 仓库含明文密钥 / token 泄露 | **C9.1–C9.4** + `secret_scan_checker.py` |
| 录音失效 / ASR 空 / 第二轮听不见 | **C10.1–C10.5** + [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) |
| 唤醒叮后麦幅骤降 / tap peak 塌陷 | **C10.1, C10.2** |
| NULL 解引用 / HardFault @ malloc | **C12.1, C12.2** + [error_handling.txt](../prompts/error_handling.txt) |
| 资源泄漏（socket/fd 未释放） | **C12.4**（early return 不 cleanup） |
| 裸 printf / 日志洪水 | **C14.1, C14.3** + [logging_debug.txt](../prompts/logging_debug.txt) |
| 日志含明文密码/token | **C14.4, C9.3** |
| timer 全停 / daemon 卡死 | **C16.1**（timer 回调阻塞）
| 跨核数据竞争 / mailbox 队列满 | **C17.1, C17.2** + [multi_core_ipc.txt](../prompts/multi_core_ipc.txt) |
| 唤醒后状态丢失 / 重新初始化 | **C21.1, C21.2** + [low_power_management.txt](../prompts/low_power_management.txt) |
| 睡眠后功耗不降 / 外设漏电 | **C21.4**（外设未断电） |
| tickless idle 后音频卡顿 | **C21.3**（高频任务受影响） |

---

## C18 — 外设驱动安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C18.1 | GPIO 方向必须在使用前配置（gpio_config 先于 gpio_set_level） | P0 | `peripheral_driver_checker.py` | `gpio_config()` → `gpio_set_level()` | 未 config 直接 set_level |
| C18.2 | I2C 设备地址必须来自 datasheet，禁止硬编码猜测 | P1 | `peripheral_driver_checker.py` | `#define OLED_ADDR 0x3C /* datasheet */` | `#define OLED_ADDR 0x60` 无依据 |
| C18.3 | SPI 时钟模式（CPOL/CPHA）必须匹配从设备 datasheet | P1 | 人工 | `.mode = 0` 与 Flash 匹配 | `.mode = 2` 与 Flash 不匹配 |
| C18.4 | DMA 通道分配须文档化，同一通道不可被两个外设同时使用 | P1 | 人工 | DMA 通道分配表 | I2S 和 SPI 共享 DMA 通道 |
| C18.5 | ADC 引脚必须配置为模拟输入模式，禁用上拉/下拉 | P2 | 人工 | `adc1_config_channel_atten()` | ADC 引脚同时配置为数字输出 |
| C18.6 | PWM 频率与分辨率互斥，须根据应用选择 | P2 | 人工 | 5kHz/13-bit（电机） | 100kHz/7-bit（亮度不够） |

---

## C19 — Flash / NVS / 状态持久化

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C19.1 | NVS 写入后必须 `nvs_commit()` + 检查返回值 | P0 | `flash_nvs_checker.py` | `nvs_set_str` → `nvs_commit` → `nvs_close` | 不 commit 不检查返回值 |
| C19.2 | Flash 擦写期间禁止读取同分区 | P1 | 人工 | 擦写前关闭读句柄 | 同时 erase + read NVS |
| C19.3 | OTA 首次启动必须调用 `mark_valid_cancel_rollback` | P1 | 人工 | `app_main` 中调用 | 未调用，重启后回滚 |
| C19.4 | OTA 产品分区表须含 `ota_0` + `ota_1`；NVS 分区不可删除 | P1 | 人工 | `partitions.csv` 含 ota_0/ota_1 | 缺 ota_1 分区 |
| C19.5 | Flash 高频写入场景须做磨损均衡（NVS blob API / 缓冲写入） | P2 | 人工 | 每 5 分钟批量写入 | 每秒写 NVS |

---

## C20 — 网络韧性

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C20.1 | WiFi/WSS 断线重连必须有指数退避（1s→2s→…→60s cap） | P0 | `network_resilience_checker.py` | `WIFI_RECONNECT_BASE_MS * (1 << retry)` | 立即 `esp_wifi_connect()` tight loop |
| C20.2 | 所有阻塞网络操作（recv/send/connect）必须有有限超时 | P0 | `network_resilience_checker.py` | `setsockopt(SO_RCVTIMEO, 10s)` | `recv(sock, buf, len, 0)` 无超时 |
| C20.3 | DNS 解析失败必须处理，不可直接崩溃 | P1 | 人工 | `getaddrinfo` 返回值检查 + 重试 | `getaddrinfo` 失败直接 HardFault |
| C20.4 | TLS 握手失败须区分错误类型（证书无效 vs 超时 vs 服务端拒绝） | P1 | 人工 | 按 mbedTLS 错误码分类处理 | 所有 TLS 错误统一重试 |
| C20.5 | 网络断线时业务必须有降级策略（离线模式） | P1 | 人工 | `NET_MODE_OFFLINE` + 本地功能继续 | 断线后产品完全不可用 |

---

## C21 — 低功耗管理

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C21.1 | 深度睡眠前必须保存运行状态到 NVS/Flash（`nvs_commit` + 检查返回值） | P0 | `low_power_checker.py` | `nvs_set_u8` → `nvs_commit` → `esp_deep_sleep_start` | 直接 `esp_deep_sleep_start` 丢失状态 |
| C21.2 | 唤醒后须检查 `wakeup_cause`，恢复状态而非重新初始化 | P1 | 人工 | `esp_sleep_get_wakeup_cause()` 分支处理 | 唤醒后无条件 full_init |
| C21.3 | Tickless Idle 配置须确认高频任务不受唤醒延迟影响 | P1 | 人工 | `CONFIG_FREERTOS_USE_TICKLESS_IDLE=y` + 高频任务用独立定时器 | 盲开 tickless 导致音频 tick 漂移 |
| C21.4 | 深度睡眠前必须逐个关闭外设电源（LCD 背光/音频 DAC/WiFi/PSRAM） | P1 | `low_power_checker.py` | `power_down_peripherals()` 逐个关闭 | 仅 `esp_deep_sleep_start` 不关外设 |
| C21.5 | 多唤醒源（timer/ext0/ext1/PIR）同时配置时须确认 GPIO 无冲突 | P2 | 人工 | 唤醒源分配表 + GPIO 唯一性检查 | 同一 GPIO 配 ext0 + ext1 冲突 |

---

## C23 — 显示驱动安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C23.1 | LCD 初始化时序必须严格遵循 datasheet（复位脉宽≥10ms、复位后等待≥120ms、Sleep Out 后等待≥120ms） | P0 | 人工 | [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) | 复位后立即发命令 |
| C23.2 | 背光控制必须用 PWM（非 GPIO 开关），支持亮度调节和渐变；低功耗时关闭背光电源 | P1 | 人工 | `ledc_set_duty` + `gpio_set_level(BL_EN, 0)` | `gpio_set_level(BL_PIN, 1)` 仅开/关 |
| C23.3 | `lv_timer_handler` 调用频率必须匹配面板刷新率（60Hz→16ms，30Hz→33ms）；禁止过快调用浪费 CPU | P1 | 人工 | `vTaskDelay(1000/REFRESH_RATE)` | `vTaskDelay(1)` 1ms 调用 |
| C23.4 | 显示刷新必须有撕裂防护（TE 信号同步 / 双缓冲 / 直接模式）；禁止单缓冲无同步写入 | P1 | 人工 | `esp_lcd_panel_io_tx_param(0x35)` TE 信号 | 单缓冲直接写入 |
| C23.5 | 帧缓冲大小必须根据 RAM 可用性选择：PSRAM 可用→全屏双缓冲；RAM 不足→部分刷新（1/5 或 1/10 屏）；分配失败必须检查 | P0 | `display_driver_checker.py` | `heap_caps_malloc` 返回值检查 | 未检查 `malloc` 返回 |
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
| C24.4 | 外设 stop 前必须等待 DMA/任务 idle | P1 | 人工 | `while (dma_is_busy())` | DMA 传输中关闭 |
| C24.5 | 电机停止后必须关闭加热/VH/电源门控 | P0 | 人工 | `stop_motor()` → `close_vh()` | 只停电机不关电源 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 电机停转但 VH 仍在供电 | C24.5 收尾不完整 |
| 异常后外设未关闭 | C24.1 异常路径未收尾 |
| 重复调用 stop 出错 | C24.2 不可重入 |
| 超时后硬件仍在运行 | C24.3 超时路径未释放 |
| 关闭时 DMA 报错 | C24.4 未等待 DMA 完成 |

---

## C25 — 音视频管线 / A/V Sync

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C25.1 | A/V 同步必须以 audio sample clock / I2S DMA timestamp / audio PTS 为 master clock；视频只能追帧、丢帧、重复帧或轻微调整 | P0 | `av_pipeline_checker.py` + 人工 | [good_av_pipeline_sync.c](../examples/good_av_pipeline_sync.c) | [bad_av_pipeline_blocking.c](../examples/bad_av_pipeline_blocking.c) |
| C25.2 | audio/video frame 结构必须包含 `pts_ms`/`timestamp_ms`、`seq`、`duration_ms` 或 `sample_count`，并标注 owner | P0 | `av_pipeline_checker.py` | 同上 | 同上 |
| C25.3 | 音视频队列必须有界并定义背压；video queue 满时默认 drop-oldest，audio hot path 不得被 video/UI 阻塞 | P1 | `av_pipeline_checker.py` + 人工 | 同上 | 同上 |
| C25.4 | per-frame 热路径（process/render/decode/callback）禁止 `malloc/free/pvPortMalloc/printf/LOG_*`，使用 pool/ring + 低频统计日志 | P1 | `av_pipeline_checker.py` | 同上 | 同上 |
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

## 约束冲突与权衡矩阵

以下场景中两条或多条约束可能互相矛盾，Agent 需要**权衡决策**并记录理由。

| 冲突场景 | 约束 A | 约束 B | 权衡方案 |
|----------|--------|--------|----------|
| **init 需同步时间** | C8.6 init 禁同步 TLS/大 Parse | C8.2 TLS 握手前须 SNTP 同步 | SNTP 用异步 `esp_netif_sntp_init()` + 回调通知，不在 main 阻塞等待 |
| **LVGL 锁序 vs SDK 锁序** | C1.6 双锁顺序：先网络后 LVGL | ESP32 `esp_lvgl_port` 内部锁序可能相反 | 以 SDK 内部锁序为准；若冲突则用 `lv_async_call` 替代 mutex（避免锁序问题） |
| **WSS 栈 vs 内存受限** | C7.5 WSS 栈 ≥4096 bytes | 设备总 RAM < 200KB | 优先关闭未用模块（C6）释放 RAM；若仍不足则缩 LwIP/mbedTLS 池（C7.6），**不缩 WSS 栈** |
| **音频优先级 vs LVGL** | C4.5 音频优先级 > LVGL | C15.1 相邻优先级差 ≥2 | 音频 = MAX-1, WSS = MAX-3, LVGL = MAX-5（满足两条约束） |
| **日志调试 vs ISR 安全** | C14.1 需要日志排查 | C4.3/C14.3 ISR 禁止日志 | ISR 中用 flag/event 记录状态，退出 ISR 后在任务中打印 |
| **测试宏 vs 代码体积** | C5.1 每模块 APP_TEST_MODE_* | C6 量产须关闭减小体积 | 测试宏默认 `#define ... 0`（编译器优化掉）；量产前确认全部为 0 |
| **密钥安全 vs 调试便利** | C9.1 密钥不入库 | 开发阶段需要频繁烧写 | 用 `config.secrets.example`（占位）+ `config.secrets`（gitignore）；调试板用 UART 临时注入 |
| **跨核通信 vs 延迟** | C17.1 跨核须 IPC | IPC 增加延迟 | 高频小数据用共享内存 + 硬件信号量（C17.3）；低频用 mailbox 队列 |
| **函数长度 vs 错误处理** | C11.5 单函数 ≤80 行 | C12.4 goto cleanup 模板增加行数 | cleanup 标签后的释放代码不计入业务逻辑行数；若仍超限则提取 cleanup 为独立函数 |
| **timer 回调 vs 业务逻辑** | C16.1 timer 回调禁阻塞 | 业务需要在 timer 中发事件 | timer 回调仅 `xQueueSend` 或 `xTaskNotify`，处理逻辑移到专用任务 |
| **低功耗 vs 网络保持** | C21.4 睡眠前关 WiFi | C20.5 网络断线须降级 | 深睡眠前主动断开 WSS + 通知云端；唤醒后走完整重连流程（C20.1 指数退避） |
| **低功耗 vs 语音实时** | C21.3 Tickless Idle | C4.5 音频优先级最高 | 语音活跃期禁用 tickless idle；空闲时启用；或用独立硬件定时器驱动 I2S |
| **音频主时钟 vs 显示平滑** | C25.1 audio clock master | C23.3 帧率匹配 | 音频为主，视频按 PTS 丢帧/重复帧，禁止用固定 `vTaskDelay` 反向拖音频 |
| **视频不丢帧 vs 内存受限** | C25.3 有界 video queue | C7.4 高频路径固定块 | 预分配短 ring，满时 drop-oldest + 释放 frame，禁止扩容或阻塞 audio |

---

## L2 输出引用格式

违规项须写：`C2.2` — `file:line` — 问题 — 修复（引用 good 范例）

```markdown
- C1.1 — network_wss.c:142 — WSS 回调直接 lv_label_set_text — 改 Queue → lv_async_call（见 good_mvp_pattern.c）
```
