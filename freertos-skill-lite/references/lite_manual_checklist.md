# Lite 版 L2 人工审查清单（替代 tools/）

Code Review 或 L3 校验时逐条核对。违规项引用 `C#.#`（完整矩阵见完整版 `references/constraint_detail.md`）。完成后输出：**「Lite 人工审查已完成」**。

## C1 — LVGL 线程安全

- [ ] C1.1 非 View 文件无 `lv_obj_*` / `lv_label_*`
- [ ] C1.2 跨任务刷新用 `lv_async_call` 或 mutex
- [ ] C1.3 `lv_async_call` user_data 在回调内 free
- [ ] C1.5 无持 LVGL 锁等 Queue / 网络

## C2 — Queue 所有权

- [ ] C2.1 无 `cJSON*` 进 Queue
- [ ] C2.2 无栈指针进 Queue
- [ ] C2.3 Presenter 统一 `vPortFree(payload)`
- [ ] C2.4 Queue 满时 Model 释放 payload
- [ ] C2.7 Queue 深度与背压已说明

## C3 — cJSON

- [ ] C3.1 每个 `cJSON_Parse` 有唯一 `cleanup:` 且 `cJSON_Delete`
- [ ] C3.2 多出口用 `goto cleanup`
- [ ] C3.3 进 Queue 前已 Delete，只传 plain buffer

## C4 — ISR

- [ ] C4.1 HAL_*Callback 内无阻塞 API，仅用 `*FromISR`
- [ ] C4.2 有 `portYIELD_FROM_ISR`
- [ ] C4.7 ISR 无 mutex

## C5 — 测试宏

- [ ] C5.1 每大模块有 `APP_TEST_MODE_*` 宏

## C7 — 内存分配优化

- [ ] C7.1 缩池/缩栈前有基线或标注「未实测」
- [ ] C7.2 先修泄漏(C2/C3)再缩池，顺序正确
- [ ] C7.3 无大 buffer / JSON 树压栈
- [ ] C7.5 WSS 栈 ≥ 4096 bytes（TLS 建议 6144–8192）
- [ ] C7.6 缩 LwIP/TLS/LVGL 池后有 WiFi+WSS 冒烟说明
- [ ] C7.9 重连指数退避，无 tight loop 握手
- [ ] C7.10 普通/大块/低频内存优先外部 RAM，DMA/ISR/实时路径仍在 fast/DMA RAM
- [ ] C7.11 跨模块对象经统一 allocator/free，记录 heap kind 并 matched free
- [ ] C7.12 日志含 internal/external free、min、largest free block、alloc fail 计数
- [ ] C7.13 高频固定尺寸对象使用预分配固定块池，满时 drop/backpressure

## C8 — 启动 / WDT

- [ ] C8.1 Queue + Presenter 先于网络回调注册
- [ ] C8.2 WiFi IP → SNTP → TLS 顺序
- [ ] C8.3 Presenter 无 portMAX_DELAY 等 Queue
- [ ] C8.5 重连幂等，无重复 xTaskCreate 同模块

## C9 — 密钥/凭证

- [ ] C9.1 入库 config 无非空 SECRET/TOKEN/PASSWORD
- [ ] C9.2 Git remote 无内嵌凭证
- [ ] C9.3 日志不打印密码/token 明文
- [ ] C9.4 secrets 文件在 .gitignore

## C10 — 语音/ASR/Uplink

- [ ] C10.1 prompt/TTS stop + FINISHED 双路径 detach
- [ ] C10.2 开 uplink 前 AEC settle + mic ready
- [ ] C10.3 有 peak / tap peak / uplink bytes 日志，能区分无 PCM vs ASR 空
- [ ] C10.4 prompt/TTS FINISHED+detach 后再 start capture/uplink
- [ ] C10.5 有 session generation 过滤 stale 回调
- [ ] C10.6 playback slot/handle 来自配置或对象字段，无 hardcode magic number

## C11 — 编码规范

