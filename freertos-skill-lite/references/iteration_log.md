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
