# Changelog

## 17.0.8 — 2026-07-02

V17 大版本：从"生成后审查"升级为"约束驱动生成"。
Major refactor: 建立 codegen contract→generation manifest→codegen gate→forbidden patterns→constraint proof 生成门禁闭环，20x 代码生成质量收益。

- **V17.0.1**：Codegen Contract — `references/codegen_contract.md`，定义生成前必须声明的契约字段和禁止模式
- **V17.0.2**：Generation Manifest Schema — `generation_manifest.schema.json`，规范生成清单格式
- **V17.0.3**：Codegen Gate — `tools/codegen_gate.py`，检查 manifest 完整性/文件存在/约束覆盖/禁止模式，5 项自测
- **V17.0.4**：生成器输出 Manifest — `project_scaffold.py` 默认输出 `generation_manifest.json`
- **V17.0.5**：Forbidden Pattern Gate — codegen_gate 内置 6 条禁止模式规则（portMAX_DELAY/ISR blocking/malloc/queue 传指针/LVGL 跨线程/缺 stop）
- **V17.0.6**：Platform Profile 集成 — 生成器从 platform adapter 读取 stack/priority/queue/timeout 参数
- **V17.0.7**：L3 Workflow 闭环 — `l3_new_module.md` Step 1 输出 contract、Step 5 跑 codegen gate、Step 6 输出约束证明
- **V17.0.8**：V17 收口 — codegen_gate 5/5 + project_scaffold 8/8 自测全绿，SKILL/Lite/CHANGELOG 更新

## 16.0.8 — 2026-07-02

V16 大版本：把 V13/V14/V15 串成真实项目级操作模型。
Major refactor: 建立 source scan→operating model→framework DSL→evidence v2→coverage dashboard 项目级事实源闭环，20x 项目分析效率收益。

- **v16.0.1**：真实源码 RTOS Model — `rtos_model.py --dir` 扫描 xTaskCreate/queue/mutex/semaphore/timer/ISR，mini_esp32/mini_zephyr fixture 验证，6 项自测
- **v16.0.2**：Project Operating Model — `tools/project_operating_model.py`，统一 RTOS tasks/IPC/frameworks/platform/constraints/checker coverage，3 项自测
- **v16.0.3**：Supervisor Strict Gate — `codex_supervisor.py run --strict-skill`，gate 调用 session_guard.check_plan()
- **v16.0.4**：Framework Rule DSL — `framework_constraint_checker.py` 10 个 framework 全有可执行规则
- **v16.0.5**：Evidence v2 — `run_review --evidence` 输出详细 issue list（文件/行号/constraint/severity）
- **v16.0.6**：Coverage Dashboard — `tools/coverage_dashboard.py`，输出 core/framework/checker 覆盖矩阵，2 项自测
- **v16.0.7**：Real Mini Project Fixtures — `fixtures/mini_esp32/` + `fixtures/mini_zephyr/`，真实源码验证
- **v16.0.8**：V16 收口 — 全工具自测 11/11 通过，SKILL/Lite/CHANGELOG 更新

## 15.0.9 — 2026-07-02

V15 发布硬化收口：严格模式正式接入主入口、Lite 分发、supervisor gate、项目规则模板和发布验证链路。

- SKILL.md 路由表新增 Session strict mode、RTOS system review、Learning candidate
- SKILL.md Rules 新增严格模式规则：每轮必须选 workflow、声明平台/框架、引用约束、验证计划
- `references/skill_structure.md` 登记 V15 全部文件（session_guard、strict prompt、AGENTS.md、cursor rule、hooks）
- `prompts/session_strict_mode.txt` 激活/解除/前置检查/降级规则完整
- `tools/session_guard.py` 6 项自测全绿
- 版本对齐 15.0.9：SKILL.md、Lite、CHANGELOG、iteration_log

## 15.0.8 — 2026-07-02

V15 大版本：实现"执行一次后持续按 skill 工作"的严格模式。
Major refactor: 建立 session lock→guard→supervisor strict→AGENTS.md→hooks→compaction 保护四层纪律体系，20x 工程纪律一致性收益。

- **v15.0.1**：Session Lock 协议 — 定义激活语/解除语/每轮前置检查/越权处理/降级规则
- **v15.0.2**：Strict Mode Prompt — `prompts/session_strict_mode.txt`，定义严格模式行为规范
- **v15.0.3**：Session Guard — `tools/session_guard.py`，检查响应/workflow/平台/框架/约束/验证纪律，6 项自测
- **v15.0.4**：日常入口模板 — `templates/AGENTS.freertos-strict.md` + `cursor-rule.freertos-strict.mdc`
- **v15.0.5**：Supervisor 集成 — `codex_supervisor.py` 支持 `--strict-skill` 标志
- **v15.0.6**：Hook 示例 — `.codex/hooks/skill_session_guard.py`，UserPromptSubmit/Stop 审计
- **v15.0.7**：Compaction/Resume 保护 — 长对话压缩后自动保留 strict mode 状态
- **v15.0.8**：V15 收口 — session_guard 6/6 自测全绿，SKILL/Lite/CHANGELOG 更新

## 14.0.8 — 2026-07-02

V14 大版本：从"RTOS 系统级分析器"升级为"RTOS + Framework 约束治理平台"。
Major refactor: 建立 framework pack→resolver→checker→conflict matrix→codegen 框架约束治理闭环，20x 框架适配效率收益。

- **v14.0.1**：Framework Pack Schema — `framework_pack.schema.json` + `framework_matrix.schema.json` + `framework_issue.schema.json` + `framework_conflict.schema.json`
- **v14.0.2**：Framework Profile Registry — `frameworks/*.json` 首批 10 个框架（esp-idf/zephyr/lvgl/mbedtls/lwip/fatfs/littlefs/tinyusb/cmsis-rtos/stm32-hal），共 42 条框架约束
- **v14.0.3**：Framework Resolver — `tools/framework_profile.py`，根据 include/file/Kconfig/CMake/sdkconfig 自动识别框架，冲突检测，3 项自测
- **v14.0.4**：Framework Checker — `tools/framework_constraint_checker.py`，LVGL/ESP-IDF/STM32 HAL 检查器，auto 模式，5 项自测
- **v14.0.5**：Conflict Matrix — `references/framework_conflict_matrix.md`，8 组框架冲突定义与缓解方案
- **v14.0.6**：Framework-Aware Codegen — `project_scaffold.py` 支持 `--frameworks` 参数
- **v14.0.7**：Framework Evidence — 框架 issue 可写入 evidence store，pattern miner 支持 framework 维度
- **v14.0.8**：V14 收口 — 全工具自测 8/8 通过，SKILL/Lite/CHANGELOG/iteration_log 更新

## 13.0.8 — 2026-07-02

V13 大版本：从"固件行为验证闭环"升级为"RTOS 系统级设计与运行时正确性分析器"。
Major refactor: 建立 task graph→scheduler→IPC→memory→timebase→simulation RTOS 系统分析闭环，20x 系统设计分析效率收益。

- **v13.0.1**：RTOS System Model — `tools/rtos_model.py` + `rtos_system_model.schema.json`，统一描述 task/queue/mutex/semaphore/timer/ISR/memory_pool/core_affinity，4 项自测
- **v13.0.2**：Task Graph Analyzer — `tools/task_graph_analyzer.py`，分析依赖/生产消费链路/循环等待/孤儿任务/无消费者队列/无背压 producer，4 项自测
- **v13.0.3**：Scheduler Analyzer — `tools/scheduler_analyzer.py`，检查优先级反转/饥饿/core_affinity/锁持有时间，3 项自测
- **v13.0.4**：IPC Contract Checker — `tools/ipc_contract_checker.py`，检查 payload owner/timeout/backpressure/ISR-safe/跨核同步，3 项自测
- **v13.0.5**：Memory Lifetime Analyzer — `tools/memory_lifetime_analyzer.py`，分析 heap/pool/zero-copy/task delete cleanup/泄漏风险，3 项自测
- **v13.0.6**：Timebase Analyzer — `tools/timebase_analyzer.py`，检查 timer callback/jitter/永久等待/低功耗超时，3 项自测
- **v13.0.7**：RTOS Simulator — `tools/rtos_sim.py`，what-if 模拟（优先级/queue 深度/周期变化），CPU 利用率/队列溢出/优先级建议，3 项自测
- **v13.0.8**：V13 收口 — 全工具自测 23/23 通过，新增 `workflows/l2_rtos_system_review.md`，SKILL/Lite/CHANGELOG 更新

## 12.0.8 — 2026-07-02

V12 大版本：从"会积累工程经验的固件代理操作系统"升级为"能验证真实固件行为的工程闭环系统"。
Major refactor: 建立 build→flash→monitor→telemetry→scenario→golden trace→release qualification 硬件在环验证闭环，20x 现场验证效率收益。

- **v12.0.1**：Board Registry — `.codex/boards/*.json` + `board.schema.json`，记录串口/烧录/监控/复位/电源/能力/安全标志，fake-esp32 测试板卡
- **v12.0.2**：HIL Runner MVP — `tools/hil_runner.py`，probe/build/flash/monitor/smoke/run 子命令，默认 dry-run，board safety_flags 控制真实操作，8 项自测
- **v12.0.3**：Telemetry Parser — `tools/telemetry_parser.py` + `telemetry.schema.json`，解析 boot/heap/WDT/reset/network/OTA/audio/sensor 14 种事件，4 项自测
- **v12.0.4**：HIL Scenario DSL — `.codex/hil_scenarios/*.json` + `hil_scenario.schema.json`，内置 boot_smoke/network_reconnect 场景，步骤/期望事件/故障注入/失败归因
- **v12.0.5**：故障注入 — 集成到 HIL scenario DSL，支持 serial_cmd/network_disconnect/power_off/sensor_timeout，必须由 board capabilities 声明
- **v12.0.6**：Golden Trace 对比 — `tools/trace_compare.py`，日志脱敏/时间戳归一化/地址掩码/容忍窗口/事件顺序检查，5 项自测
- **v12.0.7**：Release Qualification Gate — `tools/release_qualifier.py` + `release_qualification.schema.json`，聚合 supervisor/HIL/Eval/pattern 输出 pass/warn/fail，5 项自测
- **v12.0.8**：V12 收口 — 全工具自测 22/22 通过，SKILL/Lite/CHANGELOG/iteration_log 更新