- [ ] C11.1 文件名 `模块_功能.c/h`
- [ ] C11.5 单函数 ≤80 行
- [ ] C11.6 每个 .c/.h 有文件头注释

## C12 — 错误处理

- [ ] C12.1 FreeRTOS API 返回值已检查
- [ ] C12.2 pvPortMalloc 失败路径不 NULL 解引用
- [ ] C12.4 多资源函数用 goto cleanup

## C13 — 状态机

- [ ] C13.1 长生命周期任务有 enum state
- [ ] C13.3 switch-default 处理非法状态

## C14 — 日志规范

- [ ] C14.1 无裸 printf，用 LOG_* + TAG
- [ ] C14.3 ISR/DMA/LVGL timer 内无日志
- [ ] C14.4 日志不打印密码/token 明文
- [ ] C14.6 高频/周期日志已限频或改计数聚合
- [ ] C14.7 关键链路日志含 event_id/state/err/seq 等结构化字段
- [ ] C14.8 crash 可 dump 最近日志 ring，ring buffer 有界不阻塞
- [ ] C14.9 量产日志 profile 默认 WARN/ERROR，无 verbose/敏感日志

## C15 — 优先级与通信

- [ ] C15.1 相邻任务优先级差 ≥2
- [ ] C15.2 共享资源用 mutex（非 binary semaphore）

## C16 — 定时器管理

- [ ] C16.1 timer 回调无阻塞操作
- [ ] C16.2 动态 timer 有 stop + delete 路径

## C17 — 多核 IPC

- [ ] C17.1 无跨核直接共享全局变量（无 IPC/mailbox）
- [ ] C17.2 无不同 FreeRTOS 实例间的 xQueueSend
- [ ] C17.3 共享内存访问有硬件信号量保护

## C24 — 外设关闭安全

- [ ] C24.1 异常退出路径与正常路径调用相同收尾函数
- [ ] C24.2 stop/deinit 可重入，有状态检查
- [ ] C24.3 abort/timeout/skip 路径释放所有硬件资源
- [ ] C24.4 stop/deinit 前等待 DMA/任务 idle
- [ ] C24.4 音频/媒体 stop 只进 idle，deinit/free 只在会话结束、低功耗或错误恢复执行
- [ ] C24.5 执行器停止后关闭加热/电源门控/外设使能

## C25 — 音视频管线 / A/V Sync

- [ ] C25.1 以 audio clock / I2S DMA timestamp / audio PTS 为 A/V master clock
- [ ] C25.2 audio/video frame 有 pts/timestamp、seq、duration/sample_count、owner
- [ ] C25.3 队列有界，视频可丢帧，音频高优先级路径不阻塞
- [ ] C25.4 per-frame 热路径无 malloc/free/printf/重日志
- [ ] C25.5 camera/LCD/DMA callback 不直接跑 UI/codec/network/json
- [ ] C25.6 有 drift/drop/late/underrun/overrun 遥测计数

## C26 — 编解码 / 媒体格式一致性

- [ ] C26.1 I2S/AEC/ASR/encoder/uplink 的 sample rate/channels/bit depth 一致或有显式转换
- [ ] C26.2 frame_samples 由 sample_rate * frame_ms * channels 推导，无 magic 512/1024
- [ ] C26.3 video frame 有 pixel_format/stride，RGB565 stride ≥ width*2
- [ ] C26.4 resample/convert/encode/decode 热路径无 malloc/free/printf/重日志
- [ ] C26.5 codec handle 在 open/start 创建，stop/cleanup 释放，不每帧 create/init/open
- [ ] C26.6 有 negotiated format、format_mismatch、codec_error、last_frame_size 遥测

## C27 — 音视频时钟漂移 / Jitter Buffer

