# Changelog

最近 3 个版本。完整历史见 [archive/CHANGELOG_FULL.md](archive/CHANGELOG_FULL.md)。

## 45.0.0 - 2026-07-11

v45: 内置 LVGL v9 headless runner 与图片转 LVGL 闭环。
- UI 自动化工具链曾收口为 6 个面向模型的高层工具，并修复 render/apply/self-test 契约。
- 新增 Windows x64 与 Linux x64 runner CI、完整性 manifest 和端到端渲染 smoke test。
- 新增 asset.pack 协议、RGB565A8 Alpha 支持，以及原生 runner 图片资源加载。
- 随包提交 Windows x64 与 Linux x64 runner；12 个 golden page 已用原生 renderer 重建为权威基线。
- 发布门禁改为重编码 UI Spec、调用 runner，并逐像素和原生对象树比对基线（12/12）。

## 44.0.0 - 2026-07-04

v44: Module Boundary Contract - high cohesion / low coupling as first-class C29 rules.
- C29 extends module contracts with responsibility, public API, dependencies, forbidden dependencies, event boundaries, and owned resources.
- L3 new-module flow now requires a module boundary table before codegen.
- Codegen contract and manifest validation add module boundary fields when C29 is covered.
- Added `module_boundary_checker.py` for god-module, cross-layer include/call, and shared global context signals.
- Added good/bad module-boundary examples and checker fixtures.

## 43.0.0 - 2026-07-03

v43: 工程验证探针版 — 命中后输出最小验证探针，先确认根因再建议修复。
- symptom 输出新增 routing_decision/diagnostic_probes/checker_targets/log_signals/stop_conditions
- 10 个高频症状补充验证探针（日志确认/代码定位/工具验证）
- 弱匹配时 routing_decision=ask_more，不加载大 shard
- 新增 --probe-detail compact|full 和 --allow-weak-route

## 42.0.0 - 2026-07-03

v42: 工程问题指纹路由版 — 自然语言症状自动匹配 workflow + C 号 + 候选根因。
- context_router.py 新增 --symptom-text 和 --symptom-file
- log_symptom_routes.json 增强：15 个症状 + 中英文自然说法 + verify_steps + missing_facts
- 症状命中后自动加载微分片，联动 v41
- 输出 matched_symptoms/likely_constraints/top_hypotheses/verify_steps/missing_facts
- 42.0.1: 修复平台推断 — Zephyr kernel oops 自动路由到 zephyr 平台
- 42.0.2: 扩展中文自然语言别名 — 堆一直掉/花屏/升级后回滚/偶发重启
- 42.0.3: 置信度分层 — strong/medium/weak，低置信只给 missing_facts
