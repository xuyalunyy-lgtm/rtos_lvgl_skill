# Skill 结构总览（维护 / L2+ 按需加载）

Agent 维护 skill 或不确定「该读哪个文件」时读取本文件。**L1 概念问答不必加载。**

## 四层加载模型

```
L0 控制平面   SKILL.md              意图路由 · 铁律索引 · rules（禁止膨胀）
L1 编排       workflows/*.md        选定 1 个 workflow，按 Step 顺序执行
L2 总纲       references/           core_rules · constraint_index · 本文件
L3 场景       prompts/*.txt         workflow 指定 1–3 个，禁止全加载
     平台     platforms/*.md        workflow Step 1 加载 1 个
L4 可执行     examples/ · tools/    完整版 L2+；Lite 无此层
```

**铁律：** 每层只向下加载，禁止跳层把 12 个 prompt 塞进 context。

---

## 目录职责

| 路径 | 职责 | 谁维护 | Lite |
|------|------|--------|------|
| `SKILL.md` | 控制平面（<100 行） | 人工 | 自动生成 |
| `workflows/` | 步骤编排、输出模板 | 人工 | 同步 + patch |
| `references/` | 总纲、约束矩阵、结构、日志 | 人工 | 同步 |
| `references/constraint_index.md` | C#.# 速查（L2 默认，省 token） | 人工 | 同步 |
| `references/git_commit_style.md` | 多仓 Git 提交说明规范 | 人工 | 同步 |
| `references/claude_code.md` | Claude Code 懒加载指南 | 人工 | 同步 |
| `prompts/` | 场景专链（深细节） | 人工 | 同步 |
| `platforms/` | 芯片/SDK 事实 | 人工 | 同步 |
| `examples/` | good/bad 范例、`app_mvp.h` | 人工 + checker | **无** |
| `tools/` | checker、codegen、fixtures | 人工 + CI | **无** |
| `scripts/` | sync、iterate、install | 人工 | 部分复制 |
| `freertos-skill-lite/` | Lite 分发包 | **sync 生成** | — |

---

## Workflow → 必读 / 按需加载

| Workflow | L2 必读 | L3 按需（1–3） | L4 完整版 |
|----------|---------|----------------|-----------|
| L1 无 | — | — | — |
| [l2_code_review](../workflows/l2_code_review.md) | core_rules + **constraint_index** | 嫌疑场景 prompt | run_review + 单文件 example |
| [debug_crash](../workflows/debug_crash.md) | constraint_detail 症状表 | 症状对应 prompt | run_review + 反例 |
| [l3_sdk_trim](../workflows/l3_sdk_trim.md) | core_rules | sdk_trim_prune | — |
| [l3_new_module](../workflows/l3_new_module.md) | core_rules | 模块表 prompt | mvp_codegen / good_* |
| [hw_sw_cocodebug](../workflows/hw_sw_cocodebug.md) | core_rules（C8 初始化顺序） | 平台引脚复用 | — |
| [l3_bring_up](../workflows/l3_bring_up.md) | core_rules + hw_sw_cocodebug IO 表 | boot_wdt_lifecycle + audio_dma_pingpong | run_review + good_boot_sequence |
| [l2_memory_analysis](../workflows/l2_memory_analysis.md) | core_rules + constraint_index | memory_alloc_optimize + cjson_safe_parse | run_review + stack_calculator |
| [l3_lvgl_page](../workflows/l3_lvgl_page.md) | core_rules（C1 线程安全） | lvgl_thread_safety | — |
| [self_iterate](../workflows/self_iterate.md) | **本文件** + iteration_log | 受影响层 prompt | skill_iterate |

用户要求 **git commit / 提交** → 读 [git_commit_style.md](git_commit_style.md)（无需单独 workflow）

Workflow 索引 → [workflows/README.md](../workflows/README.md)

---

## 场景 Prompt 目录（C 域 → 文件）