- [ ] C27.1 A/V sync 有唯一 master clock，frame PTS/timestamp 单调，不用系统 tick 冒充媒体时钟
- [ ] C27.2 jitter buffer 有 capacity、low/high watermark、target delay 与满水位策略
- [ ] C27.3 drift correction 有 ppm 上限，禁止无界 resample/playback 调整
- [ ] C27.4 render/playback/sync 热路径不按 drift/PTS `vTaskDelay` 或 `portMAX_DELAY` 硬等
- [ ] C27.5 underrun/overrun 只做静音/重复/丢帧/resync，路径内无 malloc/free/printf/重日志
- [ ] C27.6 有 drift、jitter_depth、underrun/overrun、drop/insert、resync 遥测

## C28 — 媒体 DMA/cache/零拷贝 buffer 生命周期

- [ ] C28.1 Camera/I2S/LCD/codec DMA buffer 位于 DMA-capable 内存且 cache-line/控制器要求对齐
- [ ] C28.2 DMA 写后 CPU 读前 invalidate；CPU 写后 DMA/LCD/codec 读前 clean
- [ ] C28.3 零拷贝 frame pool 有 owner/state/generation/release，consumer 未 release 前不复用
- [ ] C28.4 Queue 传 buffer index/handle/descriptor，不传裸 DMA 指针
- [ ] C28.5 cache clean/invalidate 地址和长度按 cache line 对齐并覆盖完整 frame/stride
- [ ] C28.6 有 cache clean/invalidate、stale、reuse_before_release、buffer overrun/underrun 遥测

## C29 — 模块契约

- [ ] C29.1 模块 API 声明 task/ISR/timer/LVGL 可调用上下文
- [ ] C29.2 模块 API 声明阻塞语义、最大等待时间和可重入性
- [ ] C29.3 入参/出参/Queue/callback payload 所有权明确
- [ ] C29.4 init/start/stop/deinit 合法顺序明确
- [ ] C29.5 错误码语义与可恢复/不可恢复分类明确

## C30 — 任务/队列拓扑表

- [ ] C30.1 多任务模块有 task/priority/stack/queue 拓扑表
- [ ] C30.2 每条 Queue 声明元素类型、生产者、消费者和所有权
- [ ] C30.3 每条 Queue 声明深度、timeout 和满队列背压策略
- [ ] C30.4 每个 task 有退出条件，不依赖 reboot 退出
- [ ] C30.5 有 queue high-water/drop/timeout/overflow 观测点

## C31 — 超时预算

- [ ] C31.1 阻塞等待默认有限 timeout，无裸 `portMAX_DELAY` / `WAIT_FOREVER`
- [ ] C31.2 网络/TLS/DNS/file IO 有 deadline 与失败恢复
- [ ] C31.3 mutex/semaphore 等待声明持锁路径和超时处理
- [ ] C31.4 永久等待仅限 dedicated idle/daemon consumer，且有例外注释
- [ ] C31.5 timeout/drop/retry 有低频遥测计数

## C32 — 可观测性优先

- [ ] C32.1 关键模块暴露 state、last_error、last_error_line
- [ ] C32.2 关键链路计数 timeout/drop/retry/overflow/underrun
- [ ] C32.3 可采集 stack high-water、queue high-water、heap free/min/largest
- [ ] C32.4 init/connect/decode/render/flush 等阶段保留 max time
- [ ] C32.5 现场 dump 可还原最近关键事件，且脱敏、限频、可关闭

## C33 — 生命周期对称

- [ ] C33.1 init/open/start/enable 有 stop/disable/close/deinit
- [ ] C33.2 alloc/create/register/attach 有 free/delete/unregister/detach
- [ ] C33.3 多资源函数统一 cleanup，异常路径复用收尾 helper
- [ ] C33.4 stop/deinit 可重入，能处理半初始化状态
- [ ] C33.5 lifecycle 状态与 release 结果低频可观测

## C34 — 热路径禁区

- [ ] C34.1 ISR/DMA/LVGL flush/audio/video/control hot path 无阻塞等待
- [ ] C34.2 hot path 无 malloc/free/printf/重日志/file IO
- [ ] C34.3 hot path 无 cJSON parse、codec create、TLS handshake
- [ ] C34.4 hot path 只做 notify/enqueue/set flag/increment counter
- [ ] C34.5 hot path 有预算、峰值耗时和丢弃计数

