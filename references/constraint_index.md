# Constraint ID Quick Reference (L2+ · Token-saving)

Full matrix (positive/negative/checker) → [constraint_detail.md](constraint_detail.md). Violation reports still reference `C#.#`.

## C1 LVGL
| ID | P | One-line |
|----|---|----------|
| C1.1 | 0 | Non-View MUST NOT call `lv_obj_*` / `lv_label_*` |
| C1.2 | 0 | UI only from LVGL task or `lv_async_call` |
| C1.3 | 0 | `lv_async_call` user_data free inside callback |
| C1.4 | 1 | mutex MUST have timeout, `portMAX_DELAY` forbidden |
| C1.5 | 0 | Holding LVGL lock MUST NOT block Queue/network |
| C1.6 | 1 | Dual-lock order: network first, then LVGL |
| C1.7 | 2 | High-frequency UI MUST be throttled |

## C2 Queue
| ID | P | One-line |
|----|---|----------|
| C2.1 | 0 | `cJSON*` MUST NOT enter Queue |
| C2.2 | 0 | Stack pointer MUST NOT enter Queue |
| C2.3 | 0 | Heap payload: Model alloc → Presenter free |
| C2.4 | 0 | When Queue full, Model MUST still free payload |
| C2.5 | 1 | After Send succeeds, Model MUST NOT touch payload |
| C2.6 | 2 | Annotate who alloc / who free |
| C2.7 | 1 | Queue depth and backpressure strategy MUST be documented |
| C2.8 | 0 | `lv_obj_t*` MUST NOT enter Queue |

## C3 cJSON
| ID | P | One-line |
|----|---|----------|
| C3.1 | 0 | Each Parse MUST have Delete in same function |
| C3.2 | 0 | Multiple exits use `goto cleanup` |
| C3.3 | 0 | Delete before entering Queue, only pass plain buffer |
| C3.4 | 1 | Parse in loop MUST Delete each iteration |
| C3.5 | 1 | malloc failure path MUST NOT leak root |
| C3.6 | 2 | L2+ MUST run cjson_leak_checker |

## C4 ISR/DMA
| ID | P | One-line |
|----|---|----------|
| C4.1 | 0 | ISR MUST only use `*FromISR` API |
| C4.2 | 0 | ISR MUST end with `portYIELD_FROM_ISR` |
| C4.3 | 0 | ISR MUST NOT use delay/malloc/cJSON/printf |
| C4.4 | 1 | I2S Ping-Pong + 4-byte alignment |
| C4.5 | 1 | Audio priority MUST be higher than LVGL/WSS |
| C4.6 | 0 | Audio results via Queue, MUST NOT directly modify UI |
| C4.7 | 0 | ISR MUST NOT use mutex |
| C4.8 | 1 | Cache SoC: invalidate/clean after DMA |

## C5–C8
| ID | P | One-line |
|----|---|----------|
| C5.1 | 1 | Each major module MUST have `APP_TEST_MODE_*` |
| C6.1 | 0 | Questionnaire first, then SDK trimming |
| C6.5 | 1 | main/CMakeLists MUST match Kconfig/init chain; uninitialized MUST NOT be compiled |
| C7.1 | 0 | MUST have baseline before reducing pool/stack |
| C7.5 | 0 | WSS stack ≥4096 bytes |
| C7.9 | 1 | Reconnection MUST use exponential backoff |
| C7.10 | 1 | Normal heap allocation prefers external RAM, falls back to internal on failure |
| C7.11 | 1 | Cross-module memory MUST use unified allocator/free wrapper |
| C7.12 | 1 | Telemetry MUST include per-heap free/min/largest/fail |
| C7.13 | 1 | High-frequency fixed-size objects MUST use startup pre-allocated fixed-block pool |
| C8.1 | 0 | Queue/Presenter MUST initialize before network callback |
| C8.3 | 1 | Presenter MUST NOT use `portMAX_DELAY` waiting for Queue |
| C8.6 | 0 | init MUST NOT use synchronous TLS/large Parse |

