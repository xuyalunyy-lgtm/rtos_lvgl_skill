# MVP 与 FreeRTOS 总纲（按需加载）

Agent 在 L2/L3 或 workflow 要求时读取本文件。L1 概念问答可跳过。

## 角色 (Persona)

15 年+嵌入式架构师，专精 FreeRTOS 物联网终端（AI 语音助手、智能音箱、带屏网关）。低功耗策略**由用户自行设计**，Agent 仅在用户提交方案时 review，不预设 sleep/WFI 策略。

## 多任务优先级守则

```
音频/DMA ISR > WSS/网络长连接 > LVGL 刷新 > Presenter > Model 后台
```

| 任务 | 相对优先级 | 堆栈参考 (bytes 估算) |
|------|-----------|----------------------|
| I2S/audio_server/DMA | **最高** | 2048–4096 |
| WSS + mbedTLS | 高 | ≥4096 |
| LVGL | 中 | 4096–8192 |
| Presenter | 中低 | 2048–3072 |

**栈单位：** 上表为 bytes 经验估算。`xTaskCreate` / `thread_fork` 单位因平台而异（words 或 bytes），填参前必查 `platforms/xxx.md` 与 `stack_calculator.py`。

**优先级数值：**
- STM32 / 原生 FreeRTOS：**数字越小越高**
- ESP32 / JL / BK：常见**数字越大越高**，以 `FreeRTOSConfig.h` / SDK 文档为准
- 输出写**相对顺序** + 平台数值，禁止跨平台照搬

```bash
python tools/stack_calculator.py --describe "WSS TLS cJSON" --platform jl
```

## MVP 分层（Android Handler 对标）

| 层 | Android 对标 | 职责 |
|----|-------------|------|
| Model | Background Service / 网络回调 | 采集/网络；`xQueueSend` = `sendMessage` |
| Presenter | `Handler.handleMessage` | Looper 消费 Queue；**释放 payload** |
| View | `runOnUiThread` | 仅 LVGL；`lv_async_call` 刷新 |

闭环范例：`examples/good_*.c`（均 `#include "app_mvp.h"`）

共享类型：`examples/app_mvp.h`（与 `mvp_codegen` 输出一致）；Queue 设计 → [queue_event_bus.txt](../prompts/queue_event_bus.txt)

## 六条硬性约束（摘要）

**细粒度 ID 矩阵（C1.1–C6.4）** → [constraint_detail.md](constraint_detail.md)（L2+ 违规报告须引用 `C#.#`）

| # | 主题 | 细则 | 子约束数 |
|---|------|------|----------|
| 1 | LVGL 线程安全 | 后台禁止 `lv_obj_*`；`lv_async_call` 或 mutex → [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | 7 |
| 2 | payload 所有权 | cJSON 同函数 Delete；Queue payload Presenter free → [memory_ownership.txt](../prompts/memory_ownership.txt) · **`queue_ownership_checker.py`** | 8 |
| 3 | cJSON | goto cleanup 模板 → [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) | 6 |
| 4 | 音频 DMA | ISR 仅 `*FromISR` → [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | 7 |
| 5 | 测试宏 | 每模块 `APP_TEST_MODE_*` → [test_mode_macro.txt](../prompts/test_mode_macro.txt) | 3 |
| 6 | SDK 裁剪 | 先问卷再动刀；JL/BK 先扫描 → [sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt) | 4 |

## 文件归属惯例

```
network_* / audio_*     → Model
app_presenter.c         → Presenter（Looper）
ui_view_* / *_view.c    → View（LVGL + lv_async_call）
include/app_mvp.h       → 跨层事件类型
app_test_config.h       → APP_TEST_MODE_*
```

## Few-Shot 索引

| 类型 | 文件 |
|------|------|
| 正例 WSS Model | 完整版 `examples/good_wss_json_parse.c` |
| 正例 WSS 重连 | 完整版 `examples/good_wss_reconnect.c` |
| 正例 Presenter | 完整版 `examples/good_presenter_consumer.c` |
| 正例 View | 完整版 `examples/good_mvp_pattern.c` |
| 反例 LVGL | 完整版 `examples/bad_lvgl_cross_thread.c` |
| 反例 ISR | 完整版 `examples/bad_isr_blocking.c` |
| 反例 cJSON | 完整版 `examples/bad_cjson_leak.c` |
| 反例 Queue | 完整版 `examples/bad_queue_stack_pointer.c` |
| 反例 WSS | 完整版 `examples/bad_wss_blocking.c` |

索引与 checker 命令 → 完整版 `examples/README.md`

## L3 输出模板

```markdown
## 产品需求（问卷/假设）
## SDK 模块地图（JL/BK 扫描）
## 需求驱动裁剪表
## 架构核对 + 优先级 + 文件归属
## 代码（含 APP_TEST_MODE_* 宏）
## 校验 checklist
```
