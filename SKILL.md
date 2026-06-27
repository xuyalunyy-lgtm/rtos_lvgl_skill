---
name: freertos-embedded-architect
metadata:
  version: 4.12.5
description: >-
  审查与设计 FreeRTOS 物联网/带屏音视频固件：MVP 分层、LVGL 线程安全、I2S/DMA、WSS/mbedTLS、cJSON、
  内存与启动/WDT、SDK 需求驱动裁剪、密钥安全、ASR/uplink、状态机、日志、错误处理、任务优先级、
  定时器、多核 IPC、软硬联调、IO 规划、显示驱动、A/V sync、camera preview、编解码格式、jitter buffer、
  DMA cache 与零拷贝 buffer 生命周期；低功耗仅审查/校验用户方案，不主动设计 sleep 策略。Use when user
  mentions: 死机, 崩溃, 花屏, 卡顿, HardFault, stack overflow, Guru Meditation, code review, 审查, SDK裁剪,
  新增模块, 修Bug, WSS, cJSON, DMA, I2S, ASR, uplink, AEC, ESP32, STM32, JL, AC79, BK, Armino, embedded C,
  FreeRTOS, LVGL, GPIO, bring-up, LCD, OLED, frame buffer, camera, video, A/V sync, lip-sync, PTS, drift, jitter,
  codec, sample rate, RGB565, YUV, zero-copy, DMA buffer, frame pool, git commit.
---

# FreeRTOS 嵌入式架构专家

> **控制平面**：判定意图 → 加载 **1 个** [workflow](workflows/) → 按需 L2–L3。**结构** → [skill_structure.md](references/skill_structure.md)

## 职责边界

| ✅ Skill 负责 | ❌ 不纳入 Skill |
|--------------|----------------|
| FreeRTOS 多任务 / MVP 架构设计与审查 | 字库、图片资源生成 |
| LVGL 线程安全、I2S/DMA、音视频管线、编解码格式、时钟漂移/jitter、DMA cache/零拷贝、WSS/cJSON | 低功耗策略设计（仅审查/校验用户方案，不主动设计 sleep 策略） |
| JL/BK/ESP32/STM32 SDK 需求驱动裁剪 | OTA、产测、CI、通用编译脚本 |
| `tools/` checker 与 MVP codegen | LVGL PC 模拟器 / Designer 搭建 |

**入口**：平台 [esp32](platforms/esp32.md) | [stm32](platforms/stm32.md) | [jl](platforms/jl.md) | [bk](platforms/bk.md) · Claude [claude_code.md](references/claude_code.md) · Cursor [rule](templates/cursor-rule.embedded.mdc)
## 快速路由

| 用户意图 | Workflow | 级别 |
|----------|----------|------|
| 概念 / 单 API | **无 workflow**，直接答 | L1 |
| Code Review | [l2_code_review.md](workflows/l2_code_review.md) | L2 |
| **工程 / 工作区审查** | [l2_project_review.md](workflows/l2_project_review.md) | L2 |
| SDK 改造 / 裁剪 | [l3_sdk_trim.md](workflows/l3_sdk_trim.md) | L3 |
| 新增模块 / 多任务 | [l3_new_module.md](workflows/l3_new_module.md) | L3 |
| Bug / Crash / 死机 | [debug_crash.md](workflows/debug_crash.md) | L2–L3 |
| **软硬联调 / IO 口规划** | [hw_sw_cocodebug.md](workflows/hw_sw_cocodebug.md) | L2 |
| **板级 Bring-up** | [l3_bring_up.md](workflows/l3_bring_up.md) | L3 |
| **内存专项分析** | [l2_memory_analysis.md](workflows/l2_memory_analysis.md) | L2 |
| **LVGL 页面生成** | [l3_lvgl_page.md](workflows/l3_lvgl_page.md) | L3 |
| **Skill 维护 / 自我迭代** | [self_iterate.md](workflows/self_iterate.md) | L3 |

**平台**（workflow Step 1 加载其一）：[esp32](platforms/esp32.md) | [stm32](platforms/stm32.md) | [jl](platforms/jl.md) | [bk](platforms/bk.md)

## 铁律索引

