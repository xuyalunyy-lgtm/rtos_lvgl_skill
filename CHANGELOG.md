# Changelog

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