## C9 Secrets/Credentials
| ID | P | One-line |
|----|---|----------|
| C9.1 | 0 | Committed config MUST NOT contain non-empty SECRET/TOKEN/PASSWORD |
| C9.2 | 0 | Git remote MUST NOT embed credentials |
| C9.3 | 1 | Logs MUST NOT print passwords/tokens |
| C9.4 | 1 | secrets file MUST be gitignored |
| C9.5 | 2 | Build MUST support config.secrets override |
| C9.6 | 2 | L2 project review MUST run secret_scan |

## C10 语音/ASR/Uplink
| ID | P | 一句话 |
|----|---|--------|
| C10.1 | 0 | prompt/TTS 结束须 detach 播放路径 |
| C10.2 | 0 | 开 uplink 前 AEC settle + mic ready |
| C10.3 | 1 | 先 peak/uplink 区分无 PCM vs ASR 空 |
| C10.4 | 1 | prompt 完成后再 start uplink |
| C10.5 | 1 | session generation 防 stale 回调 / 旧 TTS 重启 |
| C10.6 | 2 | playback slot/handle 勿 hardcode |

## C11 编码规范
| ID | P | 一句话 |
|----|---|--------|
| C11.1 | 2 | 文件名 `模块_功能.c/h`，禁止中文/空格 |
| C11.2 | 2 | 函数名 `模块_动作_对象()`，≤30 字符 |
| C11.3 | 2 | 宏全大写 `MODULE_FEATURE_VALUE` |
| C11.4 | 2 | 结构体名 `模块_xxx_t` |
| C11.5 | 1 | 单函数 ≤80 行，超限须拆分 |
| C11.6 | 2 | 每个 .c/.h 须有模块说明文件头注释 |

## C12 错误处理
| ID | P | 一句话 |
|----|---|--------|
| C12.1 | 0 | FreeRTOS API 返回值必须检查 |
| C12.2 | 0 | malloc 失败须有 fallback，禁止 NULL 解引用 |
| C12.3 | 1 | 统一错误码枚举，禁 magic number 返回 |
| C12.4 | 0 | 多资源函数用 goto cleanup 统一释放 |
| C12.5 | 1 | configASSERT 仅用于不可恢复错误 |

## C13 状态机
| ID | P | 一句话 |
|----|---|--------|
| C13.1 | 1 | 长生命周期任务须有显式 enum state |
| C13.2 | 2 | >5 状态须有转换表注释 |
| C13.3 | 1 | switch-default 处理非法状态（log + reset） |
| C13.4 | 2 | 需断电恢复的状态持久化到 NVS/Flash |

## C14 日志规范
| ID | P | 一句话 |
|----|---|--------|
| C14.1 | 1 | 分级日志 + TAG，禁止裸 printf |
| C14.2 | 2 | 日志级别可 Kconfig 配置 |
| C14.3 | 0 | ISR/DMA/LVGL timer 内禁止日志 |
| C14.4 | 1 | 日志禁止打印密码/token 明文 |
| C14.5 | 1 | HardFault handler 须采集 PC/LR/寄存器 |
| C14.6 | 1 | 高频/周期日志必须限频或计数聚合 |
| C14.7 | 2 | 关键链路日志必须结构化并带 event_id |
| C14.8 | 1 | 最近日志 ring buffer 有界且 crash 可 dump |
| C14.9 | 1 | Debug/Release/Production 日志 profile 明确 |

## C15 任务优先级与通信
| ID | P | 一句话 |
|----|---|--------|
| C15.1 | 1 | 相邻任务优先级差 ≥2 |
| C15.2 | 1 | 共享资源用 mutex（优先级继承），禁 binary semaphore |
| C15.3 | 2 | 禁止运行时 vTaskPrioritySet（需文档说明） |

## C16 定时器管理
| ID | P | 一句话 |
|----|---|--------|
| C16.1 | 0 | 软件定时器回调禁止阻塞（daemon 共享） |
| C16.2 | 1 | 动态创建 timer 须有 stop + delete 路径 |
| C16.3 | 2 | 周期 pdTRUE / 单次 pdFALSE 须区分 |