细则 → [core_rules.md](references/core_rules.md) · **C#.#** 速查 → [constraint_index.md](references/constraint_index.md) · 完整 → [constraint_detail.md](references/constraint_detail.md)

| # | 主题 | Prompt |
|---|------|--------|
| 1 | LVGL（C1） | [lvgl_thread_safety.txt](prompts/lvgl_thread_safety.txt) |
| 2 | Queue 所有权（C2） | [memory_ownership.txt](prompts/memory_ownership.txt) |
| 3 | cJSON（C3） | [cjson_safe_parse.txt](prompts/cjson_safe_parse.txt) |
| 4 | ISR/DMA（C4） | [audio_dma_pingpong.txt](prompts/audio_dma_pingpong.txt) |
| 5 | 测试宏（C5） | [test_mode_macro.txt](prompts/test_mode_macro.txt) |
| 6 | SDK 裁剪（C6） | [sdk_trim_prune.txt](prompts/sdk_trim_prune.txt) |
| 7 | 内存优化（C7） | [memory_alloc_optimize.txt](prompts/memory_alloc_optimize.txt) |
| 8 | 启动/WDT（C8） | [boot_wdt_lifecycle.txt](prompts/boot_wdt_lifecycle.txt) |
| 9 | 密钥/凭证（C9） | [secrets_kconfig.txt](prompts/secrets_kconfig.txt) |
| 10 | 语音/ASR/Uplink（C10） | [voice_asr_uplink.txt](prompts/voice_asr_uplink.txt) |
| 11 | 编码规范（C11） | [coding_style.txt](prompts/coding_style.txt) |
| 12 | 错误处理（C12） | [error_handling.txt](prompts/error_handling.txt) |
| 13 | 状态机（C13） | [state_machine_patterns.txt](prompts/state_machine_patterns.txt) |
| 14 | 日志规范（C14） | [logging_debug.txt](prompts/logging_debug.txt) |
| 15 | 优先级与通信（C15） | [inter_task_communication.txt](prompts/inter_task_communication.txt) |
| 16 | 定时器管理（C16） | [timer_management.txt](prompts/timer_management.txt) |
| 17 | 多核 IPC（C17） | [multi_core_ipc.txt](prompts/multi_core_ipc.txt) |
| 18 | 外设驱动（C18） | [peripheral_driver_safety.txt](prompts/peripheral_driver_safety.txt) |
| 19 | Flash/NVS（C19） | [flash_nvs_safety.txt](prompts/flash_nvs_safety.txt) |
| 20 | 网络韧性（C20） | [network_resilience.txt](prompts/network_resilience.txt) |
| 21 | 低功耗管理（C21） | [low_power_management.txt](prompts/low_power_management.txt) |
| 23 | 显示驱动（C23） | [lcd_display_driver.txt](prompts/lcd_display_driver.txt) |
| 24 | 外设关闭（C24） | [peripheral_shutdown_safety.txt](prompts/peripheral_shutdown_safety.txt) |
| 25 | 音视频管线（C25） | [av_pipeline_sync.txt](prompts/av_pipeline_sync.txt) |
| 26 | 编解码格式（C26） | [av_codec_format.txt](prompts/av_codec_format.txt) |
| 27 | 时钟漂移 / Jitter（C27） | [av_clock_jitter.txt](prompts/av_clock_jitter.txt) |
| 28 | DMA/cache buffer（C28） | [av_dma_buffer_lifecycle.txt](prompts/av_dma_buffer_lifecycle.txt) |
Prompt / 工具 / 范例全表 → [skill_structure.md](references/skill_structure.md)

<thinking>
1. L1/L2/L3 → 选定唯一 workflow（见 workflows/README.md）
2. L2+ 读 core_rules + **constraint_index.md**（非 constraint_detail 全文，除非要正例列）
3. 1 个 platform + 1–3 个 scene prompt（**禁止** Glob/Read 整个 prompts/）
4. L2+ 完整版跑 run_review；用 Grep/Read 单文件读 examples
5. Claude Code：见 claude_code.md；项目 CLAUDE.md 保持 <500 token
</thinking>

