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
| Checker 规则 | `tools/*.py` + `tools/checker_registry.py` | **必须**更新 fixtures / validate-examples case |
| 控制平面 | `SKILL.md` + `agents/openai.yaml` | 保持 <100 行；路由不膨胀；UI 元数据同步 |
| Lite 分发 | 运行 `sync_lite.py` | 禁止手改 Lite 正文 |

### 现场经验入库门槛

| 判断 | 行动 |
|------|------|
| 能归入现有约束和 prompt | 只追加到对应 `prompts/xxx.txt`，并补 checklist / 症状路由 |
| 改变 C#.# 规则边界或严重度 | 同步 `core_rules`、`constraint_index`、`constraint_detail`、Lite checklist |
| 需要自动化识别 | 更新 checker + registry + good/bad example，再跑 validate-examples |
| 只是一次项目现场日志 | 先写 `iteration_log.md`，不要新建 prompt |
| 无法归类且会反复触发 | 才新增 prompt，并在 workflow 中限制加载场景 |

每次新增现场经验，至少做一次 drift audit：`prompt -> constraint_index/detail -> workflow 路由 -> checker/example -> Lite checklist`。缺任一层时，在迭代摘要里标注“人工覆盖”或补齐。

### 通用化门禁

真实项目只能作为经验来源，运行时 skill 必须保持产品中立：

| 允许 | 禁止 |
|------|------|
| 平台/芯片/SDK 事实：如 BK7258、ESP32-S3、STM32H7、AC79、Armino、ESP-IDF | 产品名、客户名、仓库名、内部模块名直接进入通用 workflow/prompt |
| 抽象后的模式：WSS 异步建链、共享音频 backend、外设 stop/deinit 竞态 | 具体产品名、仓库名、云服务 key、业务文件名作为规则前提 |
| 通用代码示例：`device_*`、`peripheral_*`、`session_*`、`media_*` | 只能在某个产品成立的函数名/任务名作为标准模板 |
| 平台专档中的 SDK API/编译命令 | 把单项目裁剪清单当成默认删除清单 |

若现场经验来自特定产品，先写入 `iteration_log.md` 的来源；进入 prompt / workflow / profile 前必须改写为“症状 → 通用根因 → 通用修复模式”。确需保留产品名时，只能放在归档日志或平台专档的“来源”句中，不得影响触发、约束或默认实现。

**禁止：** 未经问卷扩 SDK 固定删除清单；拆成多个 skill；把 12 个 prompt 塞进 `SKILL.md`；把单个产品的目录/任务/密钥命名当作通用规范。

## Step 3 — 版本与 CHANGELOG

1. 更新 `SKILL.md` frontmatter `metadata.version`（semver：patch=文案/typo，minor=新 prompt/workflow，major=架构重构）
2. 在 [CHANGELOG.md](../CHANGELOG.md) 顶部追加版本条目
3. 若改 `skill_lite_body.md` 或完整版 SKILL 路由 → 运行 sync 生成 Lite `SKILL.md`
4. 若本次含 git commit → 遵循 [git_commit_style.md](../references/git_commit_style.md)（先 `git log` 对齐目标仓）

## Step 4 — 验证闭环（完整版）

```bash
python tools/run_review.py --self-test
python tools/run_review.py --validate-examples
python tools/run_review.py --list-checkers
python scripts/check_runtime_distribution.py
python scripts/check_skill_metadata.py
python scripts/check_skill_metadata.py --self-test
python scripts/skill_iterate.py --check
python scripts/sync_lite.py
# Windows PowerShell: $env:PYTHONUTF8='1'; python <skill-creator>\scripts\quick_validate.py .
# bash/zsh: PYTHONUTF8=1 python <skill-creator>/scripts/quick_validate.py .
# Windows: .\scripts\skill_iterate.cmd -Sync
```

| 检查项 | 通过标准 |
|--------|----------|
| fixtures 自测 | exit 0 |
| **铁律范例约束** | `--validate-examples` exit 0 |
| checker registry | `skill_iterate.py --check` 内置审计通过 |
| runtime distribution | `check_runtime_distribution.py` exit 0，安装包边界未回退 |
| skill metadata | `check_skill_metadata.py` 与 `--self-test` exit 0，description / version / openai.yaml 未漂移且脚本坏样本可检出 |
| SKILL version | frontmatter 含 `metadata.version` |
| Lite 同步 | `freertos-skill-lite/SKILL.md` 版本与完整版一致 |
| sync dry-run | `sync_lite.py --dry-run` exit 0 |
| Codex quick validate | `PYTHONUTF8=1` 下 quick_validate exit 0 |
| iteration_log | 本次变更有记录 |

Python 不可用：人工执行 [lite_manual_checklist.md](../references/lite_manual_checklist.md) 等价项，标注「待本地补验」。

## Step 5 — 输出

```markdown
## 迭代摘要
- 来源 / 平台 / 影响文件

## 变更清单
- file: 改动一句话

## 验证
- [ ] run_review --self-test
- [ ] run_review --validate-examples
- [ ] check_runtime_distribution
- [ ] check_skill_metadata
- [ ] skill_iterate --check
- [ ] sync_lite
- [ ] CHANGELOG + iteration_log

## 新版本
x.y.z
```
