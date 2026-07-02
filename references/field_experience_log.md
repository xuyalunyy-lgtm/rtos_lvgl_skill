# 现场经验日志（自学习系统）

Agent 或维护者在发现新的 anti-pattern 或现场经验时追加条目。**最新在上。**

## 条目模板

```markdown
### YYYY-MM-DD — 简短标题

- **来源：** 现场日志 / 用户反馈 / CI / 量产
- **平台：** esp32 | stm32 | jl | bk | zephyr | 通用
- **症状：** 一句话描述现象
- **根因：** 通用根因分析
- **修复模式：** 通用修复模式
- **约束映射：** C#.# 或「建议新增 CXX」
- **频率：** 低/中/高
- **影响：** P0/P1/P2
```

---

### 2026-07-03 — BK 大体积 TF binfont 放大 WSS 断线销毁 assert

- **来源：** BK7258 app_paltte 替换 TF 中文字库后现场重启日志
- **平台：** BK
- **症状：** 将约 270KB 的 `my_font_16.bin` 替换为约 2.3MB 字库后，设备启动后 WiFi 断开并进入 WSS disconnect，随后 FreeRTOS `Assert at: xTaskPriorityDisinherit` 重启
- **根因：** LVGL binfont 加载会把字体元数据/位图放入运行内存，TF 文件体积会直接消耗 PSRAM/heap；大资源降低内存余量后，网络断线路径中持应用 mutex 调用 websocket destroy/free，容易放大 SDK websocket task 与回调的锁/生命周期竞态
- **修复模式：** 外部 UI 资源加载前先 stat 文件大小并设置 Kconfig 上限，超限降级到内置字体；加载前后记录 heap/PSRAM 余量；WSS RX/TX buffer 必须按协议单帧需求配置，不要默认 64KB 大 buffer 与字体/图片争 PSRAM；WSS disconnect/reconnect/deinit 先在应用锁内 detach 当前 client 并让 stale event 失效，再在锁外执行可能阻塞的 SDK destroy；断网/重连作为回归用例
- **约束映射：** C7.12, C20.5, C31.3, C33.1, C38.1, C43.1
- **频率：** 中
- **影响：** P0

### 2026-07-03 — BK 录音结束恢复 STA 省电触发 IPC 心跳重启

- **来源：** BK7258 app_paltte 录音停止后重启现场日志
- **平台：** BK
- **症状：** AI 录音 stop / `CLIENT_AUDIO_FINISH` 后约 8s 重启，日志出现 `IPC[1]heartbeat timeout ...` 与 `Assert at: mb_ipc_task:275`，无 HardFault；若强行 stop/restart voice read，第二轮录音可能刷 `AEL_IO_ABORT`
- **根因：** 录音结束立即调用 `bk_wifi_sta_pm_enable()` 恢复 STA power save，使 WiFi/音频/IPC 跨核状态切换时 CPU1 心跳停止；BK CP 侧 `CONFIG_INT_WDT_PERIOD_MS=8000` 到期后 assert 重启
- **修复模式：** 录音期间 `bk_wifi_sta_pm_disable()` 后，不要在 capture stop 立即恢复 STA 省电；保持 voice/read handle 只进入 gated idle，避免 stop 后重启 reader；只在 deinit 或经长测验证的安全窗口恢复 PM；验收日志要求无 `IPC heartbeat timeout`、无 `AEL_IO_ABORT` 连刷，且多轮 `CLIENT_AUDIO_FINISH ok=1`
- **约束映射：** C8.3, C20.1, C24.4, C31.3, C33.1, C38.4
- **频率：** 中
- **影响：** P0

### 2026-07-02 — WSS 销毁后异步任务仍访问 client

- **来源：** BK7258 app_paltte 现场重启与提交前审查
- **平台：** BK
- **症状：** WiFi 断线、语音子系统 stop 或 WSS 重连后，设备偶发重启、堆异常或 stale event
- **根因：** WebSocket SDK 任务尚未退出时 destroy/free client 或 config；socket 未主动唤醒，回调缺少当前 client/generation 过滤，任务与 destroy 路径所有权边界不清
- **修复模式：** 为 WSS client 建立显式 state/generation；destroy 先标记 disconnecting 并 abort/close fd 唤醒任务，再有界等待 task exit；只允许一个路径释放 client/config；回调过滤 stale client；锁内不做可能阻塞的 close/send
- **约束映射：** C24.1, C31.3, C33.1, C36.1, C43.1
- **频率：** 高
- **影响：** P0

