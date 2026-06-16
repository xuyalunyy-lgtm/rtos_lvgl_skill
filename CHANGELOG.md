# Changelog

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