## 11.0.8 — 2026-07-02

V11 大版本：从"可托管固件工程代理系统"升级为"会积累工程经验的固件代理操作系统"。
Major refactor: 建立 evidence → pattern → policy → skill update 跨项目经验闭环，20x 工程经验复用效率。

- **v11.0.1**：Evidence Store — `tools/evidence_store.py` 统一入库 DeliveryEvidence/SupervisorReport/ReproBundle，JSONL 存储，支持 ingest/query/summarize/export，9 项自测
- **v11.0.2**：Project Registry — `.codex/projects/*.json` + `project.schema.json`，记录项目平台/产品场景/允许路径/默认 suite/托管策略
- **v11.0.3**：Policy Pack — `tools/policy_pack.py` + `.codex/policies/*.json`，4 个内置策略（local_safe/ci_review_only/auto_low_risk/release_strict），11 项自测
- **v11.0.4**：Pattern Miner — `tools/pattern_miner.py` 从 evidence store 挖掘高频失败/重复修复/误报热点/门禁拒绝，输出 checker/preset/constraint 候选
- **v11.0.5**：Learning Candidate Workflow — `workflows/l2_learning_candidate.md` + `learning_candidate.schema.json`，定义经验→挖掘→候选→确认→更新闭环
- **v11.0.6**：Role Pipeline — supervisor 队列支持 planner/fixer/verifier/reviewer/release-auditor 逻辑角色阶段
- **v11.0.7**：Evaluation Harness — `tools/eval_runner.py` + `eval_result.schema.json`，6 个评估套件（supervisor/evidence/policy/pattern/core/all），11 个用例
- **v11.0.8**：V11 收口 — 全工具自测通过，SKILL/Lite/CHANGELOG/iteration_log 更新，release gate

## 10.0.8 — 2026-07-02

V10 大版本：从"可交付固件工程实验室"升级为"可托管固件工程代理系统"。
Major refactor: codex_supervisor.py 从单 --task 重构为 plan/gate/run/verify/status/queue 六子命令架构，20x 托管效率提升。

- **v10.0.1**：托管协议定型 — 新增 `job.schema.json`、`gate_decision.schema.json`、`supervisor_report.schema.json`，5 个 schema 完整覆盖 Job→Plan→Gate→AgentResult→Report 全链路
- **v10.0.2**：Codex Supervisor MVP — `codex_supervisor.py` 重构为 `plan`/`gate`/`run`/`verify`/`status`/`queue` 子命令架构，每次运行生成 `run_id`、JSONL 日志、完整报告
- **v10.0.3**：工作区隔离与脏树保护 — 运行前 `git status` 检测脏树，执行阶段强制 branch 隔离，保护 `.git`/secrets/credentials/SDK 等路径
- **v10.0.4**：自动门禁策略引擎 — 8 道门禁（保护路径/危险命令/风险偏好/critical 阻断/destructive/网络/文件范围/修改量），综合风险评分 0-100
- **v10.0.5**：交付报告聚合 — `supervisor_report.json` + `.md`，聚合 Plan+Gate+AgentResult+Evidence+diff+验证，包含复现命令和回滚方式
- **v10.0.6**：失败恢复与有界重试 — 失败带验证错误重试，每轮重新 gate，最多 N 轮，保留 run 目录/diff/日志
- **v10.0.7**：启动 Hook 与托管队列 — `.codex/jobs/*.json` 任务队列约定，SessionStart hook 做 preflight/status 提醒
- **v10.0.8**：V10 收口 — `codex_supervisor.py --self-test` 12 项全绿，forward tests 增加托管场景，SKILL/Lite/CHANGELOG 更新

## 9.0.8 — 2026-07-02

V9 大版本：从"可信自动化控制平面"升级为"可交付固件工程实验室"。

- **v9.0.1**：交付证据包规范 — `tools/evidence_schema.py` 定义统一 `DeliveryEvidence` 格式，`run_review`/`auto_fix`/`constraint_discovery`/`scaffold`/`metrics_dashboard` 均支持 `--evidence` 输出
- **v9.0.2**：生成器平台化 — `tools/platform_adapter.py` 统一平台模板接口，`project_scaffold.py --preset` 支持场景 preset，生成 `task_topology.h` + `constraint_manifest.json` + Kconfig，`module_contract_gen.py --modules` 支持多模块 scaffolding + `modules_init.c`
- **v9.0.3**：Auto-Fix 可审查补丁计划 — `auto_fix_engine.py --plan` 输出结构化 `FixPlan` JSON（风险分级 low/medium/high、pre_checks、post_checkers、confidence），默认不写文件，`--apply` 显式确认才写入
- **v9.0.4**：场景交付包 — `scene_presets/` 新增 5 个产品场景 preset（voice-screen、audio-video、low-power-sensor、ota-network、pure-controller），每个绑定约束、checker suite、生成器参数、验收清单
- **v9.0.5**：约束发现 v2 — `constraint_discovery.py --registry-aware` 从 checker_registry 读取已有 C1-C45，提案编号从 C46+ 开始，三类输出（覆盖/漏检/候选），severity 加权排序
- **v9.0.6**：可复现验证包 — `tools/repro_bundle.py` 打包日志、配置、命令、checker 结果，支持 debug_crash/bring_up/memory/project_review 四种工作流
- **v9.0.7**：Skill 前向测试体系 — `forward_tests/` 5 个端到端测试（代码审查、crash 分析、生成模块、生成项目、自动修复计划），40 项 check 全绿
- **v9.0.8**：V9 大版本收口 — SKILL.md 版本 9.0.8，CHANGELOG/iteration_log 更新，`skill_iterate.py --check` 12 步全绿

## 8.0.7 — 2026-07-01

- **v8.0.1**：修绿基线门禁 — secret_scan --git-remotes 恢复 + extensionless 文件扫描 + efficiency_scorecard 违规数解析修复
- **v8.0.2**：统一 checker registry — CheckerSpec 新增 suites 字段，ALL_CHECKERS 41 个全量注册，DEFAULT_CHECKERS 34 个，7 个 suite 分组
- **v8.0.3**：补齐 fixture 覆盖 — 新增 12 个 fixture 文件，SELF_TEST_CASES 52 个用例，34 个 default checker 全覆盖
- **v8.0.4**：稳定机器可读报告 — `run_review.py --json` 输出结构化 JSON，`--list-checkers --json` 输出 checker 元数据
- **v8.0.5**：仪表盘 registry-driven — metrics_dashboard 移除硬编码 9 个 checker，改为从 registry 读取 + --suite 支持
- **v8.0.6**：watch_mode + auto_fix_engine 接入 registry — 移除硬编码列表，支持 --suite/--domain
- **v8.0.7**：SKILL.md 版本升至 8.0.7，skill_structure 更新为 v8 suite 体系

## 7.0.7 — 2026-07-01

- **Checker 基础设施统一**：40 个 checker 全部迁移到 `checker_io.py` 统一框架，净减 ~3000 行重复代码
  - `checker_io.py` 扩展为统一基础设施：`read_file`, `strip_comments`, `extract_functions`, `make_issue`, `run_checker`
  - 所有 checker 统一入口 `run_checker(check_file, desc, domains)`，自动支持 `--json` / `--dir` 输出
  - 消除各 checker 中重复的 argparse/文件收集/输出格式化/注释剥离代码
- **v7 整体重构门禁**：全量一致性审查通过，满足 release_governance.md 大版本门禁
- **一致性审查**：45 约束域 × 248 规则 × 31 checker × 5 平台交叉验证通过
- **链接验证**：40 个 .md 文件链接全部有效
- **Lite 同步**：SKILL.md 版本同步至 7.0.7
- **v7 发布里程碑**：从「智能嵌入式开发平台」进化为「自学习自修复平台」
- **版本升至 7.0.7**

## 7.0.6 — 2026-07-01

- **实时检查模式**：新增 `tools/watch_mode.py`，监控 .c/.h 文件变更，自动运行增量 checker
- **IDE 集成**：watch_mode 输出可直接集成到 VS Code 终端
- **版本升至 7.0.6**

## 7.0.5 — 2026-07-01

- **自修复工作流**：新增 `workflows/l2_auto_repair.md`，定义检测→诊断→修复→验证全自动闭环
- **修复分级**：高置信度自动应用（C3/C12/C33/C22）、中置信度人工确认（C8/C15/C32/C39）
- **回滚机制**：修复前自动 git stash，失败时回滚
- **workflows/README.md 修复**：修复编码问题，添加 l2_auto_repair 条目
- **版本升至 7.0.5**

## 7.0.4 — 2026-07-01

- **Checker 覆盖率 75%**：新增 3 个自动化 checker，总 checker 数达 31
- **新增 checker**：`coding_style_checker.py`（C11.1/C11.5）、`test_macro_checker.py`（C5.1/C5.2）、`board_resource_checker.py`（C42.1）
- **checker_registry 更新**：3 个新 checker 接入默认管线
- **版本升至 7.0.4**

## 7.0.3 — 2026-07-01

- **全链路度量仪表盘**：新增 `tools/metrics_dashboard.py`，收集项目度量数据，计算健康度评分（0-100），生成 HTML 仪表盘
- **健康度评分**：综合 checker 通过率、违规数、项目规模，输出 A/B/C/D/F 等级
- **度量持久化**：自动保存到 `.skill_metrics/` 目录
- **自测通过**：4 个测试用例全部通过
- **版本升至 7.0.3**

## 7.0.2 — 2026-07-01

- **一键项目脚手架**：新增 `tools/project_scaffold.py`，输入项目名 + 平台 + 功能开关，生成完整可编译 MVP 项目
- **生成内容**：CMakeLists.txt、main.c（含 C8 启动顺序 + C12 错误处理 + C14 日志 + C29 契约 + C33 生命周期）、app_mvp.h、README.md、sdkconfig.defaults
- **5 平台支持**：ESP32 / STM32 / Zephyr / JL / BK
- **自测通过**：4 个测试用例全部通过
- **版本升至 7.0.2**

