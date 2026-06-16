# Workflow 索引

> 控制平面入口：[SKILL.md](../SKILL.md) · 结构说明：[skill_structure.md](../references/skill_structure.md)

选定 **1 个** workflow 后按 Step 顺序执行；prompt 仅加载该 workflow 指定项。

| 文件 | 级别 | 触发 |
|------|------|------|
| [l2_code_review.md](l2_code_review.md) | L2 | review / audit / 审查 C 代码 |
| [l2_code_review_lite.md](l2_code_review_lite.md) | L2 | Lite 人工审查 |
| [l2_project_review.md](l2_project_review.md) | L2 | 工程/工作区/量产前审计 |
| [debug_crash.md](debug_crash.md) | L2–L3 | HardFault / 死机 / WDT / frozen |
| [l3_sdk_trim.md](l3_sdk_trim.md) | L3 | SDK 改造 / 需求驱动裁剪 |
| [l3_new_module.md](l3_new_module.md) | L3 | 新模块 / 多任务 / MVP 设计 |
| [hw_sw_cocodebug.md](hw_sw_cocodebug.md) | L2 | 硬件联调 / IO 口分配 / GPIO 冲突 / bring-up |
| [l3_bring_up.md](l3_bring_up.md) | L3 | 板级 bring-up / 最小系统 / 外设逐个验证 / 量产闭环 |
| [l2_memory_analysis.md](l2_memory_analysis.md) | L2 | 内存专项分析 / 基线采集 / 泄漏排查 / 缩池缩栈 |
| [self_iterate.md](self_iterate.md) | L3 | Skill 维护 / 自我迭代 |

## 标准加载顺序（L2+）

1. `references/core_rules.md`
2. `references/constraint_index.md`（**默认**；完整矩阵见 `constraint_detail.md`）
3. `platforms/xxx.md`（1 个）
4. workflow 指定的 1–3 个 `prompts/*.txt`
5. 完整版：`tools/run_review.py`；范例 **Grep/Read 单文件**，勿批量读 examples/

**Claude Code 省 token** → [claude_code.md](../references/claude_code.md)