| C 域 | 场景 | 文件 |
|------|------|------|
| C1 | LVGL 线程 / v8v9 | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) · [lvgl_v8_v9_diff.txt](../prompts/lvgl_v8_v9_diff.txt) |
| C2 | Queue / 所有权 / 死锁 | [memory_ownership.txt](../prompts/memory_ownership.txt) · [queue_event_bus.txt](../prompts/queue_event_bus.txt) · [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) |
| C3 | cJSON | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) |
| C4 | 音频 DMA / ISR | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) |
| C5 | 测试宏 | [test_mode_macro.txt](../prompts/test_mode_macro.txt) |
| C6 | SDK 裁剪 | [sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt) |
| C7 | 内存分配优化 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) |
| C8 | 启动 / WDT / 阻塞 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) |
| C9 | 密钥 / 凭证 | [secrets_kconfig.txt](../prompts/secrets_kconfig.txt) |
| C10 | 语音 / ASR / Uplink | [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) |
| C11 | 编码规范 | [coding_style.txt](../prompts/coding_style.txt) |
| C12 | 错误处理 | [error_handling.txt](../prompts/error_handling.txt) |
| C13 | 状态机 | [state_machine_patterns.txt](../prompts/state_machine_patterns.txt) |
| C14 | 日志规范 | [logging_debug.txt](../prompts/logging_debug.txt) |
| C15 | 优先级与通信 | [inter_task_communication.txt](../prompts/inter_task_communication.txt) |
| C16 | 定时器管理 | [timer_management.txt](../prompts/timer_management.txt) |
| C17 | 多核 IPC | [multi_core_ipc.txt](../prompts/multi_core_ipc.txt) |
| 网络 | WSS / mbedTLS / 栈 | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) |
| Crash | 日志解读 | [crash_log_decode.txt](../prompts/crash_log_decode.txt) |
| 同步 | FreeRTOS 原语 | [freertos_sync_primitives.txt](../prompts/freertos_sync_primitives.txt) |
| C18 | 外设驱动安全 | [peripheral_driver_safety.txt](../prompts/peripheral_driver_safety.txt) |
| C19 | Flash/NVS 安全 | [flash_nvs_safety.txt](../prompts/flash_nvs_safety.txt) |
| C20 | 网络韧性 | [network_resilience.txt](../prompts/network_resilience.txt) |
| C21 | 低功耗管理 | [low_power_management.txt](../prompts/low_power_management.txt) |
| C23 | 显示驱动 | [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) |
| C24 | 外设关闭安全 | [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) |
| C25 | 音视频管线 / A/V Sync | [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) |
| C26 | 编解码 / 媒体格式一致性 | [av_codec_format.txt](../prompts/av_codec_format.txt) |
| C27 | 时钟漂移 / Jitter Buffer | [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) |

约束 ID 细则 → [constraint_detail.md](constraint_detail.md) · L2 速查 → [constraint_index.md](constraint_index.md) · **知识图谱** → [constraint_graph.md](constraint_graph.md)

> C1–C27，26 个约束域，143 条规则。

---

## Claude Code（省 token）

安装 → [claude_code.md](claude_code.md) · 项目模板 → [templates/CLAUDE.embedded.md](../templates/CLAUDE.embedded.md)

| 原则 | 说明 |
|------|------|
| 懒加载 | 仅 workflow 指定文件；禁 Glob prompts/ |
| L2 默认 | `constraint_index.md` 替代 detail 全文 |
| 工具优先 | `run_review.py` 代替读 checker 源码 |
| 项目索引 | 固件仓 `CLAUDE.md` <500 token + `.claudeignore` |

## Cursor 命中率（DeepSeek 等）

固件仓 Rule 模板 → [templates/cursor-rule.embedded.mdc](../templates/cursor-rule.embedded.mdc) · 说明 → [INSTALL.md](../INSTALL.md)

| 原则 | 说明 |
|------|------|
| description | 中文 + `Use when` 触发词（SKILL frontmatter） |
| 项目 Rule | `globs: **/*.{c,h}` 编辑 C 时强制 Read skill |
| 显式点名 | `@freertos-embedded-architect` |

## 产品线 Profile（`product_profiles/`）