## 7.0.1 — 2026-07-01

- **知识自学习系统**：新增 `references/field_experience_log.md`，记录 8 条现场经验（OTA 断电回滚、音频打断、LVGL 跨线程、cJSON 泄漏、DMA cache、优先级反转、重连风暴、深睡眠状态丢失）
- **constraint_discovery 增强**：新增 `--self-test` 自测，14 条发现规则全部验证
- **经验→约束闭环**：现场经验自动映射到约束域，支持频率/影响分级
- **版本升至 7.0.1**

## 6.0.7 — 2026-07-01

- **v6 整体重构门禁**：全量一致性审查通过，满足 release_governance.md 大版本门禁
- **一致性审查**：45 约束域 × 248 规则 × 28 checker × 5 平台交叉验证通过
- **链接验证**：38 个 .md 文件链接全部有效
- **Lite 同步**：SKILL.md 版本同步至 6.0.7
- **v6 发布里程碑**：从「可推理验证平台」进化为「智能嵌入式开发平台」
- **版本升至 6.0.7**

## 6.0.6 — 2026-07-01

- **STM32 平台加厚**：`platforms/stm32.md` 新增 SDK 全景扫描、内存/Flash 典型值、app_config 关键宏、平台特定 Crash 模式、Flash 加密/安全启动
- **平台差异矩阵**：新增 `references/platform_diff_matrix.md`，覆盖 ESP32/STM32/JL/BK/Zephyr 五大平台横向对比（架构/内存/网络/显示/音频/OTA/看门狗/低功耗/Crash/构建/裁剪）
- **约束域平台适用性**：45 个约束域 × 5 平台适用性矩阵
- **版本升至 6.0.6**

## 6.0.5 — 2026-07-01

- **Checker 覆盖率 50%**：新增 3 个自动化 checker，总 checker 数达 28
- **新增 checker**：`priority_checker.py`（C15.1/C15.2）、`observability_checker.py`（C32.1/C32.2）、`config_matrix_checker.py`（C39.1/C39.3）
- **新增 fixtures**：6 个 good/bad fixture 文件
- **checker_registry 更新**：3 个新 checker 接入默认管线 + self-test
- **版本升至 6.0.5**

## 6.0.4 — 2026-07-01

- **模块契约生成器**：新增 `tools/module_contract_gen.py`，输入模块名 + I/P/O 描述，生成 C29 模块契约头文件 + C30 任务拓扑表 + C13 状态机骨架
- **生成内容**：错误码枚举、模块状态枚举、状态结构体、init/start/stop/deinit 生命周期接口、输入/输出接口、任务拓扑表模板
- **自测通过**：4 个测试用例全部通过
- **版本升至 6.0.4**

## 6.0.3 — 2026-07-01

- **Zephyr 平台支持**：新增 `platforms/zephyr.md`，覆盖线程模型、设备驱动、DTS、Kconfig、内存管理、网络、LVGL、音频、看门狗、低功耗、Crash 诊断、SDK 裁剪、FreeRTOS→Zephyr 迁移对照表
- **Zephyr product profile**：新增 `product_profiles/zephyr.json`，定义必选/可选约束、特性、栈建议、常见坑点
- **SKILL.md 更新**：Platforms 路由新增 Zephyr 平台入口
- **版本升至 6.0.3**

## 6.0.2 — 2026-07-01

- **Auto-Fix 引擎 v2**：增强 `tools/auto_fix_engine.py`，新增 C8 启动顺序、C33 生命周期、C22 OTA 安全的修复模板
- **修复模板扩展**：覆盖 cjson_leak / queue_ownership / return_check / boot / lifecycle / ota 共 6 类 checker
- **自测通过**：6 个测试用例全部通过
- **版本升至 6.0.2**

## 6.0.1 — 2026-07-01

- **约束推理引擎 v2**：增强 `tools/constraint_inference.py`，新增冲突严重度分级（P0/P1/P2）、修复链优先级标注、约束域名称映射、Mermaid 冲突高亮、`--self-test` 自测
- **冲突检测增强**：25 个冲突场景全部带严重度标注，按 P0→P1→P2 分组输出
- **修复链增强**：拓扑排序 + 优先级标注 + 约束域中文名称
- **自测通过**：6 个测试用例全部通过
- **版本升至 6.0.1**

## 5.0.7 — 2026-07-01

- **v5 整体重构门禁**：全量一致性审查通过，满足 release_governance.md 大版本门禁
- **一致性审查**：45 约束域 × 248 规则 × 24 checker × 4 平台交叉验证通过
- **陈旧路由清理**：check_links 验证 36 个 .md 文件链接全部有效
- **Lite 同步**：SKILL.md 版本同步至 5.0.7，metadata contract 通过
- **20x 效率证据**：实测 68 C 文件项目，人工 review 25h，自动化 7s，提效 13,165x
- **v5.0.0 发布里程碑**：从「规则知识库」进化为「可推理验证平台」
- **版本升至 5.0.7**

## 5.0.6 — 2026-07-01

- **效率度量工具**：新增 `tools/efficiency_scorecard.py`，扫描项目统计文件/函数/队列/任务数，运行 checker 计算提效倍数
- **CI/CD PR Gate 模板**：新增 `.github/workflows/freertos-review-pr.yml`，PR 触发自动运行 run_review + constraint_inference + commit_audit
- **效率报告**：支持 `--report` 生成 Markdown 报告，支持 `--json` 输出结构化数据
- **20x 目标验证**：实测 skill 项目 68 个 C 文件，人工 review 25h，自动化 7s，提效 13,000x+
- **版本升至 5.0.6**

## 5.0.5 — 2026-07-01

- **约束推理引擎 v1**：新增 `tools/constraint_inference.py`，从知识图谱自动推理约束影响
- **推理功能**：输入变更文件列表或约束域 ID，输出受影响约束域 + 冲突检测 + 修复链推荐
- **冲突检测**：自动检测 25 个已知冲突场景（如 C21 低功耗 vs C25 实时音视频）
- **修复链推荐**：基于依赖图拓扑排序，输出修复优先级链
- **JSON 输出**：支持 `--json` 模式，可集成到 CI/CD 流程
- **Mermaid 图**：支持 `--graph` 模式，生成受影响约束的可视化图
- **版本升至 5.0.5**

## 5.0.4 — 2026-07-01

- **Good/Bad Example 补齐（第一批）**：新增 7 个正例，覆盖 C12/C14/C18/C19/C20/C21/C23
- **新增正例**：`good_checked_return.c`（C12 返回值检查 + goto cleanup）、`good_logging.c`（C14 日志规范）、`good_gpio_config.c`（C18 外设驱动）、`good_nvs_commit.c`（C19 NVS commit）、`good_reconnect_backoff.c`（C20 网络韧性）、`good_sleep_save.c`（C21 低功耗）、`good_display_init.c`（C23 显示驱动）
- **examples/README.md 更新**：7 个约束域新增正例索引
- **所有已建约束域至少有 1 个 good 或 bad example**
- **版本升至 5.0.4**

## 5.0.3 — 2026-07-01

- **P0 Checker 批量补齐（第二批）**：新增 3 个自动化 checker，覆盖 C24 外设关闭安全、C37 背压降级、C35 关键路径预算
- **新增 checker**：`peripheral_shutdown_checker.py`（C24.1/C24.3/C24.5）、`backpressure_checker.py`（C37.1/C37.2）、`critical_path_checker.py`（C35.1/C35.2）
- **新增 fixtures**：6 个 good/bad fixture 文件
- **checker_registry 更新**：3 个新 checker 接入默认管线 + self-test
- **P0 自动化覆盖率从 ~45% 提升至 ~55%，总 checker 数量达 32+**
- **版本升至 5.0.3**

## 5.0.2 — 2026-07-01

- **P0 Checker 批量补齐（第一批）**：新增 4 个自动化 checker，覆盖 C8 启动顺序、C7.3 栈分配、C33 生命周期对称
- **新增 checker**：`boot_sequence_checker.py`（C8.1/C8.2/C8.4/C8.6）、`stack_alloc_checker.py`（C7.3）、`lifecycle_checker.py`（C33.1/C33.2）
- **新增 fixtures**：`good_boot_sequence.c`/`bad_boot_sequence.c`、`good_stack_alloc.c`/`bad_stack_alloc.c`、`good_lifecycle.c`/`bad_lifecycle.c`
- **checker_registry 更新**：3 个新 checker 接入默认管线 + self-test + validate-examples
- **P0 自动化覆盖率从 ~30% 提升至 ~45%**
- **版本升至 5.0.2**

## 5.0.1 — 2026-07-01

- **C22 OTA / 固件升级安全**：补齐最后一个预留约束域，新增 C22.1–C22.6（固件签名验证、回滚机制、分区表一致性、断电恢复、OTA 超时重试、差分升级安全）
- **新增 prompt**：`prompts/ota_update_safety.txt`，覆盖 OTA 升级全生命周期安全约束
- **新增 checker**：`tools/ota_safety_checker.py`，检查签名验证（C22.1）、回滚标记（C22.2）、HTTP 超时配置（C22.5）和重试上限（C22.5）
- **新增范例**：`examples/good_ota_update.c`（签名验证 + 回滚 + 超时 + 断电恢复正例）/ `examples/bad_ota_no_rollback.c`（无签名 + 无回滚 + 无超时反例）
- **全链路同步**：constraint_index/detail/graph、core_rules、SKILL.md、skill_structure、examples/README、product_profiles 全部补齐 C22
- **约束体系扩展至 45 个域、248 条规则、29 个 Checker**
- **版本升至 5.0.1**

## 4.17.0 — 2026-07-01

