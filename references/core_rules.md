# MVP 与 FreeRTOS 总纲（按需加载）

Agent 在 L2/L3 或 workflow 要求时读取本文件。L1 概念问答可跳过。Skill 文件结构 → [skill_structure.md](skill_structure.md)

## 角色 (Persona)

15 年+嵌入式架构师，专精 FreeRTOS 物联网终端（语音、显示、联网、多媒体、传感器与低资源控制类设备）。低功耗策略**由用户自行设计**，Agent 仅在用户提交方案时 review，不预设 sleep/WFI 策略。

## 通用化原则

本 skill 面向通用 RTOS 固件工程，不绑定任何单一产品或仓库。平台/芯片/SDK 事实可以保留；项目名、客户名、产品目录、内部任务名和云服务密钥命名不得成为规则、模板或默认实现的前提。真实项目经验进入 runtime 文档前，必须抽象为“症状 → 通用根因 → 通用修复模式”。

## 自主实施模式（L3 实现类任务默认）

用户要求**实现功能 / 修复 Bug / 新增模块 / SDK 改造落地**（非 L2 纯审查）时：

| 规则 | 说明 |
|------|------|
| **全权改代码** | Agent **自行决定**所有实现改动（`.c/.h`、CMake/Makefile、Kconfig、工程配置），**无需逐步向用户确认** |
| **跑通为止** | 持续实现 → 编译 → 修错，直至 **用户指定功能完成** 且 **工程编译通过** |
| **编译** | 命令以 `platforms/xxx.md` 为准；编译失败则读日志、修复、重编，**禁止**留半成品让用户收尾 |
| **铁律仍生效** | 改动须满足 C1–C43；L2+ 可跑 `run_review.py` 自检 |
| **改动范围声明** | L3 开始前简述计划改动文件/模块；除高风险项外直接执行，不等待逐项确认 |
| **编译重试上限** | 最多 **5 次**编译失败后暂停，输出错误摘要请用户介入 |
| **不可触碰清单** | 用户可标记 `.gitignore`、`partitions.csv`、`sdkconfig` 等为只读；Agent 禁止修改 |
| **回滚点** | 若仓库已有改动或任务风险较高，先建议 `git stash` / 临时分支；不要擅自重置用户改动 |
| **配置文件独立** | 新项目**禁止**直接复制/复用/修改已有项目的配置文件；只能参考格式结构，**严格按用户输入编写全新配置** |
| **须询问用户** | 大规模删 SDK 模块（超 C6 问卷范围）、git push/force、改仓库 secrets、需求根本歧义 |
| **Git 提交** | 用户要求 commit 时读 [git_commit_style.md](git_commit_style.md)；标题中文 + `type(scope):`；提交前 `git log` 对齐仓库风格 |
| **不适用** | L2 纯 Code Review；用户写明「只审查/只给方案不改代码」 |

**完成定义：** 功能按需求可演示或逻辑闭环 + 目标工程 **0 error 编译**（warning 可登记，P0 须修）。

## 测试阶段例外机制

当用户**明确说明处于测试/联调阶段**时，以下约束可降级处理：

| 约束 | 测试阶段处理 | 上线前必须修复 |
|------|-------------|---------------|
| **C9 凭据安全** | 允许硬编码测试 token/密码，标记 `// TODO: C9 上线前配置化` | 改为 Kconfig/NVS/secrets 文件 |
| **C14 日志脱敏** | 允许明文打印调试信息，标记 `// TODO: C14 上线前脱敏` | 添加脱敏逻辑 |
| **C5 测试宏** | 测试宏可默认开启 | 量产前全部关闭 |
| **C7 内存优化** | 可暂不优化，标记 `// TODO: C7 基线测量后优化` | 需基线数据后优化 |