### 2026-07-02 — TTS/speaker 热路径缺少池防护和可中断反压

- **来源：** BK7258 app_paltte 音频链路现场重启
- **平台：** BK
- **症状：** 多轮 TTS、打断或 speaker stop 后出现随机重启、payload/PCM 越界、播放拖住 stop
- **根因：** 音频 queue payload 所有权和池 slot 生命周期不够硬；变长 TTS payload/PCM 缺少首尾 guard；speaker 写入热路径持锁调用底层阻塞 API，stop/interruption 无法及时抢占
- **修复模式：** 固定池 slot 加 head/tail canary，入队/出队/free 前校验；记录 queued/played/dropped/backpressure/high-water；speaker 写入使用 generation interrupt、短超时锁和有限重试；stop 只请求任务退出并有界等待
- **约束映射：** C2.1, C31.1, C33.1, C43.5, C44.1
- **频率：** 高
- **影响：** P0

### 2026-07-02 — LVGL deinit API 存在但配置矩阵未链接

- **来源：** BK7258 app_paltte 提交前编译
- **平台：** BK
- **症状：** 为补生命周期对称性调用 `lv_deinit()` 后，链接失败：`undefined reference to lv_mem_deinit`
- **根因：** LVGL 头文件导出了 `lv_deinit()`，但当前 `LV_USE_STDLIB_MALLOC=LV_STDLIB_CUSTOM` 配置没有提供 `lv_mem_deinit()` 实现；只看源码 API 会误判可用性
- **修复模式：** LVGL 全局 deinit 必须经过目标工程链接验证；若内存 backend 不完整，应用层只删除 display/object 并停止平台 display driver；不要为通过 checker 硬调用未闭合的 SDK API
- **约束映射：** C1.2, C24.1, C36.1, C39.1
- **频率：** 中
- **影响：** P1

### 2026-07-02 — Kconfig secret overlay 与提交配置边界

- **来源：** BK7258 app_paltte secret scan 与构建脚本
- **平台：** 通用
- **症状：** secret scan 同时报出已提交 `config` 和本地 `config.secrets` 中的云端密钥
- **根因：** 真实凭据曾落入 tracked Kconfig；本地 overlay 虽被 ignore，但扫描器默认仍会扫到 ignored 文件，容易把“可构建本地密钥”和“入库泄漏”混在一起
- **修复模式：** tracked `config` 中敏感 Kconfig 永远为空；真实值只放 ignored `config.secrets`，由构建脚本临时 overlay 并在结束后恢复；提交前必须检查 `git check-ignore`、`git ls-files`、staged diff，并轮换曾入库的密钥
- **约束映射：** C9.1, C9.6, C36.1
- **频率：** 高
- **影响：** P0

### 2026-07-01 — OTA 断电回滚失败

- **来源：** 量产设备 OTA 升级后断电，重启后无法回滚
- **平台：** ESP32
- **症状：** OTA 升级后断电，设备重启后停留在新固件但功能异常
- **根因：** 未调用 `esp_ota_mark_app_valid_cancel_rollback()`，bootloader 认为新固件无效但无旧固件可回滚
- **修复模式：** 首次启动后做 health check，通过后调用 mark_valid_cancel_rollback
- **约束映射：** C22.2
- **频率：** 高
- **影响：** P0

### 2026-07-01 — 音频打断后 MIC 失效

- **来源：** BK7258 AI 闹钟，TTS 打断后 MIC 不再采集
- **平台：** BK
- **症状：** 用户打断 TTS 后，ASR 不再收到音频数据
- **根因：** speaker stop 时错误 deinit 了共享的 audio backend，导致 capture 路径也被释放
- **修复模式：** 区分 idle 与 deinit，stop playback 只进 idle，不释放共享 backend
- **约束映射：** C24.4, C10.1
- **频率：** 高
- **影响：** P0