## C17 多核 IPC
| ID | P | 一句话 |
|----|---|--------|
| C17.1 | 0 | 跨核通信禁止直接共享全局变量（须 IPC/mailbox） |
| C17.2 | 0 | 不同 FreeRTOS 实例间禁 xQueueSend（须平台 IPC API） |
| C17.3 | 1 | 核间同步用硬件信号量，禁跨核 mutex |

## C18 外设驱动安全
| ID | P | 一句话 |
|----|---|--------|
| C18.1 | 0 | GPIO 方向必须在使用前配置（gpio_config 先于 gpio_set_level） |
| C18.2 | 1 | I2C 设备地址必须来自 datasheet，禁止硬编码猜测 |
| C18.3 | 1 | SPI 时钟模式（CPOL/CPHA）必须匹配从设备 |
| C18.4 | 1 | DMA 通道分配须文档化，同一通道不可被两个外设同时使用 |
| C18.5 | 2 | ADC 引脚必须配置为模拟输入模式 |
| C18.6 | 2 | PWM 频率与分辨率互斥，须根据应用选择 |

## C19 Flash/NVS/状态持久化
| ID | P | 一句话 |
|----|---|--------|
| C19.1 | 0 | NVS 写入后必须 nvs_commit() + 检查返回值 |
| C19.2 | 1 | Flash 擦写期间禁止读取同分区 |
| C19.3 | 1 | OTA 首次启动必须调用 mark_valid_cancel_rollback |
| C19.4 | 1 | OTA 产品分区表须含 ota_0 + ota_1 |
| C19.5 | 2 | Flash 高频写入场景须做磨损均衡 |

## C20 网络韧性
| ID | P | 一句话 |
|----|---|--------|
| C20.1 | 0 | WiFi/WSS 断线重连必须有指数退避（1s→60s cap） |
| C20.2 | 0 | 所有阻塞网络操作必须有有限超时 |
| C20.3 | 1 | DNS 解析失败必须处理，不可直接崩溃 |
| C20.4 | 1 | TLS 握手失败须区分错误类型 |
| C20.5 | 1 | 网络断线时业务必须有降级策略（离线模式） |

## C21 低功耗管理
| ID | P | 一句话 |
|----|---|--------|
| C21.1 | 0 | 深度睡眠前必须保存状态到 NVS/Flash |
| C21.2 | 1 | 唤醒后必须恢复状态而非重新初始化 |
| C21.3 | 1 | Tickless Idle 必须正确配置（高频任务不受影响） |
| C21.4 | 1 | 深度睡眠前必须关闭外设电源（LCD/音频/WiFi） |
| C21.5 | 2 | 多唤醒源同时配置时须确认不冲突 |

## C22 OTA / 固件升级安全
| ID | P | 一句话 |
|----|---|--------|
| C22.1 | 0 | OTA 镜像必须有签名验证（secure boot / image verify） |
| C22.2 | 0 | OTA 升级后必须 mark_valid_cancel_rollback；失败必须可回滚 |
| C22.3 | 1 | OTA 分区表须含 ota_0 + ota_1；NVS 分区不可删 |
| C22.4 | 0 | OTA 断电恢复：写入非活动分区，断电后旧固件仍可运行 |
| C22.5 | 1 | OTA HTTP 下载必须有超时（connect/read）和重试上限 |
| C22.6 | 2 | 差分升级必须有 patch 校验和回退策略 |

## C23 显示驱动
| ID | P | 一句话 |
|----|---|--------|
| C23.1 | 0 | LCD 初始化时序严格遵循 datasheet（复位/命令间延迟） |
| C23.2 | 1 | 背光用 PWM 控制，支持渐变；低功耗关闭背光电源 |
| C23.3 | 1 | lv_timer_handler 调用频率匹配面板，输入回调不直接解码或建整页 |
| C23.4 | 1 | 显示刷新须撕裂防护（TE 信号/双缓冲） |
| C23.5 | 0 | 帧缓冲按 RAM 选择全屏/部分刷新，分配须检查 |
| C23.6 | 1 | lv_disp_drv_t 必须设置字段，flush 回调须在安全后归还 draw buffer |

