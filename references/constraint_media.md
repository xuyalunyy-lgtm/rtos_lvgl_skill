# Iron Rule Constraint Shard: Audio/Video Pipeline and Codec (Media)

This file contains constraints for audio/video pipeline/A/V Sync, audio/video codec/media format consistency, audio/video clock drift/Jitter Buffer, etc.

> Corresponding constraint IDs: C25–C27
> Other shards:[constraint_review.md](constraint_review.md) | [constraint_memory.md](constraint_memory.md) | [constraint_rtos.md](constraint_rtos.md) | [constraint_platform.md](constraint_platform.md) | [constraint_ota.md](constraint_ota.md) | [constraint_recover.md](constraint_recover.md)

---

## Severity Definitions

| Level | Meaning | Action |
|------|------|------|
| P0 | Guaranteed crash / leak / deadlock | Blocks merge; MUST attach fix diff or example reference |
| P1 | High-probability mass-production issue | MUST fix in this iteration or register risk |
| P2 | Maintainability / testability | Recommended fix, can be scheduled |

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