## C35 — 关键路径预算表

- [ ] C35.1 启动/联网/音频/视频/UI/OTA/低功耗唤醒有 stage budget
- [ ] C35.2 每个关键阶段有 owner、timeout、fallback 和 metric
- [ ] C35.3 长 IO 已评估并行化、异步化或延迟加载
- [ ] C35.4 max time、timeout/drop/retry counter 可采集
- [ ] C35.5 预算表随需求、配置、板级差异同步更新

## C36 — 数据拷贝预算

- [ ] C36.1 跨 task/跨核/DMA/网络/音视频 frame 有数据移动策略
- [ ] C36.2 大 payload 优先传 descriptor/index/handle
- [ ] C36.3 copy count、buffer owner 和 release 方明确
- [ ] C36.4 DMA/cache 路径声明 clean/invalidate、对齐和 ownership transfer
- [ ] C36.5 buffer pool 满时有 drop/backpressure/retry 策略和计数

## C37 — 背压与降级策略

- [ ] C37.1 高频 producer、网络、音视频、日志、UI 队列有背压策略
- [ ] C37.2 满队列不无限等待，已选择 drop/coalesce/overwrite/backpressure
- [ ] C37.3 降采样、降帧率、降码率、暂停非关键任务有触发条件
- [ ] C37.4 retry bounded，并有 backoff 或 circuit breaker
- [ ] C37.5 背压、降级、恢复有低频 telemetry

## C38 — 故障隔离与自动恢复

- [ ] C38.1 task/driver/protocol/cloud/UI 故障域明确
- [ ] C38.2 recoverable/fatal 错误分类与恢复动作明确
- [ ] C38.3 retry/backoff/max retry/circuit open time 有上限
- [ ] C38.4 supervisor/watchdog/health counter 能发现卡死或半死
- [ ] C38.5 恢复失败进入降级模式或安全停机

## C39 — 配置矩阵约束

- [ ] C39.1 Kconfig/feature flag/board/SDK 差异进入配置矩阵
- [ ] C39.2 每个 feature 有 dependency、resource、default、test mode
- [ ] C39.3 `#ifdef` 归类 platform/board/feature/debug，无无名散落宏
- [ ] C39.4 配置变化同步 bring-up checklist、profile 和回归样本
- [ ] C39.5 无效配置组合在 build 或初始化阶段 fail fast

## C40 — 一键复现闭环

- [ ] C40.1 新模块、bring-up、复杂 bug 有 build/flash/monitor 命令
- [ ] C40.2 crash/core dump 解码有 symbol path、工具和输入日志
- [ ] C40.3 最小配置、测试入口、预期输出可复制执行
- [ ] C40.4 失败日志保存位置、脱敏规则和保留时间明确
- [ ] C40.5 复现命令随平台脚本或 SDK 版本变化更新

## C41 — 回归样本优先

- [ ] C41.1 新约束、新 checker、新 bugfix 有 bad 样本
- [ ] C41.2 bad 样本有对应 good 样本或推荐修复模式
- [ ] C41.3 样本已通用化，无产品名、客户名、密钥或私有路径
- [ ] C41.4 checker/self-test/manual checklist 引用样本并说明预期结果
- [ ] C41.5 样本覆盖失败路径、边界条件和恢复路径

## C42 — 板级资源契约

- [ ] C42.1 GPIO/DMA/clock/IRQ/cache/heap/PSRAM 资源 owner 明确
- [ ] C42.2 板级资源冲突有检查方式或审查表
- [ ] C42.3 DMA/cache/heap capability 的对齐、cacheability 和分配域明确
- [ ] C42.4 IRQ priority、ISR-safe API、跨核访问边界明确
- [ ] C42.5 clock/power domain 生命周期与低功耗约束进入 platform/profile

