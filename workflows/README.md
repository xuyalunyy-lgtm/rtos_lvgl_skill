# 工作流索引

控制入口：[SKILL.md](../SKILL.md) · 结构说明：[skill_structure.md](../references/skill_structure.md)

先加载一个工作流，再按需加载它引用的 prompts、references 和 platform 文档。

## 审查域（L2）

| 文件 | 触发条件 |
|------|----------|
| [l2_code_review.md](l2_code_review.md) | 代码审查 / 审计 |
| [l2_code_review_lite.md](l2_code_review_lite.md) | 轻量手动审查 |
| [l2_project_review.md](l2_project_review.md) | 项目/工作区审查 |
| [l2_memory_analysis.md](l2_memory_analysis.md) | 内存分析 / 泄漏 |
| [hw_sw_cocodebug.md](hw_sw_cocodebug.md) | 软硬件协同调试 / GPIO 冲突 |

## 调试域（L2-L3）

| 文件 | 触发条件 |
|------|----------|
| [debug_crash.md](debug_crash.md) | HardFault / WDT / 死锁 / 死机 |

## 生成域（L3）

| 文件 | 触发条件 |
|------|----------|
| [l3_lvgl_page.md](l3_lvgl_page.md) | LVGL 页面 / manifest 生成 |
| [l3_lvgl_page_quick.md](l3_lvgl_page_quick.md) | LVGL 快速页面生成 |
| [l3_new_module.md](l3_new_module.md) | 新模块 / 多任务 MVP |
| [l3_bring_up.md](l3_bring_up.md) | 板级启动 / 外设验证 |
| [l3_sdk_trim.md](l3_sdk_trim.md) | SDK 裁剪 |

应用域（manifest / 多页脚手架）由 `l3_lvgl_page.md` 覆盖，在目标固件工程中实现。

## 已归档工作流

| 文件 | 状态 |
|------|------|
| [l2_architecture_review.md](../archive/workflows/l2_architecture_review.md) | v31 归档 |
| [l2_auto_repair.md](../archive/workflows/l2_auto_repair.md) | v31 归档 |
| [self_iterate.md](../archive/workflows/self_iterate.md) | v31 归档 |

## 标准加载顺序

1. `references/core_rules.md`
2. `references/constraint_index.md`；仅在需要时加载 `constraint_detail.md`
3. 一个相关平台文档 `platforms/xxx.md`
4. 选定工作流引用的 prompts
5. `tools/run_review.py` 和示例（完整验证时）

## 架构同步检查

```bash
python scripts/check_architecture_sync.py
```
