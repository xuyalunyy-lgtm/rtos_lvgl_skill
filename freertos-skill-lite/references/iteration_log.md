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