## C43 — 锁预算与优先级反转防护

- [ ] C43.1 mutex/recursive mutex 等锁等待有有限 timeout 或专用例外
- [ ] C43.2 持锁期间无网络/TLS/Flash/file IO/cJSON parse/delay 等阻塞重活
- [ ] C43.3 共享资源用带优先级继承的 mutex，不用 binary semaphore 伪装 mutex
- [ ] C43.4 多锁嵌套声明 `lock_order` / `lock_rank`
- [ ] C43.5 ISR/callback/LVGL flush/audio/video hot path 不拿 mutex

## C44 — 临界区/关中断预算

- [ ] C44.1 critical section / IRQ mask 区域短小并声明 `irq_off` / critical budget
- [ ] C44.2 关中断期间无阻塞、分配、日志、memcpy、大 IO、解析或 codec 创建
- [ ] C44.3 enter/disable 路径都有 exit/enable，错误路径不提前 return
- [ ] C44.4 关中断期间无 busy loop / poll loop
- [ ] C44.5 ISR/callback/LVGL flush/audio/video hot path 不制造长临界区

## C45 — 传感器集成契约
- [ ] C45.1 init/probe 有 datasheet/register map 依据并校验 `WHO_AM_I` / `chip_id`
- [ ] C45.2 I2C/SPI 事务有有限 timeout、retry/backoff 和错误分类
- [ ] C45.3 data-ready/DRDY/status 等待事件驱动或有界轮询，无 tight poll
- [ ] C45.4 sample 输出含 timestamp、单位、量程、scale/offset 或 calibration version
- [ ] C45.5 calibration/self-test/warm-up 不在采样 hot path，生命周期和失效策略明确

## Codegen Gate — 代码生成门禁

生成代码后逐条核对（对应 `tools/codegen_gate.py` 自动检查）：

- [ ] `generation_manifest.json` 存在且包含 schema_version、generator、platform、generated_files、constraints
- [ ] 所有 generated_files 中列出的文件实际存在
- [ ] constraints.required 中每个约束都有对应覆盖（constraints.covered 或代码注释）
- [ ] 无裸 `portMAX_DELAY`（除非 manifest 声明 allowed_infinite_waits + reason）
- [ ] ISR/callback 中无 blocking API（xQueueReceive、sem Take、vTaskDelay、printf）
- [ ] ISR 中无 malloc/free/cJSON_Parse
- [ ] Queue 无栈指针、cJSON*、裸 DMA 指针传入
- [ ] LVGL API 仅在 UI 任务中调用（非网络/音频/sensor 任务）
- [ ] 每个 init/start 有对应 stop/deinit（C33 对称）
- [ ] Queue depth > 0 时有 backpressure/drop/timeout 策略（C37）

## Framework 约束

- [ ] 已识别项目使用的框架（ESP-IDF/LVGL/mbedTLS/lwIP/Zephyr 等）
- [ ] 框架特定约束已检查（参见 `frameworks/*.json`）
- [ ] 框架间冲突已评估（参见 `references/framework_conflict_matrix.md`）

## RTOS 系统审查

- [ ] 任务拓扑表已输出（task/queue/mutex/timer/ISR）
- [ ] 无循环等待或潜在死锁
- [ ] 高优先级任务不消费低优先级生产的队列（除非有优先级继承）
- [ ] 无孤儿任务（既不生产也不消费，且非周期）
- [ ] 无消费者队列已标记或移除
- [ ] Timer 回调执行时间 < timer 周期
- [ ] 内存池有明确 owner 和释放责任

## 堆栈 / WSS / MVP

- [ ] 相对优先级表已输出（见 [core_rules.md](core_rules.md)）
- [ ] WSS 任务栈 ≥ 4096 bytes（含 TLS 取 6144–8192）
- [ ] Model 不碰 UI；View 不碰网络/音频寄存器
- [ ] SNTP 先于 TLS；重连指数退避