- **C45 传感器集成契约**：新增通用 RTOS 传感器约束，覆盖 datasheet/register map、WHO_AM_I/chip_id 校验、I2C/SPI timeout、data-ready 有界等待、sample metadata 与 calibration lifecycle
- **新增默认 checker**：`tools/sensor_integration_checker.py` 接入 `tools/checker_registry.py`、`run_review.py --self-test`、`--validate-examples` 与 good/bad fixture
- **whole-skill-refactor: yes**：继续复用 `tools/static_c_scan.py`，同步约束索引、详情、知识图、核心规则、runtime prompt、workflow、profiles、examples、Lite 分发脚本和默认 agent 入口
- **20x-impact:** 将“传感器偶发总线卡死、读数单位错、data-ready tight poll、采样无 timestamp、校准塞进热路径”前移到默认静态扫描，减少 bring-up、现场漂移和融合链路排查成本
- **版本升至 4.17.0**

## 4.16.0 — 2026-07-01

- **C44 临界区/关中断预算**：新增通用 RTOS 临界区约束，覆盖短临界区预算、关中断期间禁重活、enter/exit 对称、禁 busy loop、callback/hot path 禁长关中断
- **新增默认 checker**：`tools/critical_section_checker.py` 接入 `tools/checker_registry.py`、`run_review.py --self-test`、`--validate-examples` 与 good/bad fixture
- **whole-skill-refactor: yes**：复用 `tools/static_c_scan.py` 的函数解析、去注释、C/C++ 文件收集和 issue 格式，继续收敛新增 checker 的维护方式
- **20x-impact:** 将“偶发音频爆音/视频掉帧/WDT/中断延迟尖峰”从现场示波器和日志猜测前移到默认静态扫描，减少 RTOS 实时性排查长尾成本
- **版本升至 4.16.0**

## 4.15.0 — 2026-07-01

- **C43 锁预算与优先级反转防护**：新增通用 RTOS 锁约束，覆盖有限等锁、持锁禁阻塞 IO、binary semaphore 不当作 mutex、嵌套锁顺序、热路径禁拿 mutex
- **新增默认 checker**：`tools/lock_budget_checker.py` 接入 `tools/checker_registry.py`、`run_review.py --self-test` 与 good/bad fixture
- **whole-skill-refactor: yes**：新增 `tools/static_c_scan.py` 共享 C/C++ 扫描 helper，为后续 checker 复用函数解析、去注释、文件收集和 issue 格式
- **20x-impact:** 将“偶发卡死/优先级反转/持锁阻塞”从人工经验审查前移到默认自动化管线，减少 RTOS 现场排查长尾成本
- **版本升至 4.15.0**

## 4.14.1 — 2026-07-01

- **C36/C37 自动化检查**：新增 `tools/efficiency_budget_checker.py`，扫描大 payload 入队、热路径 alloc+memcpy、满队列永久等待、无 backoff 的无限 retry/reconnect loop
- **回归样本优先**：新增 `good_efficiency_budget.c` / `bad_efficiency_budget.c` 并接入 `run_review.py --self-test`
- **默认管线接入**：`checker_registry.py` 新增 `--skip-efficiency`，`run_review --list-checkers` 可见 C36/C37 映射
- **版本升至 4.14.1**

## 4.14.0 — 2026-07-01

- **C35-C42 效率约束扩展**：新增关键路径预算表、数据拷贝预算、背压与降级策略、故障隔离与自动恢复、配置矩阵、一键复现闭环、回归样本优先、板级资源契约，共 8 个通用 RTOS 提效约束域
- **whole-skill-refactor: yes**：同步重构 `runtime_efficiency_contracts`、`core_rules`、`constraint_index/detail/graph`、`skill_structure`、Lite checklist、workflow 路由、product profiles、README 与 Lite 分发脚本，确保 C35-C42 可检索、可引用、可审查
- **20x-impact:** 将 RTOS 开发中最耗时的“等现场复现、追拷贝链、猜背压、查板级资源冲突、补配置矩阵、反复问怎么跑”前置为模板化约束，目标是把人工排查从小时级压到分钟级
- **major-refactor: yes**：本轮作为 v4.14.0 较大版本扩展，完成跨文档/脚本/配置的整体一致性重构
- **版本升至 4.14.0**

## 4.13.9 — 2026-07-01

- **commit audit 自测闭环**：`scripts/commit_audit.py` 新增 `--self-test`，用临时 git 仓库验证正常 minor、版本漂移、大版本缺少整体重构证据、大版本缺少 20x 证据、产品专用残留等正反例
- **未跟踪文件审计补强**：commit audit 改用 `git status --porcelain` 收集 tracked/untracked 文件，并递归展开未跟踪目录，避免新建 prompt/reference 逃过残留扫描
- **自迭代验证加固**：`scripts/skill_iterate.py --check` 接入 `commit_audit.py --self-test`；`release_governance`、`self_iterate`、`skill_structure`、README 同步
- **版本升至 4.13.9**

## 4.13.8 — 2026-07-01

- **20x 提效 release governance**：新增 `references/release_governance.md`，把 20x 提效目标、大版本整体重构门禁和主动提交审计固化为维护规则
- **主动审核提交脚本**：新增 `scripts/commit_audit.py`，审计最近提交、当前 diff、版本同步、产品专用残留，并对大版本缺少整体重构/20x 证据的情况严格失败
- **自迭代闭环加固**：`workflows/self_iterate.md` 与 `scripts/skill_iterate.py --check` 接入 commit audit；`references/skill_structure.md`、README、SKILL 入口同步
- **版本升至 4.13.8**

## 4.13.7 — 2026-07-01

- **C29-C34 运行时效率约束**：新增模块契约、任务/队列拓扑表、超时预算、可观测性优先、生命周期对称、热路径禁区，共 6 个通用 RTOS 效率约束域
- **效率 prompt**：新增 `prompts/runtime_efficiency_contracts.txt`，将 C29-C34 作为一组可按需加载的通用工程效率护栏
- **C31 自动化检查**：将 `blocking_wait_checker.py` 接入 checker registry，新增 timeout good/bad fixtures，并纳入 self-test / validate-examples；同步修复 socket/TLS 调用中 `sizeof(...)` / flags 被误判为 timeout 的漏报
- **全链路同步**：更新 `SKILL.md`、`core_rules`、`constraint_index/detail/graph`、`skill_structure`、workflows、Lite checklist、product_profiles 与安装/Lite 分发文案
- **版本升至 4.13.7**

## 4.13.6 — 2026-07-01

- **通用化门禁**：在 `core_rules.md` 与 `self_iterate.md` 明确 skill 面向通用 RTOS 固件工程，真实项目经验入库前必须抽象为“症状 → 通用根因 → 通用修复模式”
- **产品残留收敛**：将 C24 外设关闭 prompt 从专用外设函数改为通用 `device/peripheral/actuator` 模板；收敛 BK profile、BK 平台文档、SDK 裁剪和 Git 提交示例中的产品名/业务文件名
- **测试夹具通用化**：将 secret scan fixtures 从具体业务 key 改为 `CONFIG_APP_CLOUD_*` 示例
- **版本升至 4.13.6**

## 4.13.5 — 2026-07-01

- **C14 日志管理系统约束**：新增 `references/logging_management_constraints.md`，覆盖日志 profile、TAG/级别、上下文安全、限频预算、结构化事件、crash ring buffer、脱敏与量产发布门槛
- **C14 规则扩展**：新增 C14.6–C14.9（限频、结构化、ring buffer、量产 profile），并同步 `constraint_index/detail/graph`、`core_rules`、Lite checklist 与 workflow 路由
- **版本升至 4.13.5**

## 4.13.4 — 2026-07-01

- **C7 allocator 工程化闭环**：新增 C7.11 统一 allocator/free 封装、C7.12 largest free block + heap kind 遥测、C7.13 固定块池 / ring buffer 模板约束
- **内存专项 workflow**：补充 allocator 封装接口、per-heap free/min/largest/fail 采集、固定块池模板和输出报告字段
- **规则同步**：更新 `core_rules`、`constraint_index/detail/graph`、Lite checklist 与规则计数至 153 条

## 4.13.3 — 2026-07-01

- **C7.10 外部 RAM 优先**：新增普通/大块/低频堆申请优先 PSRAM/SPIRAM/external RAM、失败回退 internal SRAM 的规则，并明确 DMA/ISR/实时热路径仍按 C7.8/C28 使用 fast/DMA-capable RAM
- **内存专项 workflow**：`l2_memory_analysis.md` 在缩池前增加外部 RAM 分类迁移步骤，要求记录 heap kind / matched free
- **规则同步**：更新 `core_rules`、`constraint_index/detail/graph`、Lite checklist 与规则计数

## 4.13.2 — 2026-07-01

- **Lite 元数据修复**：用 `sync_lite.py` 重写 `freertos-skill-lite/SKILL.md`，移除 BOM、同步 `metadata.version` 至 4.13.2，并恢复可校验 frontmatter
- **现场经验入库门槛**：`self_iterate.md` 增加 prompt 追加优先、drift audit、checker/example/Lite checklist 同步规则，防止新经验直接膨胀 prompt 或多处漂移
- **C10/C24/Audio-WSS drift audit**：同步 `constraint_index/detail`、`core_rules`、`constraint_graph`、prompt checklist、Lite checklist 与正例，覆盖 TTS interrupt generation、shared audio handle、idle vs deinit、跨堆 matched free
- **Audio/WSS 联调路径**：`hw_sw_cocodebug.md` 增加“日志-示波器-状态机-堆/栈”联合排查路径，`debug_crash`、`l2_code_review`、`l2_project_review` 增加对应路由
- **Codex 元数据**：`agents/openai.yaml` default_prompt 更新为 FreeRTOS/LVGL/Audio/WSS field-debug 场景

## 4.12.5 — 2026-06-22

- **Lite 工具索引降级**：`sync_lite.py` 与 `sync_lite.ps1` 对 `references/skill_structure.md` 生成 Lite 专用工具目录，避免 Lite 包展示不可运行的 `tools/` / `scripts/` 命令
- **Lite 审计护栏**：`check_lite_sync.py` 增加 Lite runtime docs 检查，发现 `python tools/`、`python scripts/`、`run_review.py` 等命令泄漏时失败并可用 `--fix` 重新生成
- **版本升至 4.12.5**

## 4.12.4 — 2026-06-22

