# Skill 迭代日志（自我迭代记录）

Agent 或维护者在 [self_iterate.md](../workflows/self_iterate.md) 闭环结束时追加条目。**最新在上。**

## 条目模板

```markdown
### YYYY-MM-DD — 简短标题

- **来源：** 用户反馈 / SDK 升级 / CI / 量产 / 架构 review
- **平台：** esp32 | stm32 | jl | bk | 通用
- **变更：** `path/to/file` — 一句话
- **验证：** self-test ✅ / sync_lite ✅
- **版本：** x.y.z
```

---

### 2026-07-01 — v6.0.7 v6 整体重构门禁

- **来源：** v6 路线图：满足 release_governance.md 大版本门禁
- **平台：** 通用
- **变更：** 全量一致性审查（45 约束域 × 248 规则 × 28 checker × 5 平台）；38 个 .md 文件链接全部有效；Lite 版本同步至 6.0.7
- **验证：** self-test ✅ / validate-examples ✅ / check_links ✅ / list-checkers 28 ✅
- **版本：** 6.0.7

### 2026-07-01 — v6.0.6 STM32 平台加厚 + 平台差异矩阵

- **来源：** v6 路线图：补齐 STM32 薄弱点，建立跨平台差异对比
- **平台：** 通用
- **变更：** `platforms/stm32.md` 新增 SDK 全景扫描、内存/Flash 典型值、app_config 关键宏、平台特定 Crash 模式、Flash 加密；新增 `references/platform_diff_matrix.md` 覆盖 5 大平台横向对比
- **验证：** check_links ✅
- **版本：** 6.0.6

### 2026-07-01 — v6.0.5 Checker 覆盖率 50%

- **来源：** v6 路线图：补齐 C15/C32/C39 checker
- **平台：** 通用
- **变更：** 新增 `priority_checker.py`（C15）、`observability_checker.py`（C32）、`config_matrix_checker.py`（C39）+ 6 个 fixtures
- **验证：** self-test ✅ / 总 checker 数 28
- **版本：** 6.0.5

### 2026-07-01 — v6.0.4 模块模板生成器 v2

- **来源：** v6 路线图：从 MVP 骨架升级为完整模块脚手架
- **平台：** 通用
- **变更：** 新增 `tools/module_contract_gen.py`，生成 C29 模块契约头文件 + C30 任务拓扑表 + C13 状态机骨架
- **验证：** self-test 4/4 ✅
- **版本：** 6.0.4

### 2026-07-01 — v6.0.3 Zephyr 平台支持

- **来源：** v6 路线图：从 FreeRTOS 扩展为 RTOS 通用
- **平台：** Zephyr
- **变更：** 新增 `platforms/zephyr.md`（线程/设备/DTS/Kconfig/内存/网络/LVGL/音频/WDT/低功耗/Crash/裁剪/迁移对照表）；新增 `product_profiles/zephyr.json`
- **验证：** check_links ✅
- **版本：** 6.0.3

### 2026-07-01 — v6.0.2 Auto-Fix 引擎 v2

- **来源：** v6 路线图：从建议升级为自动修复
- **平台：** 通用
- **变更：** 增强 `tools/auto_fix_engine.py`，新增 C8 启动顺序、C33 生命周期、C22 OTA 安全的修复模板，覆盖 6 类 checker
- **验证：** self-test 6/6 ✅
- **版本：** 6.0.2

### 2026-07-01 — v6.0.1 约束推理引擎 v2

- **来源：** v6 路线图：推理引擎从 v1 升级到 v2
- **平台：** 通用
- **变更：** 增强 `tools/constraint_inference.py`，新增冲突严重度分级（P0/P1/P2）、修复链优先级标注、约束域名称映射、Mermaid 冲突高亮、`--self-test` 自测
- **验证：** self-test 6/6 ✅
- **版本：** 6.0.1

### 2026-07-01 — v5.0.7 v5 整体重构门禁

- **来源：** v5 路线图：满足 release_governance.md 大版本门禁
- **平台：** 通用
- **变更：** 全量一致性审查（45 约束域 × 248 规则 × 24 checker）；check_links 验证 36 个 .md 文件链接全部有效；Lite 版本同步至 5.0.7；metadata contract 通过；20x 效率证据（13,165x）；v5.0.0 发布里程碑
- **验证：** self-test ✅ / validate-examples ✅ / check_links ✅ / metadata ✅ / efficiency_scorecard ✅
- **版本：** 5.0.7

### 2026-07-01 — v5.0.6 效率度量 + CI/CD PR Gate

- **来源：** v5 路线图：让 20x 目标可量化、让 CI 零门槛接入
- **平台：** 通用
- **变更：** 新增 `tools/efficiency_scorecard.py`（效率度量工具）、`.github/workflows/freertos-review-pr.yml`（CI/CD PR Gate 模板）
- **验证：** 效率度量实测 68 C 文件，人工 25h，自动化 7s，提效 13,000x+
- **版本：** 5.0.6

### 2026-07-01 — v5.0.5 约束推理引擎 v1

- **来源：** v5 路线图：让知识图谱可执行
- **平台：** 通用
- **变更：** 新增 `tools/constraint_inference.py`（约束推理引擎），支持文件变更→约束域推断、约束域→冲突检测+修复链推荐、JSON/Mermaid 输出
- **验证：** C21+C25 推理输出 12 个受影响约束 + 6 个冲突 + 修复链 ✅
- **版本：** 5.0.5

### 2026-07-01 — v5.0.4 Good/Bad Example 补齐（第一批）

- **来源：** v5 路线图：消除「有 bad 无 good」缺口
- **平台：** 通用
- **变更：** 新增 7 个正例：`good_checked_return.c`（C12）、`good_logging.c`（C14）、`good_gpio_config.c`（C18）、`good_nvs_commit.c`（C19）、`good_reconnect_backoff.c`（C20）、`good_sleep_save.c`（C21）、`good_display_init.c`（C23）
- **验证：** examples/README 全部更新 ✅
- **版本：** 5.0.4

### 2026-07-01 — v5.0.3 P0 Checker 批量补齐（第二批）

- **来源：** v5 路线图：补齐 C24/C37/C35 checker
- **平台：** 通用
- **变更：** 新增 `peripheral_shutdown_checker.py`（C24）、`backpressure_checker.py`（C37）、`critical_path_checker.py`（C35）+ 6 个 fixtures
- **验证：** self-test ✅ / 总 checker 数 24
- **版本：** 5.0.3

### 2026-07-01 — v5.0.2 P0 Checker 批量补齐（第一批）