## C24 外设关闭安全
| ID | P | 一句话 |
|----|---|--------|
| C24.1 | 0 | 异常退出路径必须与正常路径调用相同收尾函数 |
| C24.2 | 1 | 外设 stop 函数必须可重入（有状态检查） |
| C24.3 | 0 | abort/timeout/skip 必须释放所有硬件资源 |
| C24.4 | 1 | stop/deinit 前等 DMA/任务 idle；音频区分 idle 与 free |
| C24.5 | 0 | 执行器停止后必须关闭加热/电源门控/外设使能 |

## C25 音视频管线 / A/V Sync
| ID | P | 一句话 |
|----|---|--------|
| C25.1 | 0 | 以 audio clock / I2S DMA timestamp 为 A/V master clock |
| C25.2 | 0 | audio/video frame 必须有 pts/timestamp、seq、duration/sample_count、owner |
| C25.3 | 1 | 队列有界，视频可丢帧，音频高优先级路径不阻塞 |
| C25.4 | 1 | per-frame 热路径禁止 malloc/free/printf/重日志 |
| C25.5 | 0 | camera/LCD/DMA callback 只 notify/enqueue，不跑 UI/codec/network/json |
| C25.6 | 2 | 保留 drift/drop/late/underrun/overrun 遥测计数 |

## C26 编解码 / 媒体格式一致性
| ID | P | 一句话 |
|----|---|--------|
| C26.1 | 0 | I2S/AEC/ASR/encoder/uplink 的 sample rate/channels/bit depth 必须一致或显式转换 |
| C26.2 | 0 | frame_samples 必须由 sample_rate * frame_ms * channels 推导，禁止 magic 512/1024 |
| C26.3 | 1 | video frame 必须声明 pixel_format/stride，RGB565 stride ≥ width*2 |
| C26.4 | 1 | resample/convert/encode/decode 热路径禁止 malloc/free/printf/重日志 |
| C26.5 | 0 | codec handle 在 open/start 创建，禁止每帧 create/init/open |
| C26.6 | 2 | 保留 negotiated format、format_mismatch、codec_error、last_frame_size 遥测 |

## C27 音视频时钟漂移 / Jitter Buffer
| ID | P | 一句话 |
|----|---|--------|
| C27.1 | 0 | A/V sync 必须声明唯一 master clock，并使用单调 PTS/timestamp |
| C27.2 | 0 | jitter buffer 必须有 capacity、low/high watermark、target delay 与满水位策略 |
| C27.3 | 1 | drift correction 必须有 ppm 上限，禁止无界 resample/playback 调整 |
| C27.4 | 1 | render/playback/sync 热路径禁止按 drift/PTS `vTaskDelay` 或 `portMAX_DELAY` 硬等 |
| C27.5 | 1 | underrun/overrun 路径只做静音/重复/丢帧/resync，禁止分配、释放、打印 |
| C27.6 | 2 | 保留 drift、jitter_depth、underrun/overrun、drop/insert、resync 遥测 |

## C28 媒体 DMA/cache/零拷贝 buffer 生命周期
| ID | P | 一句话 |
|----|---|--------|
| C28.1 | 0 | Camera/I2S/LCD/codec DMA buffer 必须 DMA-capable 且 cache-line/控制器要求对齐 |
| C28.2 | 0 | DMA 写后 CPU 读前 invalidate；CPU 写后 DMA/LCD/codec 读前 clean |
| C28.3 | 0 | 零拷贝 frame pool 必须有 owner/state/generation/release，consumer 未 release 前禁止复用 |
| C28.4 | 1 | Queue 传 buffer index/handle/descriptor，禁止裸 DMA 指针所有权不清 |
| C28.5 | 1 | cache clean/invalidate 地址和长度必须按 cache line 对齐并覆盖完整 frame/stride |
| C28.6 | 2 | 保留 cache_clean/invalidate、stale、reuse_before_release、buffer overrun/underrun 遥测 |

