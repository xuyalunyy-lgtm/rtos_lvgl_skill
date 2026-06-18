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
- [ ] C10.5 有 session generation 过滤 stale 回调

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

## 堆栈 / WSS / MVP

- [ ] 相对优先级表已输出（见 [core_rules.md](core_rules.md)）
- [ ] WSS 任务栈 ≥ 4096 bytes（含 TLS 取 6144–8192）
- [ ] Model 不碰 UI；View 不碰网络/音频寄存器
- [ ] SNTP 先于 TLS；重连指数退避
