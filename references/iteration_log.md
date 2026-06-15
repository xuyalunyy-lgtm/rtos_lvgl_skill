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

### 2026-06-15 — v2.4.0 自我迭代机制

- **来源：** 架构 review
- **平台：** 通用
- **变更：** 新增 `workflows/self_iterate.md`、`scripts/skill_iterate.py`、`CHANGELOG.md`、本日志
- **验证：** self-test + skill_iterate + sync_lite
- **版本：** 2.4.0