| 平台 | 文件 | 必选约束 | 特性 |
|------|------|----------|------|
| ESP32 | `esp32.json` | C1-C4,C7-C9,C11-C12,C14-C15,C23,C25-C27 | WiFi+BLE+LVGL+I2S+Camera, 双核, PSRAM |
| STM32 | `stm32.json` | C2-C4,C7-C9,C11-C12,C14-C15,C23 | LVGL+I2S+TLS, 单核 Cortex-M |
| JL | `jl.json` | C1-C4,C6-C15,C23,C25-C27 | WiFi+BLE+LVGL+I2S+语音/视频, 双核 RISC-V |
| BK | `bk.json` | C1-C4,C6-C15,C17,C23,C25-C27 | WiFi+BLE+LVGL+AVDK音频+语音/视频, 双核 IPC |

加载方式：`python tools/product_profile.py <platform>` · `--json` · `--stack <task>`

Agent 在 L3 开始前**推荐**加载产品 profile：自动获取必选约束、栈建议、常见坑点。

## 工具目录（完整版 · workflow 内调用）

| 用途 | 命令 |
|------|------|
| 一键 L2 | `python tools/run_review.py --dir src/ --platform xxx` |
| 自测 | `python tools/run_review.py --self-test` |
| 铁律范例约束 | `python tools/run_review.py --validate-examples` |
| Lite 同步 | `python scripts/sync_lite.py` · Windows：`.\scripts\sync_lite.cmd` |
| 迭代验证 | `python scripts/skill_iterate.py --check --sync` · Windows：`.\scripts\skill_iterate.cmd -Sync` |
| 安装 Cursor | `.\scripts\install_skill.ps1`（见 [INSTALL.md](../INSTALL.md)） |
| 安装 Claude Code | `.\scripts\install_claude_code.ps1`（见 [claude_code.md](claude_code.md)） |
| C10 语音时序 | `python tools/voice_sequence_checker.py --dir src/` |
| C18 外设驱动 | `python tools/peripheral_driver_checker.py --dir src/` |
| C19 Flash/NVS | `python tools/flash_nvs_checker.py --dir src/` |
| C20 网络韧性 | `python tools/network_resilience_checker.py --dir src/` |
| C21 低功耗 | `python tools/low_power_checker.py --dir src/` |
| C23 显示驱动 | `python tools/display_driver_checker.py --dir src/` |
| C25 音视频管线 | `python tools/av_pipeline_checker.py --dir src/` |
| C26 编解码格式 | `python tools/media_format_checker.py --dir src/` |
| C27 时钟/Jitter | `python tools/av_clock_jitter_checker.py --dir src/` |
| C13 状态机 | `python tools/state_machine_checker.py --dir src/` |
| C14.4 日志脱敏 | `python tools/log_desensitize_checker.py --dir src/` |
| C16 定时器 | `python tools/timer_checker.py --dir src/` |
| 链接检查 | `python tools/check_links.py` |
| C14 日志检查 | `python tools/logging_checker.py --dir src/` |
| C12 返回值检查 | `python tools/return_check_checker.py --dir src/` |
| C11.5 函数长度 | `python tools/function_length_checker.py --dir src/` |
| MVP 骨架 | `python tools/mvp_codegen_tool.py Module --platform jl -o ./generated` |
| 自动约束发现 | `python tools/constraint_discovery.py --dir src/` · `--report proposal.md` · `--json` |

Checker 与 C#.# 映射 → [examples/README.md](../examples/README.md)

---

## 维护：改哪一层

```
改铁律/约束 ID     → core_rules.md + constraint_detail.md (+ 必要时 prompt 一句)
改场景深细节       → prompts/xxx.txt（检查 workflow 引用）
改步骤/输出格式    → workflows/xxx.md（检查 SKILL 路由表）
改平台事实         → platforms/xxx.md
改范例/checker     → examples/ + tools/fixtures/（跑 validate-examples）
改控制平面         → SKILL.md（保持 <100 行）+ skill_lite_body.md → sync
改 Skill 结构说明  → 本文件 + workflows/README.md + README.md
```

**禁止：** 拆多个 skill；未问卷扩 SDK 删除清单；手改 `freertos-skill-lite/` 正文。

---

## 完整版 vs Lite 结构差

| 层 | 完整版 | Lite |
|----|--------|------|
| L0 | SKILL.md | sync 生成 |
| L1 | 全部 workflow | l2 用 lite 子 workflow |
| L2–L3 | 同左 | 同左（无 examples 链接） |
| L4 | examples + tools | 用 lite_manual_checklist 替代 |