- **来源：** v5 路线图：补齐 C8/C7.3/C33 checker
- **平台：** 通用
- **变更：** 新增 `boot_sequence_checker.py`（C8）、`stack_alloc_checker.py`（C7.3）、`lifecycle_checker.py`（C33）+ 6 个 fixtures
- **验证：** self-test ✅ / 总 checker 数 21
- **版本：** 5.0.2

### 2026-07-01 — v5.0.1 C22 OTA 安全约束域

- **来源：** v5 路线图：补齐 C22 预留域，消除最后一个约束空白
- **平台：** 通用（ESP32/STM32/JL/BK 均适用 OTA）
- **变更：** 新增 `prompts/ota_update_safety.txt`、`tools/ota_safety_checker.py`、`examples/good_ota_update.c`、`examples/bad_ota_no_rollback.c`、`tools/fixtures/good_ota_update.c`、`tools/fixtures/bad_ota_update.c`；C22.1–C22.6 纳入 constraint_index/detail/graph、core_rules、skill_structure、SKILL.md、examples/README、README 与 4 个 product_profiles；checker_registry 接入 ota_safety_checker
- **验证：** self-test ✅ / validate-examples ✅ / ota good ✅ / ota bad ✅
- **版本：** 5.0.1

### 2026-07-01 — v4.17.0 C45 传感器集成契约自动化检查
- **来源：** 延续 20x 提效目标：RTOS 传感器 bring-up 和现场问题常见于 WHO_AM_I 未校验、I2C/SPI 无 timeout、data-ready tight poll、sample 无 timestamp/unit/scale、校准塞进热路径，人工复盘成本高
- **平台：** 通用 RTOS skill 维护 / checker 管线
- **变更：** 新增 C45 传感器集成契约；新增 `tools/sensor_integration_checker.py`、`tools/fixtures/good_sensor_integration.c`、`tools/fixtures/bad_sensor_integration.c`；接入 `checker_registry.py` 默认管线、self-test 与 validate-examples；同步约束索引、详情、核心规则、知识图、运行时契约、工具目录、样本说明、workflow、profiles 与 Lite
- **20x-impact:** 将传感器总线无界等待、身份校验缺失、采样 metadata 缺失和热路径校准从现场日志猜测前移到默认静态扫描，减少 bring-up、漂移和融合链路排查长尾成本
- **验证：** sensor_integration checker good/bad ✅ / run_review --self-test ✅ / run_review --validate-examples ✅ / skill_iterate --check ✅ / commit_audit --strict-release ✅ / check_lite_sync ✅ / check_links ✅ / sync_lite ✅ / 残留扫描 ✅
- **版本：** 4.17.0

### 2026-07-01 — v4.16.0 C44 临界区/关中断预算自动化检查
- **来源：** 延续 20x 提效目标：RTOS 现场的音频爆音、视频掉帧、WDT、周期性延迟尖峰常由长关中断、临界区里做重活、提前 return 未恢复 IRQ 触发，人工定位成本高
- **平台：** 通用 RTOS skill 维护 / checker 管线
- **变更：** 新增 C44 临界区/关中断预算；新增 `tools/critical_section_checker.py`、`tools/fixtures/good_critical_section.c`、`tools/fixtures/bad_critical_section.c`；接入 `checker_registry.py` 默认管线、self-test 与 validate-examples；同步约束索引、详情、核心规则、运行时契约、工具目录、样本说明、workflow、profiles 与 Lite
- **20x-impact:** 将长临界区、关中断重活、busy loop、callback 里关中断和 enter/exit 不对称前移到默认静态扫描，减少实时性问题的现场复盘成本
- **验证：** critical_section checker good/bad ✅ / run_review --self-test ✅ / run_review --validate-examples ✅ / skill_iterate --check ✅ / commit_audit --strict-release ✅ / check_lite_sync ✅ / check_links ✅ / sync_lite ✅ / 残留扫描 ✅
- **版本：** 4.16.0

### 2026-07-01 — v4.15.0 C43 锁预算与优先级反转自动化检查
- **来源：** 延续 20x 提效目标：RTOS 偶发卡死、音视频抖动、网络慢时 UI 卡顿常由无界持锁、持锁阻塞 IO、嵌套锁顺序和热路径拿锁触发，人工 review 成本高
- **平台：** 通用 RTOS skill 维护 / checker 管线
- **变更：** 新增 C43 锁预算与优先级反转防护；新增 `tools/lock_budget_checker.py`、`tools/static_c_scan.py`、`tools/fixtures/good_lock_budget.c`、`tools/fixtures/bad_lock_budget.c`；接入 `checker_registry.py` 默认管线和 self-test；同步约束索引、详情、核心规则、运行时契约、工具目录、样本说明与 Lite
- **20x-impact:** 将锁等待、持锁阻塞 IO、嵌套锁顺序和热路径拿锁从人工通读前移到默认静态扫描，减少死锁/WDT/实时任务抖动排查成本
- **验证：** lock_budget checker good/bad ✅ / run_review --self-test ✅ / run_review --validate-examples ✅ / skill_iterate --check ✅ / commit_audit --strict-release ✅ / check_lite_sync ✅ / check_links ✅ / sync_lite ✅
- **版本：** 4.15.0

### 2026-07-01 — v4.14.1 C36/C37 效率预算自动化检查
- **来源：** 延续 20x 提效目标：将 C35-C42 中最适合自动化的 C36 数据拷贝预算与 C37 背压降级策略转为默认 checker
- **平台：** 通用 RTOS skill 维护 / checker 管线
- **变更：** 新增 `tools/efficiency_budget_checker.py`，覆盖大 payload 入队、缺 copy budget 的热路径 copy、alloc+memcpy 缺满池策略、满队列永久等待、无 backoff 的无限 retry/reconnect loop；新增 `good_efficiency_budget.c` / `bad_efficiency_budget.c` fixtures；`checker_registry.py` 接入 `--skip-efficiency`
- **20x-impact:** 将帧/包/事件路径的拷贝链和背压缺口从人工通读提前到默认静态扫描，减少 RTOS 现场卡顿、内存抖动和队列假死排查成本
- **验证：** efficiency checker good/bad ✅ / run_review --self-test ✅ / skill_iterate --check ✅ / commit_audit --strict-release ✅ / sync_lite ✅ / 残留扫描 ✅
- **版本：** 4.14.1

