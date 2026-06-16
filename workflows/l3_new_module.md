# Workflow: L3 新增模块 / 多任务设计

**触发：** 新功能模块、WSS+LVGL MVP、多任务架构、codegen 骨架。

<thinking>
1. 判定是否需 Step 0 裁剪（新 Demo → 是；量产加功能 → 增量）
2. 读 platform 专档 + core_rules 优先级表
3. 生成代码须对齐 examples/ 正例风格
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
3. 输出相对优先级表 + 平台数值 + 文件归属表

## Step 2 — 场景 prompt（按需 1–3 个）

| 模块 | Prompt | 正例 |
|------|--------|------|
| 启动编排 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) | [good_boot_sequence.c](../examples/good_boot_sequence.c) |
| 网络/WSS | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) + [queue_event_bus.txt](../prompts/queue_event_bus.txt) | [good_wss_json_parse.c](../examples/good_wss_json_parse.c) |
| WSS 重连 | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt)（SNTP + 退避） | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) |
| UI | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | [good_mvp_pattern.c](../examples/good_mvp_pattern.c) |
| 音频 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | — |
| JSON | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) | [good_wss_json_parse.c](../examples/good_wss_json_parse.c) |
| Presenter | [memory_ownership.txt](../prompts/memory_ownership.txt) | [good_presenter_consumer.c](../examples/good_presenter_consumer.c) |

## Step 3 — 代码生成

**方式 A — 范例对齐：** 参照 [good_wss_json_parse.c](../examples/good_wss_json_parse.c) 等三件套。

**方式 B — codegen：**

```bash
python tools/mvp_codegen_tool.py <Module> --platform <jl|bk|esp32|stm32> -o ./generated
```

输出含 `app_mvp.h`；多次生成须**手动合并** `app_test_config.h` 中 `APP_TEST_MODE_*`。

## Step 4 — 工具校验

```bash
python tools/stack_calculator.py --describe "..." --platform xxx
python tools/run_review.py --dir ./generated --platform xxx
```

## Step 5 — 输出

[core_rules.md](../references/core_rules.md) L3 模板全文 + 校验 checklist。