## C29 模块契约
| ID | P | 一句话 |
|----|---|--------|
| C29.1 | 0 | 模块必须声明 task/ISR/timer/LVGL 可调用上下文 |
| C29.2 | 0 | 模块 API 必须声明阻塞语义、最大等待时间和可重入性 |
| C29.3 | 1 | 模块必须声明入参/出参/Queue/callback payload 所有权 |
| C29.4 | 1 | 模块必须声明 init/start/stop/deinit 合法顺序 |
| C29.5 | 2 | 模块必须声明错误码语义与可恢复/不可恢复分类 |
| C29.6 | 0 | 模块必须声明单一职责、public API、依赖、禁止依赖、事件边界和 owned resources |
| C29.7 | 0 | 低层禁止直接 include/call 高层，跨模块通过 API/Queue/Event/callback |
| C29.8 | 1 | 禁止跨模块访问 private struct/global，只传 handle/descriptor/event |
| C29.9 | 0 | 禁止共享可写全局 context；全局状态必须有唯一 owner API |
| C29.10 | 1 | review 必须判断高内聚低耦合、单向依赖、循环依赖和跨层调用 |

## C30 任务/队列拓扑表
| ID | P | 一句话 |
|----|---|--------|
| C30.1 | 0 | 多任务模块必须输出 task/priority/stack/queue 拓扑表 |
| C30.2 | 0 | 每条 Queue 必须声明元素类型、生产者、消费者与所有权 |
| C30.3 | 1 | 每条 Queue 必须声明深度、timeout、满队列背压策略 |
| C30.4 | 1 | 每个 task 必须声明退出条件，禁止只能 reboot 退出 |
| C30.5 | 2 | 拓扑表必须保留 queue high-water/drop/timeout 观测点 |

## C31 超时预算
| ID | P | 一句话 |
|----|---|--------|
| C31.1 | 0 | 阻塞等待默认必须有限 timeout，禁止裸 `portMAX_DELAY` |
| C31.2 | 0 | 网络/TLS/DNS/file IO 等待必须有 deadline 与失败恢复 |
| C31.3 | 1 | mutex/semaphore 等待必须声明持锁路径和超时处理 |
| C31.4 | 1 | 允许永久等待必须限 dedicated idle/daemon consumer 且有注释 |
| C31.5 | 2 | timeout/drop/retry 必须有低频遥测计数 |

## C32 可观测性优先
| ID | P | 一句话 |
|----|---|--------|
| C32.1 | 1 | 关键模块必须暴露 state、last_error、last_error_line |
| C32.2 | 1 | 关键链路必须计数 timeout/drop/retry/overflow/underrun |
| C32.3 | 1 | 任务必须可采集 stack high-water 与 queue/heap 水位 |
| C32.4 | 2 | init/connect/decode/render/flush 等阶段必须保留 max time |
| C32.5 | 2 | 现场 dump 必须能还原最近关键事件且脱敏限频 |

## C33 生命周期对称
| ID | P | 一句话 |
|----|---|--------|
| C33.1 | 0 | init/open/start/enable 必须有 stop/disable/close/deinit |
| C33.2 | 0 | alloc/create/register/attach 必须有 free/delete/unregister/detach |
| C33.3 | 1 | 多资源函数必须统一 `cleanup:`，异常路径复用收尾 helper |
| C33.4 | 1 | stop/deinit 必须可重入并处理半初始化状态 |
| C33.5 | 2 | lifecycle 状态与 release 结果必须低频可观测 |

## C34 热路径禁区
| ID | P | 一句话 |
|----|---|--------|
| C34.1 | 0 | ISR/DMA/LVGL flush/audio/video hot path 禁止阻塞等待 |
| C34.2 | 1 | hot path 禁止 malloc/free/printf/重日志/file IO |
| C34.3 | 1 | hot path 禁止 cJSON parse、codec create、TLS handshake |
| C34.4 | 1 | hot path 只允许 notify/enqueue/set flag/increment counter |
| C34.5 | 2 | hot path 预算、峰值耗时和丢弃计数必须可观测 |