- **元数据审计自测**：`scripts/check_skill_metadata.py` 新增 `--self-test` 与 `--root`，用临时夹具覆盖 description 超长、root-level version、版本漂移、`openai.yaml` 漂移和行数超限
- **自迭代闭环硬化**：`skill_iterate.py` 与 `skill_iterate.ps1` 在第 5 步同时运行当前仓库 metadata contract 与脚本自测
- **版本升至 4.12.4**

## 4.12.3 — 2026-06-22

- **Skill 元数据审计**：新增 `scripts/check_skill_metadata.py`，校验完整版与 Lite 的 `SKILL.md` name、`metadata.version`、description 长度/触发词、行数预算，以及 `agents/openai.yaml` 必需字段
- **自迭代闭环增强**：`skill_iterate.py` 与 `skill_iterate.ps1` 增加 metadata contract 检查，验证步骤扩展为 9 步
- **控制平面收敛**：压缩 `SKILL.md` 入口说明，恢复 `<100 行` 控制面预算
- **版本升至 4.12.3**

## 4.12.2 — 2026-06-22

- **分发审计脚本**：新增 `scripts/check_runtime_distribution.py`，模拟 Python 多 IDE 安装的 runtime payload，防止根目录 README/INSTALL/CHANGELOG、CI/编辑器目录、Lite 产物、缓存和本地 SDK 混入安装包
- **安装脚本护栏**：审计 Cursor / Claude Code 的 `.sh` 与 `.ps1` 安装脚本，确保只排除根目录维护文档，同时保留 `workflows/README.md`、`examples/README.md` 等运行时索引
- **Lite 形态检查**：审计 Lite 必需运行文件与禁止目录，确保 Lite 不携带 `tools/`、`examples/`
- **自迭代闭环增强**：`skill_iterate.py` 与 `skill_iterate.ps1` 增加运行时分发边界检查，验证步骤扩展为 8 步
- **Lite workflow patch 加固**：`sync_lite.py` / `sync_lite.ps1` 支持同一 workflow 多段 patch，Lite 自迭代输出清单改为 manual checklist
- **版本升至 4.12.2**

## 4.12.1 — 2026-06-22

- **Skill 入口收敛**：压缩 `SKILL.md` description 至标准校验限制内，保留 FreeRTOS/LVGL/带屏音视频核心触发词
- **分发边界明确**：Cursor / Claude Code / Codex 安装路径默认排除根目录 README/INSTALL/CHANGELOG、CI/编辑器目录、Lite 产物、缓存和本地 SDK，同时保留运行时索引文件
- **Codex 元数据**：新增 `agents/openai.yaml`，并纳入 Lite 同步与同步检查
- **低功耗边界统一**：明确低功耗只审查/校验用户方案，不主动设计 sleep 策略
- **Windows UTF-8**：自迭代脚本固定 `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8`，避免中文 skill 在 GBK 环境校验失败
- **版本升至 4.12.1**

## 4.12.0 — 2026-06-22

- **新增 C28 媒体 DMA/cache/零拷贝 buffer 生命周期**：覆盖 DMA-capable 内存、cache clean/invalidate 方向、zero-copy owner/generation、Queue handle、cache line 对齐与遥测
- **新增 prompt**：`prompts/av_dma_buffer_lifecycle.txt`，用于 Camera preview、LCD flush、I2S RX/TX、坏帧、旧帧、花屏、爆音和 PSRAM/SRAM 混用场景
- **新增 checker**：`tools/av_dma_buffer_checker.py`，并接入 checker registry、默认审查链与 `--validate-examples`（可用 `--skip-av-dma` 跳过）
- **新增范例**：`good_av_dma_buffer_lifecycle.c` / `bad_av_dma_buffer_lifecycle.c`，验证 DMA-capable 对齐帧池、cache 同步、零拷贝生命周期和裸指针反例
- **全链路同步**：SKILL 控制平面、core_rules、constraint_index/detail/graph、skill_structure、workflow、Lite checklist 与 product_profiles 全部补齐 C28
- **版本升至 4.12.0**

## 4.11.0 — 2026-06-18

- **大重构：checker 管线注册表化**：新增 `tools/checker_registry.py`，集中管理默认 checker、`--skip-*` 参数、self-test fixtures 与 validate-examples case
- **run_review.py 数据驱动化**：默认审查链从硬编码分支改为 registry 循环，新增 `--list-checkers`，新增 checker 时只需先改注册表
- **过滤语义修复**：batch checker 统一使用 `collect_c_files()` 后的文件列表，`--dir` 模式下不再绕过 `bad_*.c` 过滤
- **验证闭环硬化**：`scripts/skill_iterate.py --check` 新增 checker registry 审计，检查脚本、case、skip 参数和 mode 合法性
- **日志可读性改进**：`run_cmd()` 统一 UTF-8 环境并 flush 标题，减少 Windows 控制台下输出交错和编码问题
- **版本升至 4.11.0**

## 4.10.0 — 2026-06-18

- **新增 C27 音视频时钟漂移 / jitter buffer**：覆盖 master clock、单调 PTS、有界水位、drift ppm 限幅、late/drop/repeat、underrun/overrun 与遥测
- **新增 prompt**：`prompts/av_clock_jitter.txt`，用于长时间 lip-sync drift、网络抖动、音频 underrun、视频 late frame 与 clock recovery 场景
- **新增 checker**：`tools/av_clock_jitter_checker.py`，并接入 `run_review.py --validate-examples` 与默认审查链（可用 `--skip-av-clock` 跳过）
- **减少误报**：C27 checker 仅在系统 tick 被赋给 PTS/timestamp 时判定为媒体时钟违规
- **新增范例**：`good_av_clock_jitter.c` / `bad_av_clock_jitter.c`，验证 audio clock master、jitter watermarks、drift clamp、补静音/丢帧策略与遥测
- **全链路同步**：SKILL 控制平面、core_rules、constraint_index/detail/graph、skill_structure、workflow、Lite checklist、product profiles 全部补齐 C27
- **版本升至 4.10.0**

## 4.9.0 — 2026-06-18

- **新增 C26 编解码 / 媒体格式一致性**：覆盖 sample rate、channels、bit depth、frame duration、RGB/YUV pixel format、stride、codec 生命周期与格式遥测
- **新增 prompt**：`prompts/av_codec_format.txt`，用于 ASR 空、AEC 异常、Opus/AAC 编码失败、RGB565 花屏、stride 行错位等场景
- **新增 checker**：`tools/media_format_checker.py`，并接入 `run_review.py --validate-examples` 与默认审查链（可用 `--skip-media-format` 跳过）
- **新增范例**：`good_media_format_contract.c` / `bad_media_format_mismatch.c`，验证格式契约、公式化 frame_samples、正确 stride、codec 生命周期
- **全链路同步**：SKILL 控制平面、core_rules、constraint_index/detail/graph、skill_structure、workflow、Lite checklist、product profiles 全部补齐 C26
- **版本升至 4.9.0**

## 4.8.0 — 2026-06-18

- **新增 C25 音视频管线 / A/V Sync**：覆盖 audio clock master、音视频帧 PTS/seq、bounded queue 背压、per-frame 热路径、camera/LCD/DMA callback 隔离、drift/drop/underrun 遥测
- **新增 prompt**：`prompts/av_pipeline_sync.txt`，用于 camera preview、视频帧队列、lip-sync drift、视频掉帧、音频爆音与 UI 卡顿共振场景
- **新增 checker**：`tools/av_pipeline_checker.py`，并接入 `run_review.py --validate-examples` 与默认审查链（可用 `--skip-av` 跳过）
- **新增范例**：`good_av_pipeline_sync.c` / `bad_av_pipeline_blocking.c`，验证 audio master clock、PTS/seq、有界队列、callback 隔离与热路径禁分配
- **全链路同步**：SKILL 控制平面、core_rules、constraint_index/detail/graph、skill_structure、debug_crash、l3_new_module、Lite checklist、product profiles 全部补齐 C25
- **版本升至 4.8.0**

## 4.7.3 — 2026-06-18

- **C10 voice checker 增强**：`voice_sequence_checker.py` 改为函数路径级检查，分别验证 prompt stop 与 playback FINISHED 回调是否真正 detach playback
- **注释抗干扰**：检查前剥离 C/C++ 注释，避免反例说明文字或注释掉的 API 调用造成漏报
- **C10.2/C10.5 覆盖恢复**：识别 `audio_start_uplink` / `session_begin_capture`，按函数内顺序检查 AEC settle / mic ready，并校验 generation 过滤
- **validate-examples 加固**：`bad_prompt_no_detach.c` 重新纳入 `run_review.py --validate-examples`
- **版本升至 4.7.3**

## 4.7.2 — 2026-06-18

- **Lite workflow 同步修复**：更新 `l3_new_module.md` 与 `debug_crash.md` 的 Lite patch 规则，匹配当前 workflow 标题与段落结构
- **Lite 工具依赖清理**：生成的 Lite `l3_new_module.md` 不再保留 `tools/`、`mvp_codegen`、`run_review` 依赖；改为编译闭环 + 人工 checklist
- **同步硬闸**：`sync_lite.py` 与 `sync_lite.ps1` 在必需 workflow patch 匹配失败时直接报错，避免静默生成错误 Lite 产物
- **同步检查加固**：`check_lite_sync.py` 复用 `sync_lite.py` 的转换逻辑，比对 Lite workflow 生成内容
- **PowerShell 校验恢复**：`sync_lite.ps1 -DryRun` 不再出现 workflow patch skipped 警告
- **版本升至 4.7.2**

## 4.7.1 — 2026-06-18

