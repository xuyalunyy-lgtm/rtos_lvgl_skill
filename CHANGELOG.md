# Changelog

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
- 来源：带屏 AI 闹钟日志诊断（ASR 空 / 第二轮麦幅塌陷）闭环

## 2.17.0 — 2026-06-16

- `platforms/bk.md` 增补 bk_printer WSS 异步建链竞态（vc_start）、QueueSet Assert、littlefs 表情资源、SARADC gpio busy
- `prompts/crash_log_decode.txt` BK7258 HardFault / Assert 解读与 addr2line 流程
- `workflows/debug_crash.md` 症状路由：WSS 401/断线后 vc_start HardFault
- 来源：bk_printer 日志诊断 + vc_start 竞态修复闭环

## 2.16.0 — 2026-06-16

- 新增 **C6.5** 产品层裁剪：`main/CMakeLists.txt` 与 Kconfig/init 链一致
- `l2_project_review.md` Step 4b 产品层死代码 spot-check
- `platforms/bk.md` 增补 bk_printer 实测（密钥路径、可裁模块、打印 mutex/栈）
- `secrets_kconfig.txt` 单工程 `config/bk7258` 布局；`sdk_trim_prune.txt` 产品层章节
- 来源：AI 打印机工程审查 + 裁剪闭环

## 2.15.1 — 2026-06-16

- 新增 [references/git_commit_style.md](references/git_commit_style.md) — 多仓（AIAlarmClock / skill / SDK）中文 conventional commit 规范
- `core_rules`、`skill_structure`、`self_iterate`、SKILL rules 与 Cursor 模板联动

## 2.15.0 — 2026-06-16

- 新增 **C9 密钥/凭证**（C9.1–C9.6）与 `prompts/secrets_kconfig.txt`
- 新增 `tools/secret_scan_checker.py`；`run_review.py` 支持 `--scan-secrets` / `--git-remotes`
- 新增 workflow `l2_project_review.md`（多仓工程审查）
- 来源：AIAlarmClock 工程审查闭环（config.secrets、ARCHITECTURE.md、build.sh 可移植）

## 2.14.0 — 2026-06-16

- BK 平台：`platforms/bk.md` 增补 AIAlarmClock 实测模式（app_event 桥接、BEKEN_NO_WAIT、栈表、timer→事件）
- Checker：`cjson_leak_checker` 识别 `!json` Parse 失败早 return；`lvgl_thread_checker` 放行 lvgl_ui 目录与 lcd/port 驱动
- 来源：AIAlarmClock L2 review + P1 修复闭环

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
