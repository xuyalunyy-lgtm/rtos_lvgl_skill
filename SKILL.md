---
name: freertos-embedded-architect
metadata:
  version: 45.0.0
description: >-
  FreeRTOS/IoT 固件架构师：代码审查、LVGL UI 生成、崩溃调试、OTA 安全、SDK 裁剪、
  模块契约、任务拓扑、DMA/ISR 安全、音视频同步、时钟抖动、零拷贝缓冲区、cJSON 泄漏防护、
  WSS/mbedTLS、传感器集成、锁预算、优先级反转、临界区。多平台（ESP32/STM32/JL/BK/Zephyr）。
  Use when working on embedded C, RTOS tasks, board bring-up, memory analysis, peripheral drivers, or firmware review.
---
# FreeRTOS 嵌入式架构师

路由规则：将用户的第一条消息匹配到**一个**工作流。
优先级：1 = 最高（调试/安全），2 = 高（审查），3 = 正常（生成）。
排除：如果输入同时包含 Keywords 和 Exclude，跳过该路由。
按优先级从高到低匹配；同一优先级内，取关键字命中最多的。

| Keywords | Exclude | Priority | Workflow |
|----------|---------|----------|----------|
| crash, HardFault, WDT, deadlock, frozen, 死机, 看门狗, 崩溃, backtrace, Guru Meditation, watchdog, stack overflow crash, exception, 卡在, 卡死, 重启 | — | 1 | debug_crash |
| review, audit, 审查, check, ISR, DMA, cJSON, 代码质量, code quality, static analysis, lint, OTA, 安全, 看看代码, 代码规范, code review | crash, 死机, 卡死, 卡在, 重启 | 2 | l2_code_review |
| co-debug, GPIO conflict, 硬件协同, GPIO, IO conflict, peripheral conflict, pin mux, 引脚冲突, pin conflict | — | 2 | hw_sw_cocodebug |
| memory, leak, 内存, 堆栈, heap, stack overflow, memory analysis, pool, fragmentation, 堆栈溢出, 内存泄漏 | crash, 死机, 卡死 | 2 | l2_memory_analysis |
| project review, 项目审查, workspace review, 全项目, 整个项目, 整个工程, project audit, 项目检查 | crash, 死机 | 2 | l2_project_review |
| manifest, 多页, multi-page, Router, Presenter, Model, 脚手架, scaffold, app architecture, 应用架构, 多页面 | — | 3 | l3_lvgl_page (manifest sub-path) |
| bring-up, 板级, 最小系统, peripheral validation, board init, boot, startup, 外设, 新板, first boot, 上电, 串口没输出, 启动流程 | — | 3 | l3_bring_up |
| LVGL, UI, page, 页面, 设计截图, design, 界面, GUI, widget | crash, 死机, 卡死, frozen, 卡在 | 3 | l3_lvgl_page |
| new module, 新模块, task, 任务, multitask, module design, 模块设计, module, 模块 | crash, review, 审查, leak, 内存 | 3 | l3_new_module |
| SDK trim, 裁剪, 裁, driver prune, sdk_trim, component pruning, 减小体积, trim, prune, flash不够, 精简, 缩减 | — | 3 | l3_sdk_trim |
组合请求：优先匹配用户主要交付物对应的工作流。
仅在该工作流明确需要时才加载补充材料。
如果主要任务不明确，先问一个澄清问题再继续。
---
## 审查域
**触发：**代码审查 / 审计 / 内存分析 / 工程审查 / 软硬件协同调试
**输出：**风险等级、验证结果和可执行建议
| 工作流 | 触发条件 |
|----------|---------|
| l2_code_review.md | 代码审查 / 审计 |
| l2_code_review_lite.md | 轻量人工审查 |
| l2_project_review.md | 工程 / 工作区审查 |
| l2_memory_analysis.md | 内存分析 / 泄漏 |
| hw_sw_cocodebug.md | 软硬件协同 / GPIO 冲突 |
- **必读:** `references/core_rules.md`, `references/constraint_index.md`
- **按需:** `platforms/{platform}.md`, workflow 指定的 `prompts/{scene}.txt`
- **工具:** `python tools/run_review.py`, `python tools/context_router.py`
- **禁止:** `ui/`, `schemas/`
---
## 生成域
**触发：**LVGL 页面 / manifest / 新模块 / 板级启动 / SDK 裁剪
**输出：**最小可编译固件产物；验证证据记录在内部运行台账中
| 工作流 | 触发条件 |
|----------|---------|
| l3_lvgl_page.md | LVGL 页面 / manifest 生成 |
| l3_new_module.md | 新模块 / 多任务 MVP |
| l3_bring_up.md | 板级启动 |
| l3_sdk_trim.md | SDK 裁剪 |
- **必读:** `references/core_rules.md`
- **LVGL 必读:** `workflows/l3_lvgl_page.md`
- **按需:** `platforms/{platform}.md`, `references/lvgl_*`
- **工具:** 使用目标工程的 LVGL 构建、渲染和测试工具。对未确认的视觉或交互意图先澄清，再交付最小可编译文件集。
- **禁止:** `tools/*_checker.py`, `examples/bad_*.c`
---
## 调试域
**触发：**崩溃 / HardFault / 死机 / WDT / 崩溃日志 / 卡死 / 死锁
**输出：**根因假设、最小验证步骤和下一步行动计划
| 工作流 | 触发条件 |
|----------|---------|
| debug_crash.md | HardFault / WDT / 崩溃转储 |
- **必读:** `references/core_rules.md`, `references/log_symptom_routes.json`
- **按需:** `platforms/{platform}.md`, 症状匹配的 `prompts/{scene}.txt`
- **工具:** `python tools/log_triage.py`, `python tools/context_router.py`
- **禁止:** 无额外默认禁读目录。
---
## 共享规则（所有域）
- 缺少平台信息时先询问；ESP32/STM32/JL/BK 是平台，FreeRTOS/Zephyr 是 RTOS。
- 先选定工作流再行动；只加载所在域“加载规则”中列出的文件。
- 提交请求：遵循 `references/git_commit_style.md`，使用 `type(scope):` 格式。
- LVGL UI 生成必须在目标工程中实现和验证；不要假设仓库提供了生成器或模拟器。
## 约束分片索引
只加载你选定工作流引用的分片：
| 约束分片 | 覆盖约束 |
|-------|-------------|
| constraint_review.md | C1-C6, C11-C16 |
| constraint_memory.md | C7, C28, C36 |
| constraint_rtos.md | C8, C15, C17, C29-C35, C43-C44 |
| constraint_platform.md | C18-C21, C23, C42, C45-C46 |
| constraint_media.md | C25-C27 |
| constraint_voice.md | C10 |
| constraint_ota.md | C9, C22, C24 |
| constraint_recover.md | C37-C41 |
| constraint_bluetooth_protocol.md | C46 |
