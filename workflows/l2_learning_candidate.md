# L2: Learning Candidate — 经验闭环

> 从 evidence store 中挖掘模式，生成 skill 更新候选提案。
> 候选只能生成报告，不能默认修改 SKILL/checker/prompt。

## 触发条件

- 用户要求"分析最近运行记录"、"挖掘改进机会"
- 定期（每周/每月）自动运行 pattern mining
- 托管运行累积 ≥10 条 evidence 后

## 步骤

### 1. 查询 Evidence Store

```bash
python tools/evidence_store.py query --since 30 --json
```

### 2. 挖掘模式

```bash
python tools/pattern_miner.py --store .codex/evidence/store.jsonl --report pattern_report.md
```

### 3. 审查候选

阅读 `pattern_report.md`，关注：
- 高频失败的 checker（precision 问题）
- 重复出现的 fix_type（应新增 checker）
- 门禁频繁拒绝的原因（preset/job 配置优化）

### 4. 确认操作

对每个候选，决定：
- **批准**：实施 proposed_action（修改 checker/preset/constraint）
- **拒绝**：标记为 rejected，记录原因
- **延期**：保持 proposed，等更多 evidence

### 5. 实施批准的候选

⚠️ 修改 skill 本体必须：
1. 走 `codex_supervisor.py run --policy release_strict`
2. 通过 `forward_tests/run_forward_tests.py`
3. 通过 `skill_iterate.py --check`

### 6. 记录

在 `references/iteration_log.md` 追加学习记录。

## 输出格式

每个候选符合 `learning_candidate.schema.json`。