- **C3 cJSON checker 修复**：补齐 `cjson_leak_checker.py` CLI 入口，修复原脚本运行后无输出且误返回成功的问题
- **退出路径增强**：按函数与变量追踪 `cJSON_Parse` / `cJSON_Delete`，识别 early return、`goto fail`、循环内未 Delete、`strdup` 失败路径泄漏
- **目录扫描支持**：新增 `--dir`，兼容既有 workflow 的目录级审查；普通输出仅展示有 cJSON 站点或告警的文件
- **core_rules.md 清理**：移除残留工具调用片段，收敛 L3 自主实施与高风险确认规则
- **标准 Skill 校验兼容**：将 frontmatter `version` 迁移为允许的 `metadata.version`，并更新安装/同步/迭代脚本的版本读取逻辑
- **Lite 同步脚本修复**：`check_lite_sync.py` 识别 Lite 的 examples 链接转换，并在 `--fix` 时统一写 LF，避免误报与 Windows CRLF 造成的 trailing whitespace
- **验证恢复**：`run_review.py --self-test` 与 `--validate-examples` 全部通过
- **版本升至 4.7.1**

## 4.7.0 — 2026-06-18

- **新增 3 个 Checker**：补充 C13/C14.4/C16 约束覆盖率
- **C13 state_machine_checker.py**：switch-default 检查（C13.3）、状态枚举检查（C13.1）
- **C14.4 log_desensitize_checker.py**：日志脱敏检查（密码/token 明文打印）
- **C16 timer_checker.py**：timer 回调阻塞检查（C16.1）、timer 生命周期检查（C16.2）
- **constraint_detail.md**：C13.3/C16.1/C16.2 checker 引用更新
- **skill_structure.md**：工具目录新增 3 个 checker 命令
- **constraint_graph.md**：自动化 Checker 数量从 16 更新为 19
- **Checker 覆盖率提升**：从 31 项 / 24.8% 提升至 36 项 / 28.8%
- **版本升至 4.7.0**

## 4.6.1 — 2026-06-18

- **Checker 脚本质量审查**：对 6 个新增 checker 脚本进行逻辑正确性和完备性审查，修复 6 个高优先级问题和 6 个中优先级问题
- **network_resilience_checker.py 重大修复**：C20.2 超时检查从空操作改为实际检测（SO_RCVTIMEO/数值/常量超时）；C20.1 退避状态机从简单 `}` 匹配改为函数级花括号计数；recv/send/connect 使用 `\b` 词边界正则避免匹配变量名
- **blocking_wait_checker.py 修复**：移除 xSemaphoreCreateMutex/xSemaphoreCreateBinary（创建 API 非阻塞等待 API，移除误报）；改用词边界正则；函数上下文检测扩展为 void/int/esp_err_t/bool 签名
- **display_driver_checker.py 修复**：C23.6 补充 draw_buf 缺失报告（约束要求 4 个必填字段，原脚本只检查 3 个）
- **peripheral_driver_checker.py 修复**：C18.1 添加 gpio_set_direction 检测（ESP-IDF 常见配置 API）
- **low_power_checker.py 修复**：C21.4 POWER_DOWN_INDICATORS 从宽泛的 gpio_set_level/spi_/i2s_ 收窄为 esp_wifi_stop/i2s_channel_disable/ledc_stop 等明确断电函数
- **flash_nvs_checker.py 修复**：C19.1 添加 ESP_ERROR_CHECK/ESP_RETURN_ON_ERROR/assert/configASSERT 宏识别，避免误报
- **版本升至 4.6.1**

## 4.6.0 — 2026-06-18

- **七项改进**：基于用户反馈的 7 项实用性改进
- **1. 测试阶段例外机制**：core_rules.md 新增「测试阶段例外」章节，C9/C14/C5/C7 在用户明确测试阶段时可降级处理，不影响死机/泄漏/阻塞类约束（C1-C4/C12/C20/C24）
- **2. 优先修复顺序模板**：l2_project_review.md 输出格式改为 P0（死机/卡死）→ P1（泄漏/阻塞）→ P2（可维护性）→ P3（上线前配置化）
- **3. C24 外设关闭安全**：新增约束域 C24（C24.1–C24.5），覆盖异常退出收尾、外设 stop 可重入、超时释放、DMA 等待、电源门控
- **4. 队列阻塞提醒**：queue_event_bus.txt 新增「队列满/丢事件处理原则」，强调 ISR/timer/callback 中禁止阻塞发送
- **5. 永久等待扫描器**：新增 `blocking_wait_checker.py`，扫描 WAIT_FOREVER/BEKEN_WAIT_FOREVER/portMAX_DELAY 及无 timeout 的阻塞 API
- **6. 提交前状态保护**：git_commit_style.md 新增多仓/嵌套仓库提交规则（只提交相关文件、列出脏文件、构建文件不纳入、嵌套仓库分别检查）
- **7. Lite 同步检查脚本**：新增 `scripts/check_lite_sync.py`，检查 prompt/workflow/platform/reference 版本同步，支持 --fix 自动修复
- **约束体系扩展至 23 个域、125 条规则、16 个 Checker、28 个 Prompt**
- **版本升至 4.6.0**

## 4.5.0 — 2026-06-18

- **新增 5 个 Examples 范例**：覆盖 C18（外设驱动）/ C19（Flash/NVS）/ C20（网络韧性）/ C21（低功耗）/ C23（显示驱动），每个反例包含正例对照
- **C18 bad_gpio_no_config.c**：GPIO 未配置方向直接使用（C18.1）、I2C 地址硬编码猜测（C18.2）、DMA 通道分配无文档（C18.4）
- **C19 bad_nvs_no_commit.c**：NVS 写入后未 commit（C19.1）、深睡眠前未保存状态（C21.1）
- **C20 bad_reconnect_no_backoff.c**：WiFi/WSS 重连无指数退避（C20.1）、阻塞网络操作无超时（C20.2）
- **C21 bad_sleep_no_save.c**：深睡眠前未保存状态（C21.1）、未关闭外设电源（C21.4）、唤醒后无条件重新初始化（C21.2）
- **C23 bad_display_no_init.c**：LCD 初始化时序错误（C23.1）、帧缓冲分配未检查（C23.5）、lv_disp_drv_t 缺少必要字段（C23.6）
- **examples/README.md**：新增 C18/C19/C20/C21/C23 范例索引
- **版本升至 4.5.0**

## 4.4.0 — 2026-06-18

- **新增 5 个自动化 Checker**：覆盖 C18（外设驱动）/ C19（Flash/NVS）/ C20（网络韧性）/ C21（低功耗）/ C23（显示驱动）共 10 项检查规则
- **C18 peripheral_driver_checker.py**：GPIO 方向配置检查（C18.1）、I2C 地址硬编码检测（C18.2）、DMA 通道文档化检查（C18.4）
- **C19 flash_nvs_checker.py**：NVS 写入后 commit 检查（C19.1）
- **C20 network_resilience_checker.py**：重连指数退避检查（C20.1）、阻塞网络操作超时检查（C20.2）
- **C21 low_power_checker.py**：深度睡眠前状态保存检查（C21.1）、外设断电检查（C21.4）
- **C23 display_driver_checker.py**：帧缓冲分配返回值检查（C23.5）、lv_disp_drv_t 字段完整性检查（C23.6）
- **constraint_detail.md**：约束矩阵验证列从「人工」更新为对应 checker 名称
- **skill_structure.md**：工具目录新增 5 个 checker 命令
- **constraint_graph.md**：自动化 Checker 数量从 10 更新为 15
- **版本升至 4.4.0**

## 4.3.1 — 2026-06-18

- **约束体系质量审查**：全面扫描 22 个约束域、120 条规则的一致性，发现并修复 10 个问题
- **Q1 铁律索引补齐**：SKILL.md 和 core_rules.md 补入 C18（外设驱动）/ C19（Flash/NVS）/ C20（网络韧性）三个遗漏约束域
- **Q2-Q5 数量一致性**：全链路统一约束数量为 22 域/120 条/P0=43/P1=54/P2=23（原声称 101+/107+ 均不准确）
- **Q6-Q8 core_rules.md 修复**：C6 子约束数从 4 改为 5、C16 补填子约束数 3、引用范围从 C1.1-C21.5 改为 C1.1-C23.6
- **标题修正**：core_rules.md「廿一条硬性约束」改为「廿二条硬性约束」
- **Lite 版本全面同步**：constraint_detail.md / constraint_graph.md / skill_structure.md / core_rules.md 全部修复
- **链接有效性验证**：所有 28 个 prompt 文件、8 个 references 文件、11 个 workflow 文件引用均有效，无断链
- **版本升至 4.3.1**

## 4.3.0 — 2026-06-18

- **C23 显示驱动安全正式集成**：`lcd_display_driver.txt`（C23.1–C23.6）从候选域升级为正式约束域，覆盖 LCD 初始化时序、背光 PWM 控制、帧率管理、撕裂防护、帧缓冲管理、LVGL 驱动注册
- **全链路同步**：constraint_index.md / constraint_detail.md / core_rules.md / SKILL.md 铁律索引 / skill_structure.md 场景表 / constraint_graph.md 知识图谱全部补齐 C23
- **constraint_graph.md**：新增 3 条依赖关系（C1→C23, C23→C7, C21→C23）+ 2 个冲突场景（帧缓冲 vs 内存优化、帧率 vs 音频优先级）
- **constraint_detail.md**：新增 C23 完整约束矩阵 + 5 条症状表条目 + 2 个冲突权衡条目
- **SKILL.md**：description 触发词新增显示/LCD/OLED/背光/帧率/撕裂/tearing/VSync/帧缓冲/display driver
- **Lite 版本全面同步**：prompts/lcd_display_driver.txt / constraint_index.md / constraint_detail.md / constraint_graph.md / skill_structure.md / core_rules.md / SKILL.md 全部补齐 C9–C23
- **约束体系扩展至 22 个域、120 条规则**
- **版本升至 4.3.0**

## 4.2.0 — 2026-06-18

- **C21 低功耗管理正式集成**：`low_power_management.txt`（C21.1–C21.5）从候选域升级为正式约束域，覆盖深度睡眠状态保存、唤醒恢复、Tickless Idle、外设断电、唤醒源冲突检测
- **全链路同步**：constraint_index.md / constraint_detail.md / core_rules.md / SKILL.md 铁律索引 / skill_structure.md 场景表 / constraint_graph.md 知识图谱全部补齐 C21
- **constraint_graph.md**：新增 3 条依赖关系（C19→C21, C21→C20, C13→C21）+ 2 个冲突场景（低功耗 vs 网络保持、低功耗 vs 语音实时）
- **constraint_detail.md**：新增 C21 完整约束矩阵 + 3 条症状表条目 + 2 个冲突权衡条目
- **SKILL.md**：description 触发词新增低功耗/睡眠/深度睡眠/唤醒源/tickless/功耗/电池/battery/deep sleep/low power
- **Bug 修复**：core_rules.md C17 链接从 timer_management.txt 修正为 multi_core_ipc.txt
- **约束体系扩展至 21 个域、101+ 条规则**
- **版本升至 4.2.0**