## C35 关键路径预算表
| ID | P | 一句话 |
|----|---|--------|
| C35.1 | 0 | 启动/联网/音频/视频/UI/OTA/低功耗唤醒必须声明 stage budget |
| C35.2 | 0 | 每个关键阶段必须声明 owner、timeout、fallback 和 metric |
| C35.3 | 1 | 关键路径禁止无证据串行长 IO，必须评估并行化或异步化 |
| C35.4 | 1 | 关键路径必须记录 max time、timeout/drop/retry counter |
| C35.5 | 2 | 预算表必须随需求、配置、板级差异变化同步更新 |

## C36 数据拷贝预算
| ID | P | 一句话 |
|----|---|--------|
| C36.1 | 0 | 跨 task/跨核/DMA/网络/音视频 frame 必须声明数据移动策略 |
| C36.2 | 0 | 大 payload 默认传 descriptor/index/handle，禁止无理由传大结构体进 Queue |
| C36.3 | 1 | 每条数据路径必须声明 copy count、buffer owner 和 release 方 |
| C36.4 | 1 | DMA/cache 路径必须声明 clean/invalidate、对齐和 ownership transfer |
| C36.5 | 2 | buffer pool 满时必须有 drop/backpressure/retry 策略和计数 |

## C37 背压与降级策略
| ID | P | 一句话 |
|----|---|--------|
| C37.1 | 0 | 高频 producer、网络、音视频、日志、UI 队列必须声明背压策略 |
| C37.2 | 0 | 满队列禁止无限等待，必须选择 drop/coalesce/overwrite/backpressure |
| C37.3 | 1 | 降采样、降帧率、降码率、暂停非关键任务必须有触发条件 |
| C37.4 | 1 | retry 必须 bounded，并带 backoff 或 circuit breaker |
| C37.5 | 2 | 背压、降级、恢复必须有低频 telemetry |

## C38 故障隔离与自动恢复
| ID | P | 一句话 |
|----|---|--------|
| C38.1 | 0 | 关键模块必须声明 task/driver/protocol/cloud/UI 故障域 |
| C38.2 | 0 | 错误必须分类 recoverable/fatal，并声明恢复动作 |
| C38.3 | 1 | retry/backoff/max retry/circuit open time 必须有上限 |
| C38.4 | 1 | supervisor/watchdog/health counter 必须能发现卡死或半死 |
| C38.5 | 2 | 恢复失败必须进入降级模式或安全停机，而非静默失败 |

## C39 配置矩阵约束
| ID | P | 一句话 |
|----|---|--------|
| C39.1 | 0 | Kconfig/feature flag/board/SDK 差异必须进入配置矩阵 |
| C39.2 | 0 | 每个 feature 必须声明 dependency、resource、default、test mode |
| C39.3 | 1 | `#ifdef` 必须归类 platform/board/feature/debug，禁止无名散落 |
| C39.4 | 1 | 配置变化必须同步 bring-up checklist、profile 和回归样本 |
| C39.5 | 2 | 无效配置组合必须在 build 或初始化阶段 fail fast |

## C40 一键复现闭环
| ID | P | 一句话 |
|----|---|--------|
| C40.1 | 0 | 新模块、bring-up、复杂 bug 必须提供 build/flash/monitor 命令 |
| C40.2 | 0 | crash/core dump 解码必须声明 symbol path、工具和输入日志 |
| C40.3 | 1 | 最小配置、测试入口、预期输出必须可复制执行 |
| C40.4 | 1 | 失败日志保存位置、脱敏规则和保留时间必须明确 |
| C40.5 | 2 | 复现命令必须随平台脚本或 SDK 版本变化更新 |

## C41 回归样本优先
| ID | P | 一句话 |
|----|---|--------|
| C41.1 | 0 | 新约束、新 checker、新 bugfix 必须优先沉淀 bad 样本 |
| C41.2 | 0 | 每个 bad 样本必须有对应 good 样本或推荐修复模式 |
| C41.3 | 1 | 样本必须通用化，不包含产品名、客户名、密钥或私有路径 |
| C41.4 | 1 | checker/self-test/manual checklist 必须引用样本并说明预期结果 |
| C41.5 | 2 | 样本覆盖失败路径、边界条件和恢复路径，不只覆盖 happy path |