### 2026-07-01 — v4.14.0 C35-C42 20x 效率约束扩展
- **来源：** 长期目标：不要担心 token、持续迭代；每个较大版本对整体代码进行一次重构；目标提效 20 倍；运行主动审核提交
- **平台：** 通用 RTOS skill 维护 / 全平台
- **变更：** 新增 C35 关键路径预算表、C36 数据拷贝预算、C37 背压与降级策略、C38 故障隔离与自动恢复、C39 配置矩阵约束、C40 一键复现闭环、C41 回归样本优先、C42 板级资源契约；同步 `prompts/runtime_efficiency_contracts.txt`、`references/core_rules.md`、`constraint_index.md`、`constraint_detail.md`、`constraint_graph.md`、`skill_structure.md`、`lite_manual_checklist.md`、workflow 路由、product profiles、README、Lite 分发脚本与 agent metadata
- **whole-skill-refactor:** yes
- **major-refactor:** yes
- **20x-impact:** 将关键路径预算、copy count、背压降级、故障恢复、配置矩阵、复现命令、good/bad 样本、板级资源 owner 前置为统一审查入口，减少 RTOS 现场排查和新人接手的重复劳动
- **验证：** commit_audit --self-test ✅ / commit_audit --strict-release ✅ / skill_iterate --check ✅ / sync_lite ✅ / metadata ✅ / Lite sync ✅ / 残留扫描 ✅
- **版本：** 4.14.0

### 2026-07-01 — v4.13.9 commit audit 自测闭环
- **来源：** 用户目标：持续迭代、每个大版本整体重构、目标提效 20 倍、运行主动审核提交
- **平台：** 通用 skill 维护 / release 流程
- **变更：** `scripts/commit_audit.py` 增加 `--self-test` 坏样本闭环，覆盖版本漂移、大版本缺少整体重构证据、大版本缺少 20x 证据、产品专用残留；未跟踪目录会递归纳入审核。`scripts/skill_iterate.py`、`scripts/sync_lite.py`、`workflows/self_iterate.md`、`references/release_governance.md`、`references/skill_structure.md`、`README.md` 同步接入自测门禁
- **验证：** commit_audit --self-test ✅ / commit_audit --strict-release ✅ / skill_iterate --check ✅ / sync_lite ✅
- **版本：** 4.13.9

### 2026-07-01 — v4.13.8 20x 提效与主动提交审计门禁

- **来源：** 用户目标：不要担心 token、持续迭代；每个大版本对整体代码进行一次重构；目标提效 20 倍；运行主动审核提交
- **平台：** 通用 skill 维护 / release 流程
- **变更：** 新增 `references/release_governance.md`，定义 20x efficiency scorecard、大版本 whole-skill refactor gate 与 proactive commit audit；新增 `scripts/commit_audit.py`，审计最近提交、当前 diff、版本同步、产品专用残留和大版本重构证据；`workflows/self_iterate.md`、`scripts/skill_iterate.py`、`references/skill_structure.md`、`README.md`、`SKILL.md`、`agents/openai.yaml` 同步接入
- **验证：** commit_audit ✅ / skill_iterate --check ✅ / sync_lite ✅
- **版本：** 4.13.8

### 2026-07-01 — v4.13.7 C29-C34 运行时效率约束

- **来源：** 用户确认新增 C29 模块契约、C30 任务/队列拓扑表、C31 超时预算、C32 可观测性优先、C33 生命周期对称、C34 热路径禁区，用于提升通用 RTOS 开发效率
- **平台：** 通用 RTOS（ESP32 / STM32 / JL / BK 均适用）
- **变更：** 新增 `prompts/runtime_efficiency_contracts.txt`；C29-C34 纳入 `references/core_rules.md`、`constraint_index.md`、`constraint_detail.md`、`constraint_graph.md`、`skill_structure.md`、`lite_manual_checklist.md`、workflows 与 product profiles；`blocking_wait_checker.py` 映射 C31 并接入 `tools/checker_registry.py`，新增 `good_timeout_budget.c` / `bad_timeout_budget.c` fixtures，覆盖 RTOS wait 与 socket/TLS 无超时场景
- **验证：** C31 good ✅ / C31 bad ✅ / self-test ✅ / validate-examples ✅ / skill_iterate --check ✅ / sync_lite ✅
- **版本：** 4.13.7

### 2026-07-01 — v4.13.6 通用化门禁与产品残留收敛

- **来源：** 用户反馈：skill 必须是通用 RTOS 开发能力，不应绑定某个特定项目
- **平台：** 通用 + BK 平台文档抽象化
- **变更：** `references/core_rules.md` / `workflows/self_iterate.md` — 新增通用化原则与现场经验入库门禁；`prompts/peripheral_shutdown_safety.txt` — 从打印机专用示例改为通用外设/执行器收尾模板；`platforms/bk.md` / `product_profiles/bk.json` / `prompts/sdk_trim_prune.txt` / `references/git_commit_style.md` — 收敛产品名、业务任务名与固定裁剪暗示；`tools/fixtures/*config_secrets` — 改为通用云端配置 key
- **验证：** self-test ✅ / validate-examples ✅ / architecture sync ✅ / metadata ✅ / sync_lite ✅ / skill_iterate --check ✅
- **版本：** 4.13.6

### 2026-07-01 — v4.13.5 C14 日志管理系统约束

- **来源：** 用户反馈：日志管理需要系统的约束文档
- **平台：** 通用
- **变更：** `references/logging_management_constraints.md` — 新增系统日志约束文档；`constraint_detail.md` / `constraint_index.md` / `core_rules.md` / `constraint_graph.md` — 新增并同步 C14.6–C14.9；`prompts/logging_debug.txt` / `workflows/l2_code_review.md` / `l3_bring_up.md` / `lite_manual_checklist.md` — 增加按需路由与检查项
- **验证：** metadata ✅ / lite sync ✅ / architecture sync ✅ / runtime distribution ✅ / links ✅ / skill_iterate --check ✅ / sync_lite.ps1 dry-run ✅ / compileall ✅ / diff --check ✅
- **版本：** 4.13.5

### 2026-07-01 — v4.13.4 C7 allocator 工程化闭环

- **来源：** 用户指定下一步：统一 allocator 封装 + largest free block/heap kind 遥测 + 固定块池模板
- **平台：** 通用 + ESP32/BK 等多堆/PSRAM 平台
- **变更：** `references/constraint_detail.md` — 新增 C7.11–C7.13；`prompts/memory_alloc_optimize.txt` — 增加 allocator、telemetry、pool 的审查规则；`workflows/l2_memory_analysis.md` — 增加 allocator API、碎片遥测和固定块池模板；`core_rules` / `constraint_index` / `constraint_graph` / `lite_manual_checklist` — 同步索引、联动关系和规则计数
- **验证：** metadata ✅ / lite sync ✅ / architecture sync ✅ / runtime distribution ✅ / links ✅ / skill_iterate --check ✅ / sync_lite.ps1 dry-run ✅ / compileall ✅ / diff --check ✅
- **版本：** 4.13.4