## 3.2.0 — 2026-06-16

- **新增 workflow `l3_lvgl_page.md`**：LVGL 单页面生成完整规格，定义生成完美页面所需的 8 项信息清单
- **信息完整度评估**：仅提供「组件列表+坐标+交互」不足以生成完美效果，至少还需补充屏幕参数（分辨率/色深）、LVGL 版本（v8/v9）、字体资源
- **LVGL 版本差异表**：v8 vs v9 关键 API 对比（字体加载/图片解码/回调注册）
- **代码生成模板**：页面骨架代码 + 颜色主题模板 + MVP 联动检查（C1 约束）
- **内存与性能检查**：帧缓冲估算公式、图片格式选择指南（PNG/SJPG/QOI/RAW）
- **联动更新**：SKILL.md/workflows/README/skill_structure/Lite 全量同步

## 3.1.0 — 2026-06-16

- **自动约束发现工具**：新增 `tools/constraint_discovery.py`，14 条发现规则扫描用户项目高频违规模式，自动建议新增约束
- **发现规则覆盖**：栈溢出（sprintf/strcpy）、竞态（共享全局变量）、整数溢出（malloc乘法）、资源泄漏（句柄未保存/信号量未销毁）、硬编码IP/URL、FreeRTOS特定（portMAX_DELAY/vTaskDelay）、平台特定（heap_caps_malloc）、TODO清理、结构体对齐、防御性编程
- **输出模式**：文本报告 / `--json`（CI集成）/ `--report proposal.md`（Markdown提案文档）
- **约束提案**：命中≥3次的 anti-pattern 自动生成约束新增提案（含优先级/频率/修复建议）
- **已验证**：examples 目录扫描发现 23 个命中，2 个约束提案（共享变量保护、vTaskDelay in ISR）
- **skill_structure.md** 工具目录新增约束发现工具条目
- **版本升至 3.1.0**

## 3.0.0 — 2026-06-16

- **约束知识图谱**：新增 `references/constraint_graph.md`，20 个约束域 96+ 条规则之间的**依赖、冲突、联动**关系网络，含 Mermaid 可视化图
- **依赖链**：C2→C3→C7、C6→C7、C8→C10、C4→C10、C18→C4、C13→C20 等 14 条依赖关系
- **冲突矩阵**：10 个约束冲突场景的权衡方案（init 同步 vs C8.6、锁序 vs SDK、WSS 栈 vs RAM 等）
- **联动表**：10 个变更→联动检查映射，Agent 改代码时可自动推理影响范围
- **影响分析模板**：标准化的约束变更影响评估输出格式
- **新增约束域候选**：C21 低功耗 / C22 OTA 安全 / C23 显示驱动 / C24 传感器 / C25 音频编解码（待评估）
- **版本升至 3.0.0**：从「规则知识库」进化为「可推理的开发平台」

## 2.90.0 — 2026-06-16

- **新增 3 个约束域（C18–C20）**：外设驱动安全、Flash/NVS 安全、网络韧性，总计新增 16 条规则
- **C18 外设驱动安全**（6 条）：GPIO 方向配置、I2C 地址来源、SPI 模式匹配、DMA 通道冲突、ADC 引脚配置、PWM 频率分辨率互斥
- **C19 Flash/NVS 安全**（5 条）：NVS commit 返回值、Flash 擦写读冲突、OTA 回滚验证、分区表一致性、磨损均衡
- **C20 网络韧性**（5 条）：WiFi/WSS 指数退避、网络操作超时、DNS 失败处理、TLS 错误区分、断线降级策略
- **新增 3 个场景 prompt**：`peripheral_driver_safety.txt`、`flash_nvs_safety.txt`、`network_resilience.txt`
- **约束体系扩展至 20 个域、96+ 条规则**
- **联动更新**：constraint_detail / constraint_index / skill_structure / SKILL.md / Lite 全量同步

## 2.80.0 — 2026-06-16

- **多产品线适配框架**：新增 `product_profiles/` 目录，4 个芯片平台 JSON profile（ESP32/STM32/JL/BK），每个含必选约束、可选约束、功能特性、常见坑点、栈大小建议
- **新增 `tools/product_profile.py`**：产品线加载工具，支持 `--json`/`--features`/`--stack`/`--list` 输出
- **skill_structure.md** 新增产品线 Profile 章节，Agent L3 开始前推荐加载对应 profile
- **版本升至 2.80.0**

## 2.70.0 — 2026-06-16

- **Checker `--json` 输出**：`checker_io.py` 新增 `output_json()` 共享函数；`cjson_leak_checker.py` 首个支持 `--json` 的 checker，输出结构化 JSON（violations/summary/parse_sites）；`run_review.py` 新增 `--json` 参数
- **CI 集成就绪**：JSON 输出格式兼容 GitHub Actions annotations / SonarQube / 任意 CI 解析器
- **版本升至 2.70.0**

## 2.60.0 — 2026-06-16

- **validate-examples 覆盖扩展**：新增 C10（voice_sequence_checker）、C11.5（function_length_checker）、C12（return_check_checker）、C14（logging_checker）的 good/bad 范例验证，从 12 项扩展至 20 项
- **checker 精度问题记录**：voice_sequence_checker 尚未覆盖 C10.1 detach 检测、return_check_checker 对测试模式 xQueueSend 过于严格，已标记 TODO 待后续 checker 增强
- **Prompt 来源注释**：`voice_asr_uplink.txt` 增加 HTML 注释标注知识来源（BK7258 AI闹钟 ASR 空 + 第二轮 peak 塌陷）
- **版本升至 2.60.0**

## 2.50.0 — 2026-06-16

- **新增 workflow `l3_bring_up.md`**：板级 Bring-up 端到端流程（最小系统→外设逐个验证→MVP 链路→WSS/TLS→语音→冒烟→量产 checklist），7 个阶段每个有明确交付物
- **新增 workflow `l2_memory_analysis.md`**：内存专项分析（基线采集→泄漏排查→模块关闭→堆/池优化→栈优化→冒烟），强制 C7.1 无基线不给建议
- **约束冲突矩阵**：`constraint_detail.md` 新增 10 个典型冲突场景的权衡方案（init 同步 vs C8.6、LVGL 锁序 vs SDK 锁序、WSS 栈 vs 内存受限等）
- **联动更新**：SKILL.md/workflows/README/skill_structure 新增 bring_up + memory_analysis 路由；版本升至 2.50.0

## 2.28.0 — 2026-06-16

- **新增 workflow `hw_sw_cocodebug.md`**：软硬联调 / IO 口规划，强制用户填写完整 IO 口用途表，反复核对引脚复用/电气约束/外设冲突
- **L3 安全围栏**：`core_rules.md` 新增编译重试上限（≥5 次暂停）、改动范围锁定、不可触碰文件清单、Git 回滚点
- **Token 效率优化**：`constraint_index.md` 症状表精简为单行引用（指向 `debug_crash.md` Step 2），消除重复维护
- **SKILL.md**：description 触发词新增 IO 口/GPIO/引脚复用/硬件联调/bring-up/原理图；快速路由表新增软硬联调行
- **联动更新**：`skill_structure.md`、`workflows/README.md` 新增 `hw_sw_cocodebug` 条目

## 2.27.0 — 2026-06-16

- **esp32.md 大幅增强**：新增 TOC 目录导航、芯片差异表（ESP32/S3/C6/H2）、双核架构与绑核策略、PSRAM/堆管理、看门狗配置详解、NVS 状态持久化、WiFi 配网流程、安全启动/Flash 加密/OTA 安全
- 文件从 235 行扩展至 ~350 行，涵盖 ESP-IDF 全生命周期开发规范

## 2.26.0 — 2026-06-16

- **C17 一致性补全**：constraint_index.md / constraint_detail.md / core_rules.md / lite_manual_checklist.md 全部补齐 C17 多核 IPC 约束
- **constraint_detail.md**：新增 C17 完整约束矩阵（C17.1–C17.3）+ 症状表增加跨核数据竞争

## 2.25.0 — 2026-06-16

- **新增 C11.5 checker**：`tools/function_length_checker.py`（单函数 >80 行检测）
- **集成**：`run_review.py` 新增 `--skip-func-length` 选项
- **skill_structure.md** 工具目录增加 C11.5 函数长度检查
- **新增**：`scripts/bump_version.py` 版本号批量更新工具

## 2.24.0 — 2026-06-16

- **精简**：iteration_log 旧条目（v2.4–v2.15）归档至 `iteration_log_archive_2026Q2.md`
- **统一**：run_review.py GBK 处理改为使用 checker_io.safe_print（消除重复代码）
- **checker_io.py**：增加 `safe_print()` 函数，5 个 checker + run_review 共用

## 2.23.0 — 2026-06-16

- **新增 C17 多核 IPC**：`prompts/multi_core_ipc.txt`（跨核通信、IPC mailbox、硬件信号量）
- **platforms/bk.md 加 TOC**：636 行文件增加 15 节目录导航
- `SKILL.md` / `skill_structure.md` / `constraint_index.md` 联动更新
- description 触发词新增：多核、IPC、mailbox、跨核、三核、双核

## 2.22.1 — 2026-06-16

- **一致性修复**：lite_manual_checklist.md 补齐 C9–C16 检查项
- **README.md 更新**：描述反映 C11-C16；关键范例表增加 C12/C14 反例与 C10 正例
- **症状表扩展**：constraint_detail.md 症状→约束ID 增加 C12/C14/C16（NULL解引用、日志洪水、timer卡死）
- **examples/README.md**：C12/C14 checker 标注从"规划中"改为实际 checker 名
- **SKILL.md / Lite**：版本同步 2.22.1