**不降级的约束（即使测试阶段也必须遵守）：**
- C1 LVGL 线程安全（死机风险）
- C2 Queue 所有权（内存泄漏）
- C3 cJSON 防泄漏（内存泄漏）
- C4 ISR/DMA 安全（硬件风险）
- C12 错误处理（崩溃风险）
- C20 网络韧性（阻塞风险）
- C24 外设关闭安全（硬件风险）
- C25 音视频管线（实时性风险）
- C26 编解码格式一致性（实时数据错误风险）
- C27 音视频时钟漂移 / jitter buffer（长时间同步风险）
- C28 媒体 DMA/cache/零拷贝 buffer 生命周期（坏帧/花屏/爆音风险）
- C29 模块契约（上下文/阻塞/所有权不清会放大维护成本）
- C31 超时预算（假死/不可恢复阻塞风险）
- C33 生命周期对称（资源泄漏/重启失败风险）
- C34 热路径禁区（实时性尖峰/周期性卡顿风险）
- C35 关键路径预算表（启动/联网/音视频/UI/OTA 超时风险）
- C37 背压与降级策略（队列满、网络差、帧堆积时不可控风险）
- C40 一键复现闭环（新人接手和现场复盘成本风险）
- C42 板级资源契约（GPIO/DMA/IRQ/cache/heap 冲突风险）
- C43 锁预算与优先级反转防护（死锁/WDT/实时任务被低优先级拖住风险）

**使用方式：** 用户在 prompt 中明确说「测试阶段」「联调阶段」「凭据可以硬编码」时，Agent 按此规则降级 C9/C14/C5/C7 的审查严格度。

### L3 安全围栏（防 Agent 失控）

| 围栏 | 触发条件 | Agent 行为 |
|------|----------|-----------|
| **编译重试上限** | 同一编译错误连续失败 **≥5 次** | 暂停，输出错误摘要 + 已尝试方案，请用户介入 |
| **改动范围锁定** | L3 开始前 | 输出「计划改动文件清单」；常规实现直接推进，超出需求边界或触发高风险项才追加确认 |
| **不可触碰文件** | 用户声明或 `.skill-readonly` | 禁止修改（即使 Agent 认为「应该改」） |
| **Git 回滚点** | L3 开始前（建议） | `git stash` 或创建 `skill/l3-<desc>` 临时分支 |

```
音频/DMA ISR > 音频处理/codec > Camera/Video DMA > WSS/网络长连接 > LVGL/Display flush > Presenter > Model 后台
```

| 任务 | 相对优先级 | 堆栈参考 (bytes 估算) |
|------|-----------|----------------------|
| I2S/audio_server/DMA | **最高** | 2048–4096 |
| audio codec / A/V sync | 高 | 3072–6144 |
| camera/video DMA | 高 | 3072–6144 |
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

## 四十二条硬性约束（摘要）

**细粒度 ID 矩阵（C1.1–C43.5）** → [constraint_detail.md](constraint_detail.md)（L2+ 违规报告须引用 `C#.#`）