### 2026-07-01 — v4.13.3 C7 外部 RAM 优先分配

- **来源：** 用户现场经验：内存申请时，能使用外部 RAM 就先使用外部 RAM
- **平台：** 通用 + ESP32/BK 等带 PSRAM/SPIRAM/external RAM 平台
- **变更：** `references/constraint_detail.md` — 新增 C7.10；`prompts/memory_alloc_optimize.txt` — 增加外部 RAM 优先策略、fallback 与 matched free 示例；`workflows/l2_memory_analysis.md` — 缩池前先做外部 RAM 分类迁移；`core_rules` / `constraint_index` / `constraint_graph` / `lite_manual_checklist` — 同步索引、冲突关系和规则计数
- **验证：** metadata ✅ / lite sync ✅ / architecture sync ✅ / runtime distribution ✅ / links ✅ / skill_iterate --check ✅ / sync_lite.ps1 dry-run ✅ / compileall ✅ / diff --check ✅
- **版本：** 4.13.3

### 2026-07-01 — v4.13.2 Lite 元数据修复与 Audio/WSS drift audit

- **来源：** 用户复盘建议：先修 Lite frontmatter，再控制现场经验入库门槛，并对 C10/C24/Audio-WSS 做一致性审计
- **平台：** 通用 + bk 音频/WSS 现场联调
- **变更：** `freertos-skill-lite/SKILL.md` — 移除 BOM 并同步 4.13.2 frontmatter；`workflows/self_iterate.md` — 增加现场经验入库门槛与 drift audit；`references/constraint_index.md` / `constraint_detail.md` / `core_rules.md` / `constraint_graph.md` / `lite_manual_checklist.md` — 对齐 C10.5、C24.4 与 Audio/WSS 联动；`workflows/hw_sw_cocodebug.md` / `debug_crash.md` / `l2_code_review.md` / `l2_project_review.md` — 增加 Audio/WSS 联调路由；`agents/openai.yaml` — 强化 Audio/WSS field-debug 默认 prompt
- **验证：** metadata ✅ / metadata self-test ✅ / lite sync ✅ / architecture sync ✅ / runtime distribution ✅ / links ✅ / run_review self-test ✅ / validate-examples ✅ / list-checkers ✅ / skill_iterate --check ✅ / compileall ✅ / diff --check ✅
- **版本：** 4.13.2

### 2026-06-30 — v4.13.1 BK 音频/WSS 现场联调经验泛化

- **来源：** BK7258 AI Palette MIC、TTS 打断、WSS 上行、长 TTS 背压与 MemFault 现场调试
- **平台：** bk + 通用音频/WSS
- **变更：** `SKILL.md` — 增加 Audio/WSS field triage 路由；`prompts/voice_asr_uplink.txt` — 增加半双工共享 voice handle、`CLIENT_INTERRUPT`、TTS generation、首包延迟和 backpressure 判断；`prompts/mbedtls_wss_memory.txt` — 增加 PSRAM/SRAM matched free、FreeRTOS IDLE 延迟崩溃与 reset reason 区分；`prompts/peripheral_shutdown_safety.txt` — 增加音频/媒体 pipeline idle 与 deinit 分层规则
- **验证：** diff --check ✅ / manual review ✅ / metadata check blocked: Lite `SKILL.md` 缺少标准 frontmatter（既有问题）
- **版本：** 4.13.1

### 2026-06-22 — v4.12.5 Lite 工具索引降级审计

- **来源：** 继续迭代；审查发现 Lite 包不携带 `tools/`/`scripts/`，但 Lite `skill_structure.md` 仍展示完整版工具命令表
- **平台：** Lite 分发 + Windows/PowerShell 同步路径
- **变更：** `sync_lite.py` / `sync_lite.ps1` 对 `references/skill_structure.md` 增加 Lite 专用 reference patch：product profile 说明改为人工识别，工具目录改为 `l2_code_review_lite` + `lite_manual_checklist` 等人工替代；`check_lite_sync.py` 增加 runtime docs 泄漏审计，禁止 Lite 工具索引出现 `python tools/`、`python scripts/`、`run_review.py` 等不可运行命令
- **验证：** sync_lite ✅ / sync_lite.ps1 -DryRun ✅ / check_lite_sync ✅ / check_lite_sync --fix clean ✅ / Lite 命令泄漏扫描 ✅ / skill_iterate --check ✅ / quick_validate 完整版+Lite ✅
- **版本：** 4.12.5

### 2026-06-22 — v4.12.4 Skill 元数据审计自测

- **来源：** 用户要求继续迭代；v4.12.3 已把元数据合同纳入自检，本轮补齐脚本自身的正/反例验证
- **平台：** 通用 + Codex/OpenAI skill 分发
- **变更：** `scripts/check_skill_metadata.py` 增加 `--root` 与 `--self-test`，使用临时 skill 夹具覆盖 description 超长、root-level `version`、完整版/Lite 版本漂移、`agents/openai.yaml` 漂移、控制面行数超限；`skill_iterate.py` 与 `skill_iterate.ps1` 第 5 步同步执行当前仓库校验和脚本自测
- **验证：** check_skill_metadata ✅ / check_skill_metadata --self-test ✅ / py_compile ✅ / skill_iterate --check ✅ / skill_iterate.ps1 -SkipSelfTest ✅ / sync_lite ✅ / check_lite_sync ✅ / check_links ✅
- **版本：** 4.12.4

### 2026-06-22 — v4.12.3 Skill 元数据合同审计

- **来源：** 用户要求继续迭代；延续 v4.12.1 description 超限与 v4.12.2 分发审计经验，把 Codex/OpenAI 元数据约束纳入本地自检
- **平台：** 通用 + Codex/OpenAI skill 分发
- **变更：** 新增 `scripts/check_skill_metadata.py`，校验完整版/Lite `SKILL.md` 的 name、`metadata.version`、semver、description 长度与 `Use when` 触发词、控制面行数，以及 `agents/openai.yaml` 必需 interface 字段和 Lite 同步一致性；`skill_iterate.py` 与 `skill_iterate.ps1` 接入第 5 步 metadata contract；压缩完整版 `SKILL.md` 入口说明，使控制面恢复 `<100 行`
- **验证：** check_skill_metadata ✅ / py_compile ✅ / skill_iterate --check ✅ / skill_iterate.ps1 -SkipSelfTest ✅ / sync_lite ✅ / sync_lite.ps1 dry-run ✅ / check_lite_sync ✅ / check_links ✅ / quick_validate 完整版+Lite ✅
- **版本：** 4.12.3

