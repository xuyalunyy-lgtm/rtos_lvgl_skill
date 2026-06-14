# 铁律细粒度约束矩阵（L2+ 按需加载）

Agent 在 L2 Code Review、Crash 诊断、L3 架构输出时读取本文件。每条约束有唯一 **ID**（`C#.#`），违规报告与 checklist 须引用 ID。

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
| C3.6 | L2+ 审查须运行 `python tools/cjson_leak_checker.py <file>` | P2 | 流程 | — | — |

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

---

## C7 — 内存分配与优化（通用）

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C7.1 | 缩池 / 缩栈 / 关模块**前**须记录基线（堆最低水位、任务 stack watermark、Flash/RAM）；无基线禁止给具体数值建议 | P0 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.2 | 优化顺序：**先**修泄漏与所有权（C2/C3）→ 关未用模块（C6）→ 缩 LwIP/TLS/LVGL 池 → **最后**缩任务栈 | P1 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.3 | 大 buffer（>256B）、证书链、JSON 解析树**禁止**放栈上；须堆分配或静态/对象池 | P0 | 人工 | — | — |
| C7.4 | 长连接 / 高频路径优先固定块或对象池；禁止每帧 / 每包 `malloc`+`free` | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.5 | WSS/TLS 任务栈须按握手峰值实测，**不得低于 4096 bytes**（建议 6144–8192） | P0 | `stack_calculator.py` + 人工 | 完整版 `examples/good_wss_reconnect.c` | `bad_wss_blocking.c` |
| C7.6 | 缩 LwIP / mbedTLS / LVGL 池**每步**须冒烟 WiFi + WSS + 业务闭环 | P1 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.7 | 主工程只链入**一个** TLS 栈（mbedtls / wolfssl / psa 择一） | P1 | 人工 | — | — |
| C7.8 | ISR / DMA / 实时路径缓冲须在 SRAM（或平台文档允许的 fast RAM）；禁止无依据默认放 PSRAM / 外部慢速区 | P1 | 人工 | `platforms/bk.md` 等 | — |
| C7.9 | 重连 / 错误恢复禁止 tight loop 反复 TLS 握手；须指数退避（cap 建议 60s） | P1 | 人工 | 完整版 `examples/good_wss_reconnect.c` | `bad_wss_blocking.c` |

---

## C8 — 启动顺序 / 阻塞 / 看门狗

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C8.1 | Queue + Presenter Looper **须**在注册 WiFi/WSS/网络事件回调之前创建并就绪 | P0 | 人工 | 完整版 `examples/good_boot_sequence.c` | `bad_wss_blocking.c` |
| C8.2 | WSS/TLS **须**在 WiFi 获 IP 之后；证书校验 **须** SNTP 同步完成 | P0 | 人工 | 完整版 `examples/good_wss_reconnect.c` | `bad_wss_blocking.c` |
| C8.3 | Presenter `xQueueReceive` **禁止**默认 `portMAX_DELAY`；须有限 timeout + 循环 | P1 | 人工 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) | — |
| C8.4 | LVGL 任务 `lv_timer_handler` 循环内**禁止**网络/TLS/长 mutex/除固定 tick 外的阻塞 | P0 | 人工 | 完整版 `examples/good_mvp_pattern.c` | `bad_wss_blocking.c` |
| C8.5 | 模块 reconnect **须**幂等：同任务禁止重复 `xTaskCreate`；用句柄 + 状态机/Notify | P1 | 人工 | 完整版 `examples/good_wss_reconnect.c` | — |
| C8.6 | main/init 路径**禁止**同步 TLS 握手、大 Parse、超长 delay 链（防 Task WDT） | P0 | 人工 | 完整版 `examples/good_boot_sequence.c` | `bad_wss_blocking.c` |

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
| heap 持续下降 | C3.1–C3.5, C2.4, **C7.2**（先修泄漏再缩池） |
| TLS 握手 fail / 反复断线 | C8.2, C7.5–C7.9 + [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) |
| WDT / task watchdog | **C8.3–C8.6**, C1.5, C4.7 + [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) |
| 启动后首包丢失 / Queue 满 | **C8.1** |
| 缩池 / 关模块后功能异常 | **C7.6** + [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) |
| 优化建议无数据支撑 | **C7.1** |

---

## L2 输出引用格式

违规项须写：`C2.2` — `file:line` — 问题 — 修复（引用 good 范例）

```markdown
- C1.1 — network_wss.c:142 — WSS 回调直接 lv_label_set_text — 改 Queue → lv_async_call（见 good_mvp_pattern.c）
```
