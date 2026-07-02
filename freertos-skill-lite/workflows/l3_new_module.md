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

## Step 1 — 架构 + Codegen Contract

1. 读 [references/core_rules.md](../references/core_rules.md)（优先级 + MVP + 文件归属）
2. 读 `platforms/xxx.md`
3. 输出相对优先级表 + 平台数值 + 文件归属表 + 模块契约 + task/queue 拓扑表
4. **输出 Codegen Contract**（参见 [codegen_contract.md](../references/codegen_contract.md)）：
   - workflow、platform、frameworks、module_type
   - tasks（name/stack/priority）、queues（name/depth/backpressure/timeout）、locks、timers
   - 必选约束 ID（如 C1,C4,C29,C33,C37）
   - 禁止模式（如裸 portMAX_DELAY、ISR blocking、queue 传栈指针）
   - 验证命令

## Step 2 — 场景 prompt（按需 1–3 个）

| 模块 | Prompt | 正例 |
|------|--------|------|
| 启动编排 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) | 完整版 `examples/good_boot_sequence.c` |
| 网络/WSS | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) + [queue_event_bus.txt](../prompts/queue_event_bus.txt) | 完整版 `examples/good_wss_json_parse.c` |
| WSS 重连 | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt)（SNTP + 退避） | 完整版 `examples/good_wss_reconnect.c` |
| UI | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | 完整版 `examples/good_mvp_pattern.c` |
| 音频 | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | — |
| 音视频管线 | [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) + [av_codec_format.txt](../prompts/av_codec_format.txt) + [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) + [av_dma_buffer_lifecycle.txt](../prompts/av_dma_buffer_lifecycle.txt) + [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | 完整版 `examples/good_av_pipeline_sync.c` + 完整版 `examples/good_media_format_contract.c` + 完整版 `examples/good_av_clock_jitter.c` + 完整版 `examples/good_av_dma_buffer_lifecycle.c` |
| JSON | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) | 完整版 `examples/good_wss_json_parse.c` |
| Presenter | [memory_ownership.txt](../prompts/memory_ownership.txt) | 完整版 `examples/good_presenter_consumer.c` |
| 多任务/通用模块效率 | [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | — |

## Step 3 — 代码生成与落地（Lite）

**默认：** [core_rules.md](../references/core_rules.md) **自主实施模式** — 按 scene prompt 手写骨架，直接写入用户工程。

**Lite 限制：** 无 `examples/`、`tools/`、`mvp_codegen`、`run_review`；按 [lite_manual_checklist.md](../references/lite_manual_checklist.md) 完成人工审查。

## Step 4 — 编译闭环（必做）

按 `platforms/xxx.md` 执行编译；失败则修错重编，直至 **0 error**。

## Step 5 — 人工校验（Lite）

执行 [lite_manual_checklist.md](../references/lite_manual_checklist.md)，并按已加载 prompt 手工核对 C1/C2/C3/C4 等约束。

## Step 6 — 输出 + 约束证明

输出：
- [core_rules.md](../references/core_rules.md) L3 模板全文 + 校验 checklist
- `generation_manifest.json`（生成清单）
- 约束证明：列出每个必选约束如何在生成代码中满足（注释、结构、API 调用）
