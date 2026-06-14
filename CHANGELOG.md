# Changelog

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