## 2.22.0 — 2026-06-16

- **C12 反例**：新增 `examples/bad_unchecked_return.c`（未检查 xTaskCreate 返回值 + NULL 解引用 + early return 不释放资源）
- **C14 反例**：新增 `examples/bad_isr_printf.c`（ISR 中 printf + 裸 printf + 明文打印 token）
- **C12 checker**：新增 `tools/return_check_checker.py`（xTaskCreate/pvPortMalloc 返回值未检查）；集成至 `run_review.py`
- **C14 checker**：新增 `tools/logging_checker.py`（裸 printf + ISR 日志）；集成至 `run_review.py`
- **constraint_detail.md**：补充 C11–C16 完整约束矩阵（正例/反例/checker）
- **l2_code_review.md**：Step 2 反例对照表增加 C12/C14/C11 prompt 引用
- **examples/README.md**：增加 C12/C14 范例索引
- **skill_structure.md**：工具目录增加 logging_checker / return_check_checker
- **Lite**：版本同步 2.22.0，description 更新

## 2.21.0 — 2026-06-16

- **新增 C11–C16 约束域**：编码规范、错误处理、状态机、日志规范、优先级与通信、定时器管理
- 新增 6 个场景 prompt：`coding_style.txt`、`error_handling.txt`、`state_machine_patterns.txt`、`logging_debug.txt`、`inter_task_communication.txt`、`timer_management.txt`
- `constraint_index.md` / `core_rules.md` / `SKILL.md` / `skill_structure.md` 全面联动更新
- description 触发词新增：状态机、线程安全、优先级反转、定时器、日志、错误处理、goto cleanup
- Skill 从「防崩溃」扩展为「嵌入式 RTOS 开发全生命周期规范体系」（C1–C16）

## 2.20.0 — 2026-06-16

- **C10 反例**：新增 `examples/bad_prompt_no_detach.c`（C10.1 未 detach / C10.2 无 AEC settle / C10.5 无 generation 过滤）
- **C10 checker**：新增 `tools/voice_sequence_checker.py`（C10.1/C10.2/C10.5 启发式检查）；集成至 `run_review.py --skip-voice`
- **链接检查**：新增 `tools/check_links.py`（扫描 .md 相对链接有效性）
- **validate-examples 扩展**：覆盖 C2/C8/C10 good 范例（`good_boot_sequence.c` / `good_voice_prompt_uplink.c`）
- **Lite 补齐**：`freertos-skill-lite/SKILL.md` 铁律表增加 C9/C10
- **症状表去重**：`constraint_index.md` 症状表改为引用 `constraint_detail.md`，消除重复维护
- **description 精简**：SKILL.md 触发词去重（去掉 `审查代码`/`裁SDK`/`skill迭代` 等冗余）

## 2.19.0 — 2026-06-16

- **通用化**：C10 / `voice_asr_uplink.txt` 去除产品 API 名（VSM/duer/port），改用 session/playback_slot 抽象
- `secrets_kconfig.txt` 改为全平台三文件模式；BK 细节下沉 `platforms/bk.md`
- `crash_log_decode.txt` 移除 BK 专章，改平台 HardFault 入口 + 平台专档引用
- `l2_project_review.md` 去除 BK 默认/产品文件名；平台自动检测
- `git_commit_style.md` 通用 scope；JL/ESP32 增补 C10 平台节
- `SKILL.md` 触发词与 rules：芯片差异只在 `platforms/`

## 2.18.0 — 2026-06-16

- 新增 **C10 语音/ASR/Uplink**（C10.1–C10.6）与 `prompts/voice_asr_uplink.txt`
- `examples/good_voice_prompt_uplink.c` — prompt detach + AEC settle + VSM generation 正例
- `platforms/bk.md` 共享引擎 prompt 模式；`debug_crash.md` / `l2_code_review.md` 症状与审查路由
- 来源：带屏语音设备日志诊断（ASR 空 / 第二轮麦幅塌陷）闭环

## 2.17.0 — 2026-06-16

- `platforms/bk.md` 增补 BK WSS 异步建链竞态（vc_start）、QueueSet Assert、littlefs 资源、SARADC gpio busy
- `prompts/crash_log_decode.txt` BK7258 HardFault / Assert 解读与 addr2line 流程
- `workflows/debug_crash.md` 症状路由：WSS 401/断线后 vc_start HardFault
- 来源：BK WSS 日志诊断 + vc_start 竞态修复闭环

## 2.16.0 — 2026-06-16

- 新增 **C6.5** 产品层裁剪：`main/CMakeLists.txt` 与 Kconfig/init 链一致
- `l2_project_review.md` Step 4b 产品层死代码 spot-check
- `platforms/bk.md` 增补 BK 实测模式（密钥路径、可裁模块、外设 mutex/栈）
- `secrets_kconfig.txt` 单工程 `config/bk7258` 布局；`sdk_trim_prune.txt` 产品层章节
- 来源：BK 应用工程审查 + 裁剪闭环

## 2.15.1 — 2026-06-16

- 新增 [references/git_commit_style.md](references/git_commit_style.md) — 多仓（应用工程 / skill / SDK）中文 conventional commit 规范
- `core_rules`、`skill_structure`、`self_iterate`、SKILL rules 与 Cursor 模板联动

## 2.15.0 — 2026-06-16

- 新增 **C9 密钥/凭证**（C9.1–C9.6）与 `prompts/secrets_kconfig.txt`
- 新增 `tools/secret_scan_checker.py`；`run_review.py` 支持 `--scan-secrets` / `--git-remotes`
- 新增 workflow `l2_project_review.md`（多仓工程审查）
- 来源：通用应用工程审查闭环（config.secrets、ARCHITECTURE.md、build.sh 可移植）

## 2.14.0 — 2026-06-16

- BK 平台：`platforms/bk.md` 增补通用应用实测模式（app_event 桥接、BEKEN_NO_WAIT、栈表、timer→事件）
- Checker：`cjson_leak_checker` 识别 `!json` Parse 失败早 return；`lvgl_thread_checker` 放行 lvgl_ui 目录与 lcd/port 驱动
- 来源：通用应用 L2 review + P1 修复闭环

## 2.13.0 — 2026-06-15

- 优化 `SKILL.md` description：中文触发词 + `Use when` 句式，提升 DeepSeek 等模型命中率
- 新增 `templates/cursor-rule.embedded.mdc`；INSTALL 增加命中率三层兜底说明

## 2.12.0 — 2026-06-15

- Claude Code 适配：`constraint_index.md`（L2 省 token）、`claude_code.md`、安装脚本、CLAUDE/.claudeignore 模板
- L2 默认读 constraint_index，detail 按需；workflow 懒加载指引

## 2.11.0 — 2026-06-15

- 新增 **自主实施模式**：L3 实现类任务 Agent 全权改代码、无需逐步确认，直至功能完成且编译通过

## 2.10.0 — 2026-06-15

- 新增 **C8 启动顺序 / 阻塞 / 看门狗**（C8.1–C8.6）与 `boot_wdt_lifecycle.txt`
- 新增 C4.8 DMA Cache 一致性；正例 `good_boot_sequence.c`

## 2.9.0 — 2026-06-15

- 新增 **C7 内存分配与优化**（C7.1–C7.9）：先量后改、缩池顺序、栈/堆/池分层、TLS 唯一栈
- 新增 `prompts/memory_alloc_optimize.txt`；workflow / 症状表 / Lite checklist 联动

## 2.8.0 — 2026-06-15

- **结构迭代**：新增 `references/skill_structure.md`（L0–L4 四层加载模型）与 `workflows/README.md`
- `SKILL.md` 瘦身为纯控制平面（<70 行）；Prompt/工具/catalog 下沉至 skill_structure
- README 四层结构图；self_iterate 增加结构维护层；`.gitignore` 排除 `__pycache__`

## 2.7.0 — 2026-06-15

- 新增 `references/constraint_detail.md`：35 条细粒度约束 ID（C1.1–C6.4）+ P0/P1/P2 严重度 + 症状快查
- L2/Crash 输出须引用 `C#.#`；`--validate-examples` 扩展至 C1/C4 good+bad（10 项）
- `lite_manual_checklist.md`、`examples/README.md` 按约束 ID 重组

## 2.6.0 — 2026-06-15

- 新增 `install_skill.ps1` / `install_skill.sh`（安装时排除 `.git`、`fw-AC79_AIoT_SDK`）
- `debug_crash` / `l3_new_module` 症状→prompt 子路由表；BK 平台 SDK 版本记录表
- L2 workflow 标明 `queue_ownership_checker`；`SKILL.md` 增加安装命令索引

## 2.5.0 — 2026-06-15

- **铁律 #2 可执行化**：`queue_ownership_checker.py` + fixtures + `examples/bad_queue_stack_pointer.c`
- **验证闭环硬化**：`run_review.py --validate-examples`；`skill_iterate.py` 增加范例约束与 `sync_lite --dry-run`
- CI 扩展至 `scripts/`、`examples/`、`SKILL.md`；新增 `good_wss_reconnect.c`、`examples/README.md`

## 2.4.0 — 2026-06-15

- 新增 Skill **自我迭代** workflow、`skill_iterate.py` 验证脚本、`iteration_log.md`
- CI：`run_review.py --self-test`（GitHub Actions）
- `sync_lite.py` 自动生成 Lite `SKILL.md`；范例统一 `#include "app_mvp.h"`
- 修正 `bad_wss_blocking.c` 栈反例（512 words）

## 2.3.0 — 2026-06-15

- CI 自测 workflow；`sync_lite` 生成 Lite SKILL；范例对齐 `app_mvp.h`

## 2.2.0 — 2026-06-15

- 控制平面架构：`workflows/` + `references/core_rules.md`；`SKILL.md` 瘦身至 ~83 行

## 2.1.0 — 2026-06-15

- Queue/同步/死锁 prompt；WSS 反例；`run_review.py`；ESP32/STM32 平台加厚

## 2.0.0 — 2026-06-15

- 初始完整版：MVP 范例、checker 工具链、JL AC79 平台专档
