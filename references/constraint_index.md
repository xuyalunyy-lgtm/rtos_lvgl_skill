# 约束 ID 速查（L2+ · 省 token 版）

完整矩阵（正例/反例/checker）→ [constraint_detail.md](constraint_detail.md)。违规报告仍引用 `C#.#`。

## C1 LVGL
| ID | P | 一句话 |
|----|---|--------|
| C1.1 | 0 | 非 View 禁止 `lv_obj_*` / `lv_label_*` |
| C1.2 | 0 | UI 仅 LVGL 任务或 `lv_async_call` |
| C1.3 | 0 | `lv_async_call` user_data 回调内 free |
| C1.4 | 1 | mutex 须超时，禁 `portMAX_DELAY` |
| C1.5 | 0 | 持 LVGL 锁禁阻塞 Queue/网络 |
| C1.6 | 1 | 双锁顺序：先网络后 LVGL |
| C1.7 | 2 | 高频 UI 须节流 |

## C2 Queue
| ID | P | 一句话 |
|----|---|--------|
| C2.1 | 0 | 禁 `cJSON*` 进 Queue |
| C2.2 | 0 | 禁栈指针进 Queue |
| C2.3 | 0 | heap payload：Model alloc → Presenter free |
| C2.4 | 0 | Queue 满时 Model 仍须 free payload |
| C2.5 | 1 | Send 成功后 Model 禁再碰 payload |
| C2.6 | 2 | 标注谁 alloc / 谁 free |
| C2.7 | 1 | Queue 深度与背压策略须文档化 |
| C2.8 | 0 | 禁 `lv_obj_t*` 进 Queue |

## C3 cJSON
| ID | P | 一句话 |
|----|---|--------|
| C3.1 | 0 | 每 Parse 同函数内 Delete |
| C3.2 | 0 | 多出口 `goto cleanup` |
| C3.3 | 0 | 进 Queue 前 Delete，只传 plain buffer |
| C3.4 | 1 | 循环内 Parse 每次 Delete |
| C3.5 | 1 | malloc 失败路径不泄漏 root |
| C3.6 | 2 | L2+ 跑 cjson_leak_checker |

## C4 ISR/DMA
| ID | P | 一句话 |
|----|---|--------|
| C4.1 | 0 | ISR 仅 `*FromISR` API |
| C4.2 | 0 | ISR 末尾 `portYIELD_FROM_ISR` |
| C4.3 | 0 | ISR 禁 delay/malloc/cJSON/printf |
| C4.4 | 1 | I2S Ping-Pong + 4 字节对齐 |
| C4.5 | 1 | 音频优先级高于 LVGL/WSS |
| C4.6 | 0 | 音频结果经 Queue，禁直改 UI |
| C4.7 | 0 | ISR 禁 mutex |
| C4.8 | 1 | Cache SoC：DMA 后 invalidate/clean |

## C5–C8
| ID | P | 一句话 |
|----|---|--------|
| C5.1 | 1 | 每大模块 `APP_TEST_MODE_*` |
| C6.1 | 0 | 先问卷再 SDK 裁剪 |
| C6.5 | 1 | main/CMakeLists 与 Kconfig/init 链一致，未 init 不得编入 |
| C7.1 | 0 | 缩池/栈前须有基线 |
| C7.5 | 0 | WSS 栈 ≥4096 bytes |
| C7.9 | 1 | 重连指数退避 |
| C7.10 | 1 | 普通堆申请优先外部 RAM，失败再回退 internal |
| C8.1 | 0 | Queue/Presenter 先于网络回调 |
| C8.3 | 1 | Presenter 禁 `portMAX_DELAY` 等 Queue |
| C8.6 | 0 | init 禁同步 TLS/大 Parse |

## C9 密钥/凭证
| ID | P | 一句话 |
|----|---|--------|
| C9.1 | 0 | 入库 config 禁非空 SECRET/TOKEN/PASSWORD |
| C9.2 | 0 | Git remote 禁内嵌凭证 |
| C9.3 | 1 | 日志禁打印密码/token |
| C9.4 | 1 | secrets 文件须 gitignore |
| C9.5 | 2 | 构建支持 config.secrets 覆盖 |
| C9.6 | 2 | L2 工程审查须跑 secret_scan |

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

## C23 显示驱动
| ID | P | 一句话 |
|----|---|--------|
| C23.1 | 0 | LCD 初始化时序严格遵循 datasheet（复位/命令间延迟） |
| C23.2 | 1 | 背光用 PWM 控制，支持渐变；低功耗关闭背光电源 |
| C23.3 | 1 | lv_timer_handler 调用频率匹配面板刷新率 |
| C23.4 | 1 | 显示刷新须撕裂防护（TE 信号/双缓冲） |
| C23.5 | 0 | 帧缓冲按 RAM 选择全屏/部分刷新，分配须检查 |
| C23.6 | 1 | lv_disp_drv_t 必须设置 hor_res/ver_res/draw_buf |

## C24 外设关闭安全
| ID | P | 一句话 |
|----|---|--------|
| C24.1 | 0 | 异常退出路径必须与正常路径调用相同收尾函数 |
| C24.2 | 1 | 外设 stop 函数必须可重入（有状态检查） |
| C24.3 | 0 | abort/timeout/skip 必须释放所有硬件资源 |
| C24.4 | 1 | stop/deinit 前等 DMA/任务 idle；音频区分 idle 与 free |
| C24.5 | 0 | 电机停止后必须关闭加热/VH/电源门控 |

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

## 症状 → ID（Crash 用）

→ [debug_crash.md](../workflows/debug_crash.md) Step 2 症状路由表（与 `constraint_detail.md` 末尾同步）。

Prompt 深细节按需 1–3 个 → [skill_structure.md](skill_structure.md) 场景表。
