# Changelog

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