### 2026-06-22 — v4.12.2 运行时分发边界审计

- **来源：** 用户要求继续迭代一个版本；延续 v4.12.1 “源码仓可以重、安装包必须轻”的分发边界，补上可执行审计护栏
- **平台：** 通用 + Cursor / Claude Code / Codex 分发
- **变更：** 新增 `scripts/check_runtime_distribution.py`，模拟 `install_multi_ide.py` runtime payload，审计根目录维护文档/CI/编辑器目录/Lite 产物/缓存/本地 SDK 不进入安装包；检查 `.sh`/`.ps1` 安装脚本保留运行时索引；校验 Lite 必需文件与禁止 `tools/`、`examples/`；`skill_iterate.py` 与 `skill_iterate.ps1` 接入第 4 步分发审计；`sync_lite.py` / `sync_lite.ps1` 支持同一 workflow 多段 patch，Lite 自迭代输出清单改为 manual checklist
- **验证：** check_runtime_distribution ✅ / py_compile ✅ / skill_iterate --check ✅ / skill_iterate.ps1 -SkipSelfTest ✅ / sync_lite dry-run ✅ / sync_lite.ps1 dry-run ✅ / check_lite_sync ✅ / check_links ✅ / quick_validate 完整版+Lite ✅
- **版本：** 4.12.2

### 2026-06-22 — v4.12.1 分发边界与 Codex 元数据收敛

- **来源：** 用户要求落实“源码仓可以重、安装包必须轻”的双轨分发计划，并修复 Codex quick_validate description 超限问题
- **平台：** 通用 + 带屏音视频产品
- **变更：** 压缩 `SKILL.md` description 至 1024 字符内；新增 `agents/openai.yaml`；安装脚本排除根目录 README/INSTALL/CHANGELOG、CI/编辑器目录、Lite 产物、缓存和本地 SDK，同时保留运行时索引文件；`sync_lite` 与 `check_lite_sync` 纳入 agents 元数据；低功耗边界统一为仅审查/校验用户方案；自迭代脚本固定 Python UTF-8 环境
- **验证：** description 654 chars ✅ / quick_validate 完整版+Lite ✅ / check_lite_sync ✅ / check_links ✅ / py_compile ✅ / sync_lite dry-run ✅ / run_review self-test ✅ / validate-examples ✅ / list-checkers ✅ / skill_iterate --check ✅
- **版本：** 4.12.1

### 2026-06-22 — v4.12.0 新增 C28 媒体 DMA/cache/零拷贝 buffer 生命周期

- **来源：** 用户要求继续迭代；延续 C25-C27 音视频方向，补齐 DMA/cache 一致性、零拷贝帧池生命周期和旧帧/花屏/爆音类量产问题
- **平台：** 通用 + ESP32/JL/BK/STM32 带屏音视频产品
- **变更：** 新增 `prompts/av_dma_buffer_lifecycle.txt`、`tools/av_dma_buffer_checker.py`、`examples/good_av_dma_buffer_lifecycle.c`、`examples/bad_av_dma_buffer_lifecycle.c`；C28（C28.1–C28.6）纳入 core_rules、constraint_index/detail/graph、skill_structure、workflow、Lite checklist 与 product_profiles；checker registry 增加 `--skip-av-dma` 与 C28 validate examples；PowerShell 自迭代脚本补充 `--list-checkers` 探针
- **验证：** C28 good ✅ / C28 bad ✅ / validate-examples ✅ / self-test ✅ / list-checkers ✅ / checker registry audit ✅ / check_lite_sync ✅ / check_links ✅ / skill_iterate --check ✅ / compileall ✅ / json ✅
- **版本：** 4.12.0

### 2026-06-18 — v4.11.0 checker 管线注册表化大重构

- **来源：** 用户要求整体优化并做一次大的重构；维护 C25-C27 后发现 `run_review.py` checker 接入、skip 参数与 examples 验证重复分散
- **平台：** 通用
- **变更：** 新增 `tools/checker_registry.py` 作为 checker 管线唯一注册表；`tools/run_review.py` 改为数据驱动执行、自动生成 `--skip-*` 参数并新增 `--list-checkers`；batch checker 统一使用过滤后的文件列表，修复 `--dir` 模式绕过 `bad_*.c` 过滤的问题；`scripts/skill_iterate.py --check` 增加 registry 审计
- **验证：** self-test ✅ / validate-examples ✅ / list-checkers ✅ / checker registry audit ✅ / check_lite_sync ✅ / check_links ✅ / skill_iterate --check ✅ / compileall ✅
- **版本：** 4.11.0

### 2026-06-18 — v4.10.0 新增 C27 音视频时钟漂移 / Jitter Buffer

- **来源：** 继续强化音视频方向，补齐 C25/C26 之后的长时间稳定同步、网络抖动恢复与现场遥测问题面
- **平台：** 通用 + ESP32/JL/BK 带屏音视频产品
- **变更：** 新增 `prompts/av_clock_jitter.txt`、`tools/av_clock_jitter_checker.py`、`examples/good_av_clock_jitter.c`、`examples/bad_av_clock_jitter.c`；C27（C27.1–C27.6）纳入 core_rules、constraint_index/detail/graph、skill_structure、workflow、Lite checklist 与 product_profiles；`run_review.py` 增加 `--skip-av-clock` 和 C27 validate examples；checker 收紧系统 tick 检测，仅在 tick 被赋给 PTS/timestamp 时判定媒体时钟违规
- **验证：** C27 good ✅ / C27 bad ✅ / validate-examples ✅ / self-test ✅ / check_lite_sync ✅ / check_links ✅ / skill_iterate --check ✅ / py_compile ✅ / json ✅
- **版本：** 4.10.0

### 2026-06-18 — v4.9.0 新增 C26 编解码 / 媒体格式一致性

- **来源：** 继续强化音视频方向，补齐 sample rate / frame size / pixel stride / codec 生命周期类量产问题
- **平台：** 通用 + ESP32/JL/BK 带屏音视频产品
- **变更：** 新增 `prompts/av_codec_format.txt`、`tools/media_format_checker.py`、`examples/good_media_format_contract.c`、`examples/bad_media_format_mismatch.c`；C26（C26.1–C26.6）纳入 core_rules、constraint_index/detail/graph、skill_structure、workflow、Lite checklist 与 product_profiles；`run_review.py` 增加 `--skip-media-format` 和 C26 validate examples
- **验证：** C26 good ✅ / C26 bad ✅ / validate-examples ✅ / self-test ✅ / check_lite_sync ✅ / check_links ✅ / skill_iterate --check ✅ / py_compile ✅
- **版本：** 4.9.0