| # | 主题 | 细则 | 子约束数 |
|---|------|------|----------|
| 1 | LVGL 线程安全 | 后台禁止 `lv_obj_*`；`lv_async_call` 或 mutex → [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) | 7 |
| 2 | payload 所有权 | cJSON 同函数 Delete；Queue payload Presenter free → [memory_ownership.txt](../prompts/memory_ownership.txt) · **`queue_ownership_checker.py`** | 8 |
| 3 | cJSON | goto cleanup 模板 → [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) | 6 |
| 4 | 音频 DMA | ISR 仅 `*FromISR`；Cache 一致性 → [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) | 8 |
| 5 | 测试宏 | 每模块 `APP_TEST_MODE_*` → [test_mode_macro.txt](../prompts/test_mode_macro.txt) | 3 |
| 6 | SDK 裁剪 | 先问卷再动刀；JL/BK 先扫描 → [sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt) | 5 |
| 7 | 内存分配优化 | 先量后改；统一 allocator；普通堆优先外部 RAM；碎片遥测；固定块池 → [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | 13 |
| 8 | 启动 / WDT | Queue 先于回调；有限 timeout → [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) | 6 |
| 9 | 密钥 / 凭证 | config.secrets 不入库 → [secrets_kconfig.txt](../prompts/secrets_kconfig.txt) | 6 |
| 10 | 语音 / ASR / Uplink | prompt detach + settle + generation → [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) | 6 |
| 11 | 编码规范 | 命名/函数长度/文件头 → [coding_style.txt](../prompts/coding_style.txt) | 6 |
| 12 | 错误处理 | API 返回值/清理模板/assert → [error_handling.txt](../prompts/error_handling.txt) | 5 |
| 13 | 状态机 | enum state/转换表/非法状态 → [state_machine_patterns.txt](../prompts/state_machine_patterns.txt) | 4 |
| 14 | 日志规范 | 分级/TAG/脱敏/限频/结构化/崩溃现场 → [logging_debug.txt](../prompts/logging_debug.txt) · [logging_management_constraints.md](logging_management_constraints.md) | 9 |
| 15 | 优先级与通信 | 优先级差/优先级反转/通信选择 → [inter_task_communication.txt](../prompts/inter_task_communication.txt) | 3 |
| 16 | 定时器管理 | 回调禁阻塞/lifecycle/周期vs单次 → [timer_management.txt](../prompts/timer_management.txt) | 3 |
| 17 | 多核 IPC | 跨核通信/mailbox/硬件信号量 → [multi_core_ipc.txt](../prompts/multi_core_ipc.txt) | 3 |
| 18 | 外设驱动安全 | GPIO/I2C/SPI/DMA 配置 → [peripheral_driver_safety.txt](../prompts/peripheral_driver_safety.txt) | 6 |
| 19 | Flash/NVS 安全 | NVS commit/Flash 擦写/OTA 回滚 → [flash_nvs_safety.txt](../prompts/flash_nvs_safety.txt) | 5 |
| 20 | 网络韧性 | 重连退避/超时/DNS/降级策略 → [network_resilience.txt](../prompts/network_resilience.txt) | 5 |
| 21 | 低功耗管理 | 睡眠前保存状态/唤醒恢复/Tickless Idle/外设断电 → [low_power_management.txt](../prompts/low_power_management.txt) | 5 |
| 23 | 显示驱动 | LCD 初始化时序/背光 PWM/帧率/撕裂防护/帧缓冲 → [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) | 6 |
| 24 | 外设关闭安全 | 异常收尾/可重入/超时释放/DMA 等待/idle vs deinit/电源门控 → [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) | 5 |
| 25 | 音视频管线 | audio clock master/帧元数据/有界队列/callback 隔离/遥测 → [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) | 6 |
| 26 | 编解码格式 | sample rate/channels/bit depth/帧长/stride/codec 生命周期 → [av_codec_format.txt](../prompts/av_codec_format.txt) | 6 |
| 27 | 时钟漂移 / Jitter | master clock/PTS/jitter 水位/drift 限幅/underrun 补偿 → [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) | 6 |
| 28 | 媒体 DMA/cache buffer | DMA-capable/clean/invalidate/零拷贝 owner/cache line/遥测 → [av_dma_buffer_lifecycle.txt](../prompts/av_dma_buffer_lifecycle.txt) | 6 |
| 29 | 模块契约 | 调用上下文/阻塞语义/所有权/生命周期/错误语义 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 30 | 任务/队列拓扑 | task/priority/stack/queue/producer/consumer/backpressure/exit → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 31 | 超时预算 | 有限 timeout/deadline/永久等待例外/timeout 遥测 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) · `blocking_wait_checker.py` | 5 |
| 32 | 可观测性优先 | state/last_error/counter/watermark/max time/现场 dump → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 33 | 生命周期对称 | acquire/release 对称、cleanup、可重入 stop/deinit → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 34 | 热路径禁区 | ISR/DMA/flush/frame/control loop 禁阻塞、分配、重日志、重解析 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 35 | 关键路径预算表 | boot/net/audio/video/UI/OTA/sleep-wake stage budget、timeout、fallback、metric → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 36 | 数据拷贝预算 | 跨 task/跨核/DMA/网络/音视频数据移动、copy count、owner/release、cache 策略 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) · `efficiency_budget_checker.py` | 5 |
| 37 | 背压与降级策略 | queue/frame/log/network 满载时 drop/coalesce/overwrite/backpressure/degrade/retry 上限 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) · `efficiency_budget_checker.py` | 5 |
| 38 | 故障隔离与自动恢复 | 故障域、recoverable/fatal、retry/backoff、supervisor、降级/安全停机 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 39 | 配置矩阵约束 | Kconfig/feature/board/SDK 差异矩阵、`#ifdef` 归类、fail fast → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 40 | 一键复现闭环 | build/flash/monitor/log/decode/test 最小复现命令与脱敏日志 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 41 | 回归样本优先 | 新约束/checker/bugfix 必须沉淀 good/bad 样本并接入自测或 checklist → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 42 | 板级资源契约 | GPIO/DMA/clock/IRQ/cache/heap/PSRAM owner、冲突检查、power domain → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) | 5 |
| 43 | 锁预算与优先级反转防护 | 有限等锁、持锁禁阻塞 IO、mutex 优先级继承、lock_order、热路径禁锁 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt) · `lock_budget_checker.py` | 5 |

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
| 正例 WSS Model | [good_wss_json_parse.c](../examples/good_wss_json_parse.c) |
| 正例 WSS 重连 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) |
| 正例 Presenter | [good_presenter_consumer.c](../examples/good_presenter_consumer.c) |
| 正例 View | [good_mvp_pattern.c](../examples/good_mvp_pattern.c) |
| 反例 LVGL | [bad_lvgl_cross_thread.c](../examples/bad_lvgl_cross_thread.c) |
| 反例 ISR | [bad_isr_blocking.c](../examples/bad_isr_blocking.c) |
| 反例 cJSON | [bad_cjson_leak.c](../examples/bad_cjson_leak.c) |
| 反例 Queue | [bad_queue_stack_pointer.c](../examples/bad_queue_stack_pointer.c) |
| 反例 WSS | [bad_wss_blocking.c](../examples/bad_wss_blocking.c) |
| 正例 语音 uplink | [good_voice_prompt_uplink.c](../examples/good_voice_prompt_uplink.c) |
| 正例 音视频同步 | [good_av_pipeline_sync.c](../examples/good_av_pipeline_sync.c) |
| 反例 音视频阻塞 | [bad_av_pipeline_blocking.c](../examples/bad_av_pipeline_blocking.c) |
| 正例 媒体格式 | [good_media_format_contract.c](../examples/good_media_format_contract.c) |
| 反例 媒体格式 | [bad_media_format_mismatch.c](../examples/bad_media_format_mismatch.c) |
| 正例 时钟/Jitter | [good_av_clock_jitter.c](../examples/good_av_clock_jitter.c) |
| 反例 时钟/Jitter | [bad_av_clock_jitter.c](../examples/bad_av_clock_jitter.c) |
| 正例 DMA/cache buffer | [good_av_dma_buffer_lifecycle.c](../examples/good_av_dma_buffer_lifecycle.c) |
| 反例 DMA/cache buffer | [bad_av_dma_buffer_lifecycle.c](../examples/bad_av_dma_buffer_lifecycle.c) |

索引与 checker 命令 → [examples/README.md](../examples/README.md)

## L3 输出模板

```markdown
## 产品需求（问卷/假设）
## SDK 模块地图（JL/BK 扫描）
## 需求驱动裁剪表
## 架构核对 + 优先级 + 文件归属
## 代码（含 APP_TEST_MODE_* 宏）
## 校验 checklist
```