### 2026-07-01 — LVGL 跨线程 HardFault

- **来源：** WSS 回调直接调用 lv_label_set_text
- **平台：** 通用
- **症状：** 网络消息到达时偶发 HardFault 或屏幕花屏
- **根因：** WSS 任务上下文直接调用 LVGL API，无 mutex 保护
- **修复模式：** 使用 lv_async_call 或 Queue → Presenter → View 模式
- **约束映射：** C1.1
- **频率：** 高
- **影响：** P0

### 2026-07-01 — cJSON 泄漏导致 heap 耗尽

- **来源：** WSS JSON 解析后 early return 未 Delete
- **平台：** 通用
- **症状：** 设备运行数小时后 malloc 失败
- **根因：** cJSON_Parse 后在错误路径 early return，未调用 cJSON_Delete
- **修复模式：** 使用 goto cleanup 模式，统一 cJSON_Delete
- **约束映射：** C3.1, C3.2
- **频率：** 高
- **影响：** P0

### 2026-07-01 — DMA cache 脏数据导致花屏

- **来源：** Camera preview 偶发花屏或旧帧
- **平台：** ESP32
- **症状：** LCD 显示偶发花屏、颜色错乱或显示旧帧
- **根因：** DMA 写入后 CPU 读前未 invalidate，CPU 读到 cache 中的旧数据
- **修复模式：** DMA 写后 CPU 读前 invalidate，CPU 写后 DMA 读前 clean
- **约束映射：** C28.2
- **频率：** 中
- **影响：** P0

### 2026-07-01 — 优先级反转导致音频卡顿

- **来源：** 低优先级任务持 mutex 时被中优先级任务抢占
- **平台：** 通用
- **症状：** 音频偶发卡顿，日志显示 I2S underrun
- **根因：** 共享资源用 binary semaphore 保护，无优先级继承
- **修复模式：** 使用 xSemaphoreCreateMutex（带优先级继承）
- **约束映射：** C15.2
- **频率：** 中
- **影响：** P1

### 2026-07-01 — 网络重连风暴

- **来源：** WiFi 断线后 tight loop 重连
- **平台：** 通用
- **症状：** WiFi 断线后 CPU 100%，其他任务饥饿
- **根因：** 重连无指数退避，立即重试
- **修复模式：** 指数退避（1s→2s→…→60s cap）
- **约束映射：** C20.1
- **频率：** 高
- **影响：** P0

### 2026-07-01 — 深睡眠后状态丢失

- **来源：** 设备深睡眠唤醒后重新初始化所有状态
- **平台：** ESP32
- **症状：** 唤醒后丢失用户设置、连接状态等
- **根因：** 深睡眠前未保存状态到 NVS
- **修复模式：** 深睡眠前 nvs_commit 保存关键状态
- **约束映射：** C21.1
- **频率：** 中
- **影响：** P0

---

## 经验统计

| 约束域 | 经验数 | 频率 | 说明 |
|--------|--------|------|------|
| C1 LVGL | 2 | 高 | 跨线程调用 / deinit 配置矩阵 |
| C3 cJSON | 1 | 高 | 泄漏 |
| C9 secrets | 1 | 高 | Kconfig secret overlay |
| C10 语音 | 1 | 高 | 打断后失效 |
| C15 优先级 | 1 | 中 | 优先级反转 |
| C20 网络 | 1 | 高 | 重连风暴 |
| C21 低功耗 | 1 | 中 | 状态丢失 |
| C22 OTA | 1 | 高 | 断电回滚 |
| C24 外设关闭 | 3 | 高 | 共享 backend / WSS task / LVGL display |
| C31 有界等待 | 2 | 高 | WSS/audio stop 有界化 |
| C33 生命周期 | 2 | 高 | 任务退出与 stop/deinit 对称 |
| C36 配置矩阵 | 3 | 高 | secret overlay / SDK API 链接验证 |
| C43 锁预算 | 2 | 高 | WSS close/send / speaker write 热路径 |
| C44 临界路径 | 1 | 高 | speaker 反压可中断 |
| C28 DMA | 1 | 中 | cache 脏数据 |