### 2026-06-18 — v4.8.0 新增 C25 音视频管线 / A/V Sync

- **来源：** 用户要求“着重往音视频方向优化”
- **平台：** 通用 + ESP32/JL/BK 带屏音视频产品
- **变更：** 新增 `prompts/av_pipeline_sync.txt`、`tools/av_pipeline_checker.py`、`examples/good_av_pipeline_sync.c`、`examples/bad_av_pipeline_blocking.c`；C25（C25.1–C25.6）纳入 core_rules、constraint_index/detail/graph、skill_structure、debug_crash、l3_new_module、Lite checklist 与 product_profiles；`run_review.py` 增加 `--skip-av` 和 C25 validate examples
- **验证：** C25 good ✅ / C25 bad ✅ / validate-examples ✅ / self-test ✅ / check_lite_sync ✅ / check_links ✅ / skill_iterate --check ✅
- **版本：** 4.8.0

### 2026-06-18 — v4.7.3 增强 C10 语音时序 checker

- **来源：** 自检发现 `run_review.py --validate-examples` 中 C10 bad 反例因 checker 覆盖不足被注释
- **平台：** 通用
- **变更：** `tools/voice_sequence_checker.py` 剥离注释并按函数路径检查 stop / FINISHED detach；按函数内顺序检查 `audio_start_uplink` / `session_begin_capture` 前的 AEC settle / mic ready；`examples/bad_prompt_no_detach.c` 使用真实 `audio_start_uplink` 调用；`tools/run_review.py` 重新启用 C10 bad 反例验证
- **验证：** quick_validate ✅ / C10 good ✅ / C10 bad ✅ / self-test ✅ / validate-examples ✅ / check_lite_sync ✅ / sync_lite.py dry-run ✅ / sync_lite.ps1 dry-run ✅ / py_compile ✅
- **版本：** 4.7.3

### 2026-06-18 — v4.7.2 修复 Lite workflow 同步硬闸

- **来源：** 本地审查发现 `sync_lite.ps1 -DryRun` 对过期 workflow patch 只警告不失败，Lite 版仍保留完整版工具依赖
- **平台：** 通用
- **变更：** `scripts/sync_lite.py` / `scripts/sync_lite.ps1` 在必需 workflow patch 匹配失败时直接失败；`scripts/check_lite_sync.py` 复用同步转换逻辑比对 workflow 内容；更新 `scripts/lite_patches/` 中 `debug_crash.md` 与 `l3_new_module.md` 的正则和替换块；生成的 Lite workflow 改为编译闭环 + 人工 checklist，不依赖 `tools/`、`examples/`、`mvp_codegen`、`run_review`
- **验证：** quick_validate ✅ / self-test ✅ / validate-examples ✅ / check_lite_sync ✅ / sync_lite.py dry-run ✅ / sync_lite.ps1 dry-run ✅ / py_compile ✅
- **版本：** 4.7.2

### 2026-06-18 — v4.7.1 修复 C3 checker 与 L3 规则污染

- **来源：** 用户要求将 skill 迭代到优秀水平；本地自检发现 C3 checker 漏报
- **平台：** 通用
- **变更：** `tools/cjson_leak_checker.py` 补齐 CLI 入口并增强函数/变量/退出路径追踪；新增 `--dir` 目录扫描；`SKILL.md` frontmatter 迁移为标准 `metadata.version`；`references/core_rules.md` 移除残留工具调用片段并收敛 L3 自主实施规则；`scripts/check_lite_sync.py` 识别 Lite examples 链接转换且自动修复统一写 LF；C3 prompt/workflow 命令同步更新
- **验证：** self-test ✅ / validate-examples ✅ / py_compile ✅ / sync_lite ✅
- **版本：** 4.7.1

### 2026-06-18 — v4.7.0 新增 3 个 Checker（C13/C14.4/C16）

- **来源：** 补充 Checker 覆盖率
- **平台：** 通用
- **变更：** 新增 `state_machine_checker.py`（C13.1/C13.3）、`log_desensitize_checker.py`（C14.4）、`timer_checker.py`（C16.1/C16.2）；constraint_detail.md 更新 checker 引用；skill_structure.md 工具目录补齐；constraint_graph.md 统计表 Checker 数从 16 更新为 19
- **验证：** 待 CI
- **版本：** 4.7.0

### 2026-06-18 — v4.6.1 Checker 脚本质量审查与修复

- **来源：** 6 个新增 checker 脚本逻辑正确性审查
- **平台：** 通用
- **变更：**
  - `network_resilience_checker.py`：C20.2 超时检查从空操作改为实际检测（SO_RCVTIMEO/数值/常量超时）；C20.1 退避状态机改为函数级花括号计数；recv/send/connect 使用词边界正则
  - `blocking_wait_checker.py`：移除 xSemaphoreCreateMutex/xSemaphoreCreateBinary（创建 API 非阻塞 API）；改用词边界正则匹配；函数上下文检测扩展更多签名
  - `display_driver_checker.py`：C23.6 补充 draw_buf 缺失报告
  - `peripheral_driver_checker.py`：C18.1 添加 gpio_set_direction 检测
  - `low_power_checker.py`：C21.4 POWER_DOWN_INDICATORS 收窄为明确断电函数
  - `flash_nvs_checker.py`：C19.1 添加 ESP_ERROR_CHECK/ESP_RETURN_ON_ERROR 宏识别
- **验证：** 待 CI
- **版本：** 4.6.1

### 2026-06-18 — v4.6.0 七项改进（测试例外/修复顺序/硬件收尾/队列提醒/永久等待/提交保护/Lite同步）

- **来源：** 用户反馈 7 项改进建议
- **平台：** 通用
- **变更：**
  1. core_rules.md 新增「测试阶段例外机制」（C9/C14/C5/C7 降级）
  2. l2_project_review.md 输出模板改为「优先修复顺序」（P0→P1→P2→P3）
  3. 新增 C24 外设关闭安全约束（C24.1–C24.5）+ `peripheral_shutdown_safety.txt`
  4. queue_event_bus.txt 新增「队列满/丢事件处理原则」
  5. 新增 `blocking_wait_checker.py`（永久等待扫描）
  6. git_commit_style.md 新增「提交前状态保护」规则
  7. 新增 `scripts/check_lite_sync.py`（Lite 同步检查）
- **验证：** 待 CI
- **版本：** 4.6.0

### 2026-06-18 — v4.5.0 新增 5 个 Examples 范例（C18-C23）