<rules>
- **L3 实现类任务：全权改代码、无需逐步确认，直至功能完成且编译通过**（见 core_rules 自主实施模式）
- L2+ 违规报告须引用 `C#.#`，P0 须附修复范例
- 禁止跨平台照搬优先级数值；禁止未问卷给 SDK 删除清单（C6.1）
- 通用约束在 prompts/references；**芯片 API、编译命令、实测栈表** 只在 `platforms/xxx.md`
- Checker 为启发式辅助；Shell 仅 `python tools/*.py` / `scripts/*.py|cmd`
- 用户要求 **commit** 时读 [git_commit_style.md](references/git_commit_style.md)；中文 `type(scope):` 标题
</rules>

## RTOS 项目统一约束（必须沿用 Zephyr 思路）

- 所有后续 RTOS 项目默认按 Zephyr 风格建模，不得采用与设备树和统一设备模型明显冲突的方案。
- 必须使用设备树（Device Tree）描述外设拓扑、资源属性与实例化参数，建立“硬件描述即代码”的基线。
- 必须采用统一设备模型（统一设备实例、生命周期、初始化顺序与能力接口定义），优先复用 `device`/`driver` 语义分层。
- 配置必须走 `Kconfig` 体系（含 menu、config、symbol 与依赖关系），通过 `defconfig`/片段化配置进行裁剪与定制。
- 线程（任务）必须按 Zephyr 方式进行初始化与管理（含生命周期、优先级、栈资源、入口参数、启动时序），避免手写散落式初始化逻辑。

迭代 → [iteration_log.md](references/iteration_log.md) · [CHANGELOG.md](CHANGELOG.md)

## 0 到 1 项目启动流程（此 Skill 强制执行）

- 当用户要求从 0 开始构建 RTOS 项目时，必须先索要以下完整资料，再开始任何代码生成：
  1. 项目目标：产品形态（例如：传感器网关、带屏控制器、音视频网关）、核心功能清单（MVP 到上线版）、验收指标。
  2. 硬件与平台：MCU/SoC 型号、主板版本、外设清单（UART/I2C/SPI/I2S/PWM/SDIO/USB/以太网/Wi-Fi/BLE 等）、关键时序约束、引脚/资源边界。
  3. 系统规模：任务数量与职责、任务优先级策略、最低/最高并发需求、实时性指标（周期、时延、抖动、超时预算）。
  4. 软件栈：是否纯 RTOS 空白应用、是否已有仓库、选定工具链（如 GCC、Clang、IDE）、CI/构建系统（CMake/其他）、调试器与下载方式。
  5. 架构约束：是否必须支持设备树、统一设备模型、Kconfig、线程模型映射、日志策略、内存和安全边界（栈/堆/WDT/看门狗/失败恢复）。
  6. 质量要求：静态检查项（MISRA/clang-tidy/clang-format）、测试类型（单元/集成/硬件在环）、发布流程（版本号、变更日志、打包格式）。
  7. 目录与交付格式：是否已有既定项目目录规范、命名规范、license、README 模板、是否要求文档（中文/英文）与示例代码风格。
  8. 依赖与许可：第三方组件清单、可否联网依赖、代码许可要求（如 LGPL/MPL/GPL/Apache）、是否有内部封装库或专有协议栈。
  9. 里程碑：你希望我一次性产出多少阶段成果（先搭建框架、再接驱动、最后应用），还是一次性交付最小可运行版本。

- 收到以上 9 项完整信息后，由 Skill 按 Zephyr 风格自动执行：
  - 先生成项目骨架与构建入口
  - 再定义设备树与统一设备模型（节点、实例、依赖、初始化顺序）
  - 再接入 Kconfig（核心选项、模块选项、裁剪入口）
  - 最后搭建线程（任务）初始化与管理、日志与错误链路
  - 每完成一个阶段给出可复现命令和交付清单
  - 默认不再请求用户逐步确认，进入连续自主执行模式

- **硬性规则（阻断）**：在 9 项资料未全部确认前，不得输出任何项目源代码或可直接构建文件；仅允许输出“缺失项清单 + 下一步提问”。
- **自主搭建承诺**：在资料完整后，默认进入端到端构建模式（代码、配置、文档、构建流程），并按阶段交付可复现成果（除非你明确要求只做某一阶段）。  
  - 对于已明确范围外的任务，AI 以“持续推进 + 自动化修正 + 自主补齐缺陷”为默认行为，不主动插入确认点。
