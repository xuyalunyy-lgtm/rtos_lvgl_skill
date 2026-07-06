# log symptom allowlist governance

## 允许列表变更审批路径

1. 在 `references/log_symptom_route_conflict_allowlist.json` 中提交变更前，先在 PR 描述里说明：
   - 变更条目的 `fixture` 或 `route_id` 来源
   - 对应冲突的复现证据（日志/路由或可复现脚本）
   - 预计清理计划与失效日期
2. 通过 `python scripts/check_log_symptom_quality_gate.py --strict` 验证规则不会被放大到非预期范围。
3. 在代码评审中单独列出：
   - 这是“新增/移除 allowlist 条目”变更
   - 该变更是一次性豁免，且附带回收条件

## 快速治理规则

- `scripts/check_log_symptom_quality_gate.py` 会在每次运行时记录 allowlist 与 policy 的 `md5 + mtime`。
- 与 `HEAD` 对比发现仅格式化或语义不变时会返回失败（语义 noop 拒绝），用于防止“空白改动”进入仓库。
- 若 `allowlist` 或 `policy` 文件被修改，建议在评审中同步更新上述审计记录（原因、归档时间、Owner）。