- **来源：** 约束体系质量审查建议「新增 Examples 范例」
- **平台：** 通用
- **变更：** 新增 `bad_gpio_no_config.c`（C18.1/C18.2/C18.4）、`bad_nvs_no_commit.c`（C19.1/C21.1）、`bad_reconnect_no_backoff.c`（C20.1/C20.2）、`bad_sleep_no_save.c`（C21.1/C21.2/C21.4）、`bad_display_no_init.c`（C23.1/C23.5/C23.6）；每个反例包含正例对照；examples/README.md 补齐 C18-C23 索引
- **验证：** 待 CI
- **版本：** 4.5.0

### 2026-06-18 — v4.4.0 新增 5 个自动化 Checker（C18-C23）

- **来源：** 约束体系质量审查建议「新增自动化 Checker」
- **平台：** 通用
- **变更：** 新增 `peripheral_driver_checker.py`（C18.1/C18.2/C18.4）、`flash_nvs_checker.py`（C19.1）、`network_resilience_checker.py`（C20.1/C20.2）、`low_power_checker.py`（C21.1/C21.4）、`display_driver_checker.py`（C23.5/C23.6）；constraint_detail.md 约束矩阵验证列更新；skill_structure.md 工具目录补齐；constraint_graph.md 统计表 Checker 数从 10 更新为 15
- **验证：** 待 CI
- **版本：** 4.4.0

### 2026-06-18 — v4.3.1 约束体系质量审查与一致性修复

- **来源：** 约束体系质量审查（22 域/120 条规则全面扫描）
- **平台：** 通用
- **变更：** 修复 10 个一致性问题：SKILL.md/core_rules.md 补齐 C18/C19/C20 铁律索引（Q1）；全链路统一约束数量为 22 域/120 条/P0=43/P1=54/P2=23（Q2-Q5）；core_rules.md C6 子约束数修正为 5、C16 补填 3、引用范围改为 C1.1-C23.6（Q6-Q8）；Lite 版本全面同步
- **验证：** 链接有效性 ✅ / 场景表完整性 ✅
- **版本：** 4.3.1

### 2026-06-18 — v4.3.0 C23 显示驱动安全正式集成

- **来源：** V3 路线图「C23 候选域转正」
- **平台：** 通用
- **变更：** `lcd_display_driver.txt`（C23.1–C23.6）从候选域升级为正式约束域；constraint_index.md / constraint_detail.md / core_rules.md / SKILL.md / skill_structure.md / constraint_graph.md 全链路同步；Lite 版本同步更新；SKILL.md description 新增显示/LCD/背光/帧率/撕裂等触发词
- **验证：** self-test 待 CI
- **版本：** 4.3.0

### 2026-06-18 — v4.2.0 C21 低功耗管理正式集成

- **来源：** V3 路线图「C21 候选域转正」
- **平台：** 通用
- **变更：** `low_power_management.txt`（C21.1–C21.5）从候选域升级为正式约束域；constraint_index.md / constraint_detail.md / core_rules.md / SKILL.md / skill_structure.md / constraint_graph.md 全链路同步；core_rules.md C17 链接 bug 修复；SKILL.md description 新增低功耗触发词
- **验证：** self-test 待 CI
- **版本：** 4.2.0

### 2026-06-16 — v3.2.0 LVGL 单页面生成 workflow

- **来源：** 用户反馈（LVGL 页面生成需要哪些信息）
- **平台：** 通用
- **变更：** 新增 `workflows/l3_lvgl_page.md`：定义 LVGL 页面生成所需 8 项信息清单（屏幕参数/字体/图片/颜色主题/样式/数据绑定/组件规格/动画）；信息不完整时拒绝生成；LVGL v8 vs v9 API 差异表；代码生成模板 + 主题模板 + MVP 联动检查 + 内存估算
- **验证：** self-test 待 CI
- **版本：** 3.2.0

### 2026-06-16 — v3.1.0 自动约束发现工具

- **来源：** V3 路线图「自动约束发现」
- **平台：** 通用
- **变更：** 新增 `tools/constraint_discovery.py`（14 条发现规则，覆盖栈溢出/竞态/整数溢出/资源泄漏/FreeRTOS特定/平台特定/代码质量）；支持 `--json` / `--report` 输出；自动约束提案（≥3 次命中）；`skill_structure.md` 工具目录新增
- **验证：** examples 目录扫描通过（23 命中，2 提案）
- **版本：** 3.1.0

### 2026-06-16 — v3.0.0 约束知识图谱（从规则库进化为可推理平台）

- **来源：** V3.0 路线图里程碑
- **平台：** 通用
- **变更：** 新增 `references/constraint_graph.md`：20 个约束域 96+ 条规则的依赖/冲突/联动关系网络（14 条依赖链 + 10 个冲突权衡 + 10 个联动映射）；Mermaid 可视化图；影响分析模板；5 个新增约束域候选（C21-C25）
- **验证：** self-test 待 CI
- **版本：** 3.0.0

### 2026-06-16 — v2.90.0 新增 3 个约束域（C18 外设驱动 / C19 Flash NVS / C20 网络韧性）

- **来源：** 官方文档 API 注意事项 + 量产踩坑经验
- **平台：** 通用
- **变更：** 新增 `prompts/peripheral_driver_safety.txt`（C18.1–C18.6）；`prompts/flash_nvs_safety.txt`（C19.1–C19.5）；`prompts/network_resilience.txt`（C20.1–C20.5）；constraint_detail.md / constraint_index.md / skill_structure.md 全量同步
- **验证：** self-test 待 CI
- **版本：** 2.90.0

### 2026-06-16 — v2.80.0 多产品线适配框架

- **来源：** Skill 审查优化建议（V2.80 路线图）
- **平台：** 通用（ESP32/STM32/JL/BK）
- **变更：** 新增 `product_profiles/` 目录含 4 个芯片平台 JSON profile；`tools/product_profile.py` 加载工具（--json/--features/--stack/--list）；`skill_structure.md` 新增产品线 Profile 章节
- **验证：** self-test 待 CI
- **版本：** 2.80.0

### 2026-06-16 — v2.70.0 Checker --json 输出（CI 集成）

- **来源：** Skill 审查优化建议（V2.70 路线图）
- **平台：** 通用
- **变更：** `tools/checker_io.py` 新增 `output_json()` 共享函数；`tools/cjson_leak_checker.py` 首个支持 `--json` 输出（violations/summary/parse_sites）；`tools/run_review.py` 新增 `--json` 参数
- **验证：** self-test 待 CI
- **版本：** 2.70.0

### 2026-06-16 — v2.60.0 validate-examples 扩展 + Prompt 来源注释

