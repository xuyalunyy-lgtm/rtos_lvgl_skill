# Workflow: L2 Code Review

**触发：** code review / audit / 审查 / 嵌入式 C 代码质量检查

```yaml
# Workflow Input Schema
inputs:
  required:
    - name: source_dir
      type: string
      description: 用户源码目录（如 ./src）
    - name: platform
      type: enum[esp32, stm32, jl, bk, freertos, zephyr]
      description: 目标平台
  optional:
    - name: constraints
      type: string[]
      description: 指定约束 ID（如 C1, C7）
    - name: budget
      type: enum[compact, standard, full]
      default: standard
      description: context_router 预算级别

# Workflow Output Schema
outputs:
  format: markdown
  sections:
    - 结论（通过/需修复，一句话）
    - 违规项（C#.file:line — 问题 — 修复建议，引用 good 范例）
    - Checker 结果（run_review 摘要或「未运行」）
    - 修复优先级（P0 安全/崩溃 → P1 泄漏/死锁 → P2 风格）
  exit_code: 0=通过, 1=发现问题
```

<thinking>
1. 确认目标平台（ESP32/STM32/JL/BK）
2. 识别涉及模块：网络 / LVGL / 音频 / 音视频管线 / 编解码格式 / 时钟漂移/Jitter / DMA cache/零拷贝 / cJSON / 模块契约 / 任务拓扑 / 超时预算 / 热路径 / 关键路径预算 / 数据拷贝预算 / 背压降级 / 故障恢复 / 配置矩阵 / 一键复现 / 回归样本 / 板级资源
3. 仅加载与本审查相关的 scene prompt（勿加载全部 prompts/）
</thinking>

## Step 1 — 读总纲

读取 [references/core_rules.md](../references/core_rules.md) + [constraint_index.md](../references/constraint_index.md)（违规报告引用 `C#.#`；需正例/checker 列时再读 [constraint_detail.md](../references/constraint_detail.md)）。Prompt 选型 → [skill_structure.md](../references/skill_structure.md)

## Step 2 — 反例对照

| 嫌疑 | 对照 |
|------|------|
| 跨线程 LVGL | [bad_lvgl_cross_thread.c](../examples/bad_lvgl_cross_thread.c) |
| ISR 阻塞 | [bad_isr_blocking.c](../examples/bad_isr_blocking.c) |
| cJSON 泄漏 | [bad_cjson_leak.c](../examples/bad_cjson_leak.c) |
| **Queue 栈指针/cJSON*** | [bad_queue_stack_pointer.c](../examples/bad_queue_stack_pointer.c) |
| WSS 栈/重连/init 顺序 | [bad_wss_blocking.c](../examples/bad_wss_blocking.c) → [good_wss_reconnect.c](../examples/good_wss_reconnect.c) · [good_boot_sequence.c](../examples/good_boot_sequence.c) |

按需深读：[lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt)、[memory_ownership.txt](../prompts/memory_ownership.txt)、[deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt)、[memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt)（堆/栈/缩池嫌疑）、[boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt)（init/WDT/portMAX_DELAY）、[runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt)（模块契约 / task queue 拓扑 / timeout budget / observability / lifecycle / hot path / critical path budget / copy budget / backpressure / recovery / config matrix / reproduce loop / regression sample / board resources）、[voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt)（`*prompt*` / `*voice*` / `*capture*` / `*uplink*` / ASR 空 — 平台 API 见 `platforms/xxx.md`）、[peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt)（`stop` / `deinit` / TTS 打断 / shared audio handle）、[av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt)（`camera` / `video` / `preview` / 音画不同步 / 掉帧 / lip-sync）、[av_codec_format.txt](../prompts/av_codec_format.txt)（sample rate / channels / bit depth / Opus / stride / RGB565）、[av_clock_jitter.txt](../prompts/av_clock_jitter.txt)（drift / jitter buffer / clock recovery / underrun / overrun / PTS）、[av_dma_buffer_lifecycle.txt](../prompts/av_dma_buffer_lifecycle.txt)（DMA buffer / cache clean/invalidate / zero-copy / frame pool / 旧帧花屏）、[error_handling.txt](../prompts/error_handling.txt)（未检查返回值 / NULL 解引用）、[logging_debug.txt](../prompts/logging_debug.txt)（裸 printf / ISR 日志 / 脱敏）、[logging_management_constraints.md](../references/logging_management_constraints.md)（日志 profile / 限频 / 结构化 / ring buffer）、[coding_style.txt](../prompts/coding_style.txt)（函数 >80 行 / 命名不规范）

## Step 3 — 自动化 checker（完整版）

在用户源码目录执行（**仅** `src/` 或用户指定路径，不扫 home / `.env`）：

```bash
python tools/run_review.py --dir ./src --platform <esp32|stm32|jl|bk|freertos>
```

含 `cjson_leak_checker`、`isr_safety_checker`、`lvgl_thread_checker`、**`queue_ownership_checker`（铁律 #2）**。

工程审查另跑密钥扫描（C9）：

```bash
python tools/secret_scan_checker.py --dir <产品>/projects --git-remotes
```

或使用 `run_review.py --scan-secrets` 一并执行。

Python 不可用：标注「待本地补验」，改用手工核对 checklist。

## Step 4 — 输出

<output_format>

```markdown
## 结论
通过 / 需修复（一句话）

## 违规项（对照 constraint_detail `C#.#`）
- C2.2 — file:line — 问题 — 修复建议（引用 good 范例模式）

## Checker 结果
（粘贴 run_review 摘要或「未运行」）

## 修复优先级
P0 安全/崩溃 → P1 泄漏/死锁 → P2 风格
```

</output_format>

---
验收标准：[acceptance_criteria.md](../references/acceptance_criteria.md#code-reviewl2_code_review)
