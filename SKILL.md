---
name: freertos-embedded-architect
description: >-
  FreeRTOS/IoT 固件架构、实现、审查与故障诊断，覆盖嵌入式 C、LVGL UI、板级启动、
  OTA、SDK 裁剪、内存与任务拓扑、DMA/ISR、音视频、网络、外设和多平台适配
  （ESP32、STM32、JL、BK、Zephyr）。Use when reviewing or changing firmware,
  diagnosing crashes or resource issues, designing RTOS modules, bringing up boards,
  generating LVGL pages, or validating embedded safety and performance.
---

# FreeRTOS 嵌入式架构师

## 工作方式

1. 从当前请求、源码、构建文件和日志推断目标平台、RTOS、SDK 及主要交付物。
2. 为当前阶段选择一个主工作流并完整读取；组合请求按交付物依赖顺序分阶段执行。
3. 只读取工作流直接要求的 reference、platform、prompt、example 和 tool；不要批量加载目录。
4. 以目标工程及其 SDK 文档为事实源。无法确认平台 API、版本或硬件能力时，不要猜测。
5. 仅当缺失信息会实质改变方案或阻止验证时，提出一个聚焦的澄清问题。

## 工作流路由

按语义和交付物路由，不依赖单个关键词。故障诊断优先于一般审查；崩溃相关的内存问题先诊断，
无崩溃症状的容量、泄漏或碎片问题走内存分析。

| 用户意图 | 主工作流 |
|---|---|
| HardFault、WDT、死机、死锁、异常重启、日志定位 | [debug_crash.md](workflows/debug_crash.md) |
| 整个工程或工作区审查 | [l2_project_review.md](workflows/l2_project_review.md) |
| 堆、栈、泄漏、碎片、内存池或容量分析 | [l2_memory_analysis.md](workflows/l2_memory_analysis.md) |
| GPIO、pin mux、板卡资源或软硬件协同问题 | [hw_sw_cocodebug.md](workflows/hw_sw_cocodebug.md) |
| 文件、模块或固件代码审查 | [l2_code_review.md](workflows/l2_code_review.md) |
| 明确要求无工具的轻量人工审查 | [l2_code_review_lite.md](workflows/l2_code_review_lite.md) |
| LVGL 页面、多页 manifest、Router/Presenter/Model 脚手架 | [l3_lvgl_page.md](workflows/l3_lvgl_page.md) |
| 明确要求快速原型或最小页面 | [l3_lvgl_page_quick.md](workflows/l3_lvgl_page_quick.md) |
| 新模块、任务拓扑、状态机或模块契约 | [l3_new_module.md](workflows/l3_new_module.md) |
| 新板上电、启动链、外设初始化或最小系统 | [l3_bring_up.md](workflows/l3_bring_up.md) |
| SDK、驱动或组件裁剪 | [l3_sdk_trim.md](workflows/l3_sdk_trim.md) |

若请求包含“审查并修复”，先用相应审查工作流形成证据，再在同一任务内实施和验证修复。
若请求同时包含多个独立交付物，先处理风险最高或其他交付物所依赖的阶段，再重新路由下一阶段。

## 渐进式加载

- 始终先读所选 workflow；workflow 中的“必读”和步骤定义优先。
- 对项目型请求，优先运行 `python tools/project_doctor.py <project> --intent "<task>" --budget compact --json`，
  复用检测到的平台、RTOS、构建入口、约束 ID 和最小加载计划。
- 按 workflow 选择 [约束快速索引](references/constraint_quick_index.md) 中相关分片；只有需要完整映射时才读
  [constraint_index.md](references/constraint_index.md)，需要细则、正例或 checker 时再读对应细节。
- 能从工程或日志识别平台时直接识别；需要平台事实时只读一个 `platforms/{platform}.md`。
- 按 [prompt_index.md](references/prompt_index.md) 或 workflow 的症状表选择 1–3 个 prompt。
- 仅在验证对应风险时读取 example 或运行 checker。审查入口优先使用
  `python tools/run_review.py --dir <source> --platform <platform>`；崩溃日志优先使用
  `python tools/log_triage.py <log>`。
- 维护本 skill 或无法确定资源职责时才读 [skill_structure.md](references/skill_structure.md)。
- 普通任务不要读取 `archive/`、迭代日志、变更日志或整目录内容。

## 执行边界

- 用户要求审查、解释或诊断时，先保持只读并给出证据；只有明确要求修改或交付实现时才改代码。
- 用户要求实现、修复或生成时，完成最小闭环：修改、构建或静态验证、检查结果并报告残余风险。
- 不把 checker 告警当作事实；回到源码、调用上下文、配置和平台语义确认真伪。
- 不虚构编译、硬件实测或日志结果。无法运行的验证明确标记为未验证，并给出可执行命令。
- 提交代码时遵循 [git_commit_style.md](references/git_commit_style.md)。

## 交付格式

- **审查：** 先给结论，再按严重度列出 `file:line`、约束 ID、影响、证据和最小修复建议。
- **诊断：** 区分已证实事实与假设，给出根因排序、最小验证探针和下一步行动。
- **实现：** 列出改动文件、关键设计、已运行的验证及未覆盖风险。
