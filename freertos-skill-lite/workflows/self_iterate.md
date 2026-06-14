# Workflow: Skill 自我迭代 / 维护

**触发：** 更新 skill、SDK 实测新发现、checker 误报/漏报、量产踩坑反哺、用户反馈规则过时、版本发布。

<thinking>
1. 明确迭代**来源**与**影响范围**（单文件最小改动）
2. 改哪一层：SKILL / workflow / reference / prompt / platform / example / tool（见 [skill_structure.md](../references/skill_structure.md)「改哪一层」）
3. 改完必须走验证闭环，禁止只改文档不验证
</thinking>

## Step 1 — 记录迭代来源

在 [iteration_log.md](../references/iteration_log.md) 追加一条（模板见该文件）：

| 字段 | 说明 |
|------|------|
| 日期 | YYYY-MM-DD |
| 来源 | 用户反馈 / SDK 升级 / CI 失败 / 量产 issue / 架构 review |
| 平台 | esp32 / stm32 / jl / bk / 通用 |
| 变更层 | prompt / platform / tool / workflow / example |

## Step 2 — 影响分析与最小改动

| 变更类型 | 改哪里 | 同步要求 |
|----------|--------|----------|
| **Skill 结构** | `references/skill_structure.md`、`workflows/README.md` | 更新 README.md；SKILL 保持 <100 行 |
| 铁律 / 优先级 | `references/core_rules.md` | 细粒度 ID → `references/constraint_detail.md` |
| 平台事实 | `platforms/xxx.md` | JL/BK 标注 SDK tag |
| 场景专链 | `prompts/xxx.txt` | 检查 workflow 是否引用 |
| 编排步骤 | `workflows/xxx.md` | 检查 SKILL 路由表 |
| 范例 / 类型 | `examples/`、`app_mvp.h` | 对齐 mvp_codegen |
| Checker 规则 | `tools/*.py` | **必须**更新 fixtures |
| 控制平面 | `SKILL.md` | 保持 <100 行；路由不膨胀 |
| Lite 分发 | 运行 `sync_lite.py` | 禁止手改 Lite 正文 |

**禁止：** 未经问卷扩 SDK 固定删除清单；拆成多个 skill；把 12 个 prompt 塞进 `SKILL.md`。

## Step 3 — 版本与 CHANGELOG

1. 更新 `SKILL.md` frontmatter `version:`（semver：patch=文案/typo，minor=新 prompt/workflow，major=架构重构）
2. 在 [CHANGELOG.md](../CHANGELOG.md) 顶部追加版本条目
3. 若改 `skill_lite_body.md` 或完整版 SKILL 路由 → 运行 sync 生成 Lite `SKILL.md`

## Step 4 — 验证闭环（Lite）

1. 更新 [iteration_log.md](../references/iteration_log.md) 与 [CHANGELOG.md](../CHANGELOG.md)
2. 在完整版仓库运行 `python scripts/sync_lite.py`
3. 完成 [lite_manual_checklist.md](../references/lite_manual_checklist.md)（含铁律 #2 Queue 所有权项）

## Step 5 — 输出

```markdown
## 迭代摘要
- 来源 / 平台 / 影响文件

## 变更清单
- file: 改动一句话

## 验证
- [ ] run_review --self-test
- [ ] run_review --validate-examples
- [ ] skill_iterate --check
- [ ] sync_lite
- [ ] CHANGELOG + iteration_log

## 新版本
x.y.z
```
