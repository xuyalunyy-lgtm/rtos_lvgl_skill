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

### 2026-06-15 — v2.12.0 Claude Code 省 token 适配

- **来源：** 用户反馈（Claude Code 适配、保能力省 token）
- **平台：** 通用
- **变更：** `constraint_index.md`、`claude_code.md`、`templates/`、`install_claude_code.*`、workflow/L2 懒加载
- **验证：** skill_iterate.cmd -Sync ✅
- **版本：** 2.12.0

### 2026-06-15 — v2.11.0 自主实施模式

- **来源：** 用户反馈（AI 应自主改代码至编译通过，无需逐步确认）
- **平台：** 通用
- **变更：** `core_rules.md` 自主实施模式、`SKILL.md` rules、`l3_new_module.md`、`debug_crash.md`、`skill_lite_body.md`
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.cmd -Sync ✅
- **版本：** 2.11.0

### 2026-06-15 — v2.10.0 启动顺序 / WDT / DMA Cache

- **来源：** 架构 review（嵌入式量产常见 init/WDT/DMA cache 踩坑）
- **平台：** 通用
- **变更：** C8.1–C8.6、`boot_wdt_lifecycle.txt`、C4.8、`good_boot_sequence.c`、workflows/examples
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.cmd -Sync ✅
- **版本：** 2.10.0

### 2026-06-15 — v2.9.0 通用内存分配约束 C7

- **来源：** 用户反馈（内存优化途径需沉淀为 Skill 约束）
- **平台：** 通用
- **变更：** `prompts/memory_alloc_optimize.txt`、`constraint_detail.md` C7.1–C7.9、`core_rules.md`、`SKILL.md` 2.9.0、workflows、Lite checklist
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.cmd -Sync ✅
- **版本：** 2.9.0

### 2026-06-15 — v2.8.0 Skill 四层结构与控制平面瘦身

- **来源：** 用户反馈（主要结构方面）
- **平台：** 通用
- **变更：** `references/skill_structure.md`、`workflows/README.md`、`SKILL.md`、`skill_lite_body.md`、`README.md`、`self_iterate.md`、`.gitignore`
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.cmd -Sync ✅
- **版本：** 2.8.0

### 2026-06-15 — v2.7.0 细粒度约束矩阵 C#.#

- **来源：** 用户反馈（约束需更细节）
- **平台：** 通用
- **变更：** `references/constraint_detail.md`、`core_rules.md`、`SKILL.md`、`l2_code_review.md`、`debug_crash.md`、`run_review.py --validate-examples`、`examples/README.md`、`lite_manual_checklist.md`
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.ps1 -Sync ✅
- **版本：** 2.7.0

### 2026-06-15 — v2.6.0 安装硬化与症状子路由

- **来源：** 用户反馈（安装带入本地 SDK 目录）+ 架构 review
- **平台：** 通用 / bk
- **变更：** `install_skill.ps1/sh`、`debug_crash.md`、`l3_new_module.md`、`platforms/bk.md`、`INSTALL.md`
- **验证：** skill_iterate --check（CI）
- **版本：** 2.6.0

### 2026-06-15 — v2.5.0 铁律 #2 与验证闭环可执行化

- **来源：** 架构 review / 用户反馈
- **平台：** 通用
- **变更：** `queue_ownership_checker.py`、`--validate-examples`、CI 扩展、`bad_queue_stack_pointer.c`、`good_wss_reconnect.c`
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate ✅
- **版本：** 2.5.0

### 2026-06-15 — v2.4.0 自我迭代机制

- **来源：** 架构 review
- **平台：** 通用
- **变更：** 新增 `workflows/self_iterate.md`、`scripts/skill_iterate.py`、`CHANGELOG.md`、本日志
- **验证：** self-test + skill_iterate + sync_lite
- **版本：** 2.4.0