## C42 板级资源契约
| ID | P | 一句话 |
|----|---|--------|
| C42.1 | 0 | GPIO/DMA/clock/IRQ/cache/heap/PSRAM 资源必须声明 owner |
| C42.2 | 0 | 板级资源冲突必须有检查方式或审查表 |
| C42.3 | 1 | DMA/cache/heap capability 必须声明对齐、cacheability 和分配域 |
| C42.4 | 1 | IRQ priority、ISR-safe API、跨核访问边界必须明确 |
| C42.5 | 2 | clock/power domain 生命周期与低功耗约束必须进入 platform/profile |

## C43 锁预算与优先级反转防护
| ID | P | 一句话 |
|----|---|--------|
| C43.1 | 0 | mutex/recursive mutex 等锁等待必须有限 timeout 或声明专用例外 |
| C43.2 | 0 | 持锁期间禁止网络/TLS/Flash/file IO/cJSON parse/delay 等阻塞或重活 |
| C43.3 | 1 | 保护共享资源必须使用带优先级继承的 mutex，禁止 binary semaphore 伪装 mutex |
| C43.4 | 1 | 多锁嵌套必须声明 lock_order/lock_rank，禁止隐式锁顺序 |
| C43.5 | 0 | ISR/callback/LVGL flush/audio/video hot path 禁止拿 mutex |

## C44 临界区/关中断预算
| ID | P | 一句话 |
|----|---|--------|
| C44.1 | 1 | `taskENTER_CRITICAL` / 关中断区域必须短小并声明 `irq_off` / critical budget |
| C44.2 | 0 | 临界区/关中断期间禁止阻塞、分配、日志、memcpy、大 IO、解析和 codec 创建 |
| C44.3 | 0 | 每个 enter/disable 路径必须保证 exit/enable，禁止提前 return 泄漏关中断状态 |
| C44.4 | 1 | 临界区/关中断期间禁止 busy loop / poll loop |
| C44.5 | 0 | ISR/callback/LVGL flush/audio/video hot path 禁止制造长临界区或再次关中断 |

## C45 传感器集成契约
| ID | P | 一句话 |
|----|---|--------|
| C45.1 | 0 | 传感器 init/probe 必须有 datasheet/register map 依据并校验 WHO_AM_I/chip_id |
| C45.2 | 0 | I2C/SPI 传感器事务必须有有限 timeout、retry/backoff 和错误分类 |
| C45.3 | 1 | data-ready/DRDY/status 等待必须事件驱动或有界轮询，禁止 tight poll |
| C45.4 | 1 | sample 输出必须携带 timestamp、单位、量程、scale/offset 或校准版本 |
| C45.5 | 2 | calibration/self-test/warm-up 不得放在采样热路径，须有生命周期与失效策略 |

## 症状 → ID（Crash 用）

| 症状 | 优先核查 ID |
|------|-------------|
| OTA 后设备变砖 / 回滚失败 | **C22.1, C22.2, C22.4** |
| OTA 下载卡死 / 反复重试 | **C22.5** |

→ [debug_crash.md](../workflows/debug_crash.md) Step 2 症状路由表（与 `constraint_detail.md` 末尾同步）。

Prompt 深细节按需 1–3 个 → [skill_structure.md](skill_structure.md) 场景表。
## C46 Bluetooth Protocol Alignment

| ID | P | One-line |
|----|---|----------|
| C46.1 | 1 | BLE init/close must have state machine and rollback |
| C46.2 | 1 | ADV/reconnect values must come from profile/board config |
| C46.3 | 1 | GATT Service/UUID/Characteristic must match documents |
| C46.4 | 1 | State machine must cover idle/connecting/connected/disconnecting |
| C46.5 | 2 | Secure pairing must define auth/encryption/bond lifecycle |
| C46.6 | 1 | MTU/subpacket capability must adapt by device |
| C46.7 | 1 | Error codes must classify recoverable vs fatal with action mapping |
| C46.8 | 1 | Platform capability matrix must cover ESP32/JL/BK/STM32/Zephyr |
