# 铁律约束分片：RTOS 任务与实时约束（RTOS）

本文件包含启动顺序、任务优先级、模块契约、任务/队列拓扑、超时预算、可观测性、生命周期对称、热路径禁区、关键路径预算、锁预算与优先级反转防护、临界区/关中断预算等约束。

> 对应约束 ID：C8, C15, C17, C29–C35, C43–C44
> 其他分片：[constraint_review.md](constraint_review.md) | [constraint_memory.md](constraint_memory.md) | [constraint_platform.md](constraint_platform.md) | [constraint_media.md](constraint_media.md) | [constraint_ota.md](constraint_ota.md) | [constraint_recover.md](constraint_recover.md) | [constraint_bluetooth_protocol.md](constraint_bluetooth_protocol.md)

---

## 严重度定义

| 级别 | 含义 | 处理 |
|------|------|------|
| P0 | 必崩 / 必泄漏 / 必死锁 | 阻塞合并，须附修复 diff 或范例引用 |
| P1 | 高概率量产问题 | 本迭代必须修复或登记风险 |
| P2 | 可维护性 / 可测试性 | 建议修复，可排期 |

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

## C15 — 任务优先级与通信

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C15.1 | 建议相邻任务优先级差 ≥2（避免优先级反转风险；非硬性要求，需文档说明原因） | P2 | 人工 | `PRIO_WSS = MAX-3, PRIO_LVGL = MAX-5` | `PRIO_WSS=5, PRIO_LVGL=6` 无注释 |
| C15.2 | 共享资源用 mutex（优先级继承），禁止 binary semaphore 保护 | P1 | 人工 | `xSemaphoreCreateMutex()` [MUTEX_CREATE] | `xSemaphoreCreateBinary()` [SEM_CREATE] 保护共享变量 |
| C15.3 | 禁止运行时 `vTaskPrioritySet`（需文档说明原因和恢复条件） | P2 | grep | 初始化时设定 | 运行时无注释改优先级 |

---

## C17 — 多核 IPC

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C17.1 | 跨核通信**禁止**直接共享全局变量（无同步机制 → 数据竞争） | P0 | 人工 | `mailbox_send(MAILBOX_CPU1, &data, sizeof(data))` | `volatile int g_sensor_data;` CPU0 写 CPU1 读无屏障 |
| C17.2 | 跨核 Queue **须**用平台 IPC mailbox，禁止不同 FreeRTOS 实例间用 `xQueueSend`（无效或未定义行为） | P0 | 人工 | `bk_mailbox_send(CPU1, MB_CMD_USER, &msg, sizeof(msg))` | `xQueueSend(cp1_queue, &msg, portMAX_DELAY)` 跨实例 |
| C17.3 | 核间同步**须**用硬件信号量，禁止不同 FreeRTOS 实例间用 `xSemaphoreTake`（mutex 无效） | P0 | 人工 | `hw_semaphore_take(SEM_ID_SHARED_MEM)` | `xSemaphoreTake(cross_core_mutex, portMAX_DELAY)` 跨实例 |

**平台注记**：

| 平台 | IPC 机制 | 文档 |
|------|----------|------|
| BK7258 | `CONFIG_MAILBOX` + `bk_mailbox_*` | `platforms/bk.md` 三核架构节 |
| ESP32 | `esp_ipc_*` + 双核 FreeRTOS 共享实例 | ESP-IDF IPC 文档 |
| JL | `thread_fork` + DSP 核专有 API | `platforms/jl.md` |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 多核数据竞争、偶发值错乱 | C17.1 全局变量无同步 |
| 跨核 Queue 发送无效果 | C17.2 用了错误的 Queue API |
| 跨核 mutex 不生效、死锁 | C17.3 用了软件信号量 |

> 详细提示词：[multi_core_ipc.txt](../prompts/multi_core_ipc.txt)

---

## C29 — 模块契约

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C29.1 | 模块公开 API 必须声明可调用上下文：task / ISR / timer callback / LVGL thread；ISR 可调用路径必须单独命名或注释 | P0 | 人工 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | API 文档未说明上下文 |
| C29.2 | 模块 API 必须声明阻塞语义、最大等待时间、是否可重入；默认不得假设调用者知道内部等待点 | P0 | 人工 + `blocking_wait_checker.py` | 同上 | `module_read()` 内部无限等 Queue |
| C29.3 | 模块必须声明入参、出参、Queue payload、callback user_data 的所有权与释放方 | P1 | 人工 | 同上 | callback 传裸指针但未说明生命周期 |
| C29.4 | 模块必须声明 `init/start/stop/deinit` 合法顺序、重复调用行为和半初始化清理策略 | P1 | 人工 | 同上 | `stop()` 未说明 init 失败后能否调用 |
| C29.5 | 模块必须声明错误码语义：timeout/resource/config/bug 等分类，以及哪些错误可恢复 | P2 | 人工 | 同上 | 全部返回 `-1` |
| C29.6 | 模块必须声明单一职责、public API、dependencies、forbidden_dependencies、events_in/out 和 owned_resources | P0 | 人工 + `module_boundary_checker.py` | [good_module_boundary.c](../examples/good_module_boundary.c) | 上帝模块同时管 UI/network/storage/driver |
| C29.7 | 低层模块禁止直接 include/call 高层模块；UI/Presenter/Model/Driver 边界必须通过 API、Queue/Event 或 callback 契约 | P0 | `module_boundary_checker.py` + 人工 | 同上 | driver include `ui_view.h` 或 network 直接 `lv_obj_*` |
| C29.8 | 模块禁止依赖对方 private struct/global；跨模块只传 handle/descriptor/event 或公开类型 | P1 | 人工 | 同上 | include 对方 private header 后直接改状态 |
| C29.9 | 禁止多个模块共享可写全局 context；全局状态必须有唯一 owner 和访问 API | P0 | `module_boundary_checker.py` + 人工 | 同上 | `extern app_context_t g_app_ctx` 到处读写 |
| C29.10 | review 必须判断高内聚/低耦合：职责是否单一、依赖是否单向、是否存在循环依赖或跨层调用 | P1 | 人工 + `module_boundary_checker.py` | 同上 | 业务修复需要同时改 5 个无关模块 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 新人接手要 grep 半天才敢调用 API | C29.1/C29.2 缺上下文和阻塞契约 |
| Queue payload 泄漏或双 free | C29.3 契约缺所有权，联动 C2 |
| 偶发 stop 后不能再 start | C29.4 生命周期顺序不清，联动 C33 |
| 改一个模块牵动 UI/network/storage/driver 多处 | C29.6-C29.10 模块边界缺失 |

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
| 现场只知道"丢消息"不知道水位 | C30.5 缺队列观测 |

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
| "偶发丢包/爆音/掉帧"只有用户描述 | C32.2 缺计数器 |
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
| C35.1 | 启动、联网、音频、视频、UI、OTA、低功耗唤醒等关键路径必须声明 stage budget | P0 | 人工 | `boot: fs<=120ms, net<=2s` | 只写"尽快初始化" |
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
