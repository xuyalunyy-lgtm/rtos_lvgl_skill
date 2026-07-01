# Workflow: L3 新增模块 / 多任务设计

**触发：** 新功能模块、WSS+LVGL MVP、多任务架构、codegen 骨架。

<thinking>
1. 判定是否需 Step 0 裁剪（新 Demo → 是；量产加功能 → 增量）
2. 读 platform 专档 + core_rules 优先级表 + **自主实施模式**
3. 生成代码须对齐 examples/ 正例风格；**无需逐步确认，编译通过为止**
</thinking>

## Step 0 — 裁剪（按需）

| 场景 | 动作 |
|------|------|
| 全新 Demo | 走 [l3_sdk_trim.md](l3_sdk_trim.md) |
| JL/BK | 强制 SDK 扫描 |
| 量产加功能 | 增量问卷 |
| 单模块追加 | **跳过** |

## Step 1 — 架构

1. 读 [references/core_rules.md](../references/core_rules.md)（优先级 + MVP + 文件归属）
2. 读 `platforms/xxx.md`
3. 输出相对优先级表 + 平台数值 + 文件归属表 + 模块契约 + task/queue 拓扑表

## Step 2 — 场景 prompt（按需 1–3 个）

| 模块 | Prompt | 正例 |
|------|--------|------|
| 启动编排 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) | [good_boot_sequence.c](../examples/good_boot_sequence.c) |
| 网络/WSS | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) + [queue_event_bus.txt](../prompts/queue_event_bus.txt) | [good_wss_json_parse.c](../examples/good_wss_json_parse.c) |
| WSS 重连 | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt)（SNTP + 退避） | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) |
| UI | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | [good_mvp_pattern.c](../examples/good_mvp_pattern.c) |
| 音频 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | — |
| 音视频管线 | [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) + [av_codec_format.txt](../prompts/av_codec_format.txt) + [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) + [av_dma_buffer_lifecycle.txt](../prompts/av_dma_buffer_lifecycle.txt) + [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | [good_av_pipeline_sync.c](../examples/good_av_pipeline_sync.c) + [good_media_format_contract.c](../examples/good_media_format_contract.c) + [good_av_clock_jitter.c](../examples/good_av_clock_jitter.c) + [good_av_dma_buffer_lifecycle.c](../examples/good_av_dma_buffer_lifecycle.c) |
| JSON | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) | [good_wss_json_parse.c](../examples/good_wss_json_parse.c) |
| Presenter | [memory_ownership.txt](../prompts/memory_ownership.txt) | [good_presenter_consumer.c](../examples/good_presenter_consumer.c) |
| 多任务/通用模块效率 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | — |

## Step 3 — 代码生成与落地（自主实施）

**默认：** [core_rules.md](../references/core_rules.md) **自主实施模式** — 全权改工程文件，无需逐步确认。

**方式 A — 范例对齐：** 参照 [good_wss_json_parse.c](../examples/good_wss_json_parse.c) 等三件套，直接写入用户工程。

**方式 B — codegen：**

```bash
python tools/mvp_codegen_tool.py <Module> --platform <jl|bk|esp32|stm32> -o ./generated
```

输出含 `app_mvp.h`；多次生成须**手动合并** `app_test_config.h` 中 `APP_TEST_MODE_*`。

## Step 4 — 编译闭环（必做）

按 `platforms/xxx.md` 执行编译；失败则修错重编，直至 **0 error**。

```bash
# 示例 — 以平台专档为准
make bk7258          # BK
idf.py build         # ESP32
make ac791n_demo_wifi  # JL
```

## Step 5 — 工具校验

```bash
python tools/stack_calculator.py --describe "..." --platform xxx
python tools/run_review.py --dir ./src --platform xxx
```

## Step 6 — 输出

[core_rules.md](../references/core_rules.md) L3 模板全文 + 校验 checklist。