- **来源：** Skill 审查优化建议（V2.60 路线图）
- **平台：** 通用
- **变更：** `tools/run_review.py` validate-examples 从 12 项扩展至 20 项（新增 C10 voice_sequence / C11.5 function_length / C12 return_check / C14 logging）；`prompts/voice_asr_uplink.txt` 增加 HTML 来源注释；标记 2 个 checker 精度 TODO
- **验证：** validate-examples 通过（2 项 checker 待增强已标记 TODO）
- **版本：** 2.60.0

### 2026-06-16 — v2.50.0 Bring-up + 内存分析 workflow + 约束冲突矩阵

- **来源：** Skill 审查优化建议（V2.50 路线图）
- **平台：** 通用
- **变更：** `workflows/l3_bring_up.md`（7 阶段端到端 bring-up：最小系统→外设逐个验证→MVP 链路→WSS→语音→冒烟→量产 checklist）；`workflows/l2_memory_analysis.md`（6 步内存专项：基线采集→泄漏排查→模块关闭→堆/池优化→栈优化→冒烟）；`constraint_detail.md` 新增 10 个约束冲突场景权衡矩阵；SKILL.md/workflows/README/skill_structure 联动更新
- **验证：** self-test 待 CI
- **版本：** 2.50.0

### 2026-06-16 — v2.28.0 软硬联调 workflow + L3 安全围栏 + Token 优化

- **来源：** Skill 审查优化建议
- **平台：** 通用
- **变更：** `workflows/hw_sw_cocodebug.md`（IO 口收集→平台核对→board_io.h 生成→反复核对）；`core_rules.md` L3 安全围栏（编译重试上限/改动范围锁定/不可触碰清单/回滚点）；`constraint_index.md` 症状表精简为单行引用；SKILL.md 触发词+路由新增软硬联调
- **验证：** self-test 待 CI
- **版本：** 2.28.0

### 2026-06-16 — v2.23.0 新增 C17 多核 IPC + bk.md TOC

- **来源：** Skill 审查优化建议
- **平台：** 通用 + BK
- **变更：** `prompts/multi_core_ipc.txt`（C17.1–C17.3）；`platforms/bk.md` 加 15 节目录导航；SKILL.md / skill_structure.md / constraint_index.md / Lite 联动更新
- **验证：** self-test ✅ / check_links ✅
- **版本：** 2.23.0

### 2026-06-16 — v2.22.1 一致性修复（Lite checklist / README / 症状表）

- **来源：** Skill 回归审查
- **平台：** 通用
- **变更：** `lite_manual_checklist.md` 补齐 C9–C16；`README.md` 更新描述与范例；`constraint_detail.md` 症状表扩展 C12/C14/C16；`examples/README.md` 去"规划中"
- **验证：** self-test ✅ / check_links ✅
- **版本：** 2.22.1

### 2026-06-16 — v2.22.0 C11-C16 约束矩阵 + 新 checker + 反例

- **来源：** Skill 审查优化建议（P0+P1 补缺）
- **平台：** 通用
- **变更：** `constraint_detail.md` 补充 C11–C16 完整矩阵；`return_check_checker.py`（C12）；`logging_checker.py`（C14）；`bad_unchecked_return.c` + `bad_isr_printf.c` 反例；`l2_code_review.md` / `examples/README.md` / `skill_structure.md` 联动；`run_review.py` 串联新 checker
- **验证：** self-test ✅ / validate-examples ✅ / check_links ✅
- **版本：** 2.22.0

### 2026-06-16 — v2.21.0 新增 C11–C16 开发规范体系

- **来源：** Skill 审查优化建议（嵌入式 RTOS 全生命周期规范）
- **平台：** 通用
- **变更：** 新增 C11 编码规范 / C12 错误处理 / C13 状态机 / C14 日志规范 / C15 优先级与通信 / C16 定时器管理；6 个 prompt；constraint_index / core_rules / SKILL.md / skill_structure 全面联动
- **验证：** self-test ✅ / validate-examples ✅ / check_links ✅
- **版本：** 2.21.0

### 2026-06-16 — v2.20.0 C10 checker + 链接检查 + 覆盖扩展

- **来源：** Skill 审查优化建议
- **平台：** 通用
- **变更：** `voice_sequence_checker.py`；`check_links.py`；`bad_prompt_no_detach.c`；validate-examples 扩展至 C8/C10；Lite 补齐 C9/C10；症状表去重；description 精简
- **验证：** self-test ✅ / validate-examples ✅ / check_links ✅
- **版本：** 2.20.0

### 2026-06-16 — v2.19.0 Skill 通用化（平台/产品分层）

- **来源：** 用户要求 skill 通用化（除芯片特性外全部审查）
- **平台：** 通用 + JL/ESP32/BK 平台节补 C10
- **变更：** C10/voice prompt/example 抽象化；secrets/crash/l2_project/SKILL/git_commit 去产品绑定
- **验证：** skill_iterate --check --sync ✅
- **版本：** 2.19.0

### 2026-06-16 — v2.18.0 C10 语音 ASR / uplink 共享引擎

- **来源：** 日志诊断（唤醒叮后 ASR 空、第二轮 mic peak 塌陷）+ prompt_tone / VSM 修复闭环
- **平台：** 通用（BK AVDK 多 port 为参考实现）
- **变更：** C10.1–C10.6；`voice_asr_uplink.txt`；`good_voice_prompt_uplink.c`；`bk.md` prompt 节；debug/l2 路由
- **验证：** self-test ✅ / sync_lite ✅ / skill_iterate --check ✅
- **版本：** 2.18.0

### 2026-06-16 — v2.17.0 bk_printer vc_start 竞态与 crash 日志反哺

- **来源：** 日志诊断 + vc_start / voicechat 生命周期修复（bk_printer BK7258）
- **平台：** bk
- **变更：** `platforms/bk.md` WSS 竞态/littlefs emoji/SARADC；`crash_log_decode.txt` BK HardFault；`debug_crash.md` 症状路由
- **验证：** self-test / sync_lite（待 CI）
- **版本：** 2.17.0

### 2026-06-16 — v2.16.0 bk_printer 审查反哺 C6.5 产品层裁剪

- **来源：** 架构 review + 裁剪落地（bk_printer BK7258 AI 打印机）
- **平台：** bk
- **变更：** C6.5；`l2_project_review.md` Step 4b；`platforms/bk.md` 打印机实测；`secrets_kconfig` 单工程布局；`sdk_trim_prune` 产品层章节
- **验证：** self-test / sync_lite（待 CI）
- **版本：** 2.16.0

> v2.4.0 – v2.15.1 的历史条目已归档至 [iteration_log_archive_2026Q2.md](iteration_log_archive_2026Q2.md)。
