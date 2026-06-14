# Git 提交说明规范（多仓工作区）

Agent **在用户明确要求 commit / 提交** 时读取本文件。提交前须 `git log -8 --oneline` 对齐目标仓库既有风格。

---

## 通用原则

| 规则 | 说明 |
|------|------|
| **语言** | 标题与正文用**中文**（专有名词、Kconfig/API 名可保留英文） |
| **格式** | [Conventional Commits](https://www.conventionalcommits.org/)：`type(scope): 简述` |
| **一行标题** | 标题 ≤ 72 字；祈使语气，不加句号 |
| **正文** | 多文件/跨模块变更时加 2–4 条 `-` 要点（说明 why，非逐文件罗列） |
| **提交前** | `git status` + `git diff`；**禁止**提交 secret、`.env`、`config.secrets`、`日志.md` |
| **amend** | 仅当 HEAD 未 push 且为用户要求改 message 或 hook 自动改文件 |
| **push** | 用户未明确要求时**不 push** |

### type 取值

| type | 用途 |
|------|------|
| `feat` | 新功能、新模块、新 CI |
| `fix` | Bug 修复、崩溃、回归 |
| `chore` | 工具链、脚本、无行为变化的杂项 |
| `docs` | 仅文档 |
| `refactor` | 重构，不改外部行为 |
| `test` | 测试、fixture |
| `ci` | CI/CD 专用（产品仓也可用 `feat(ci)`，见下表） |

`scope` 用**模块目录或子系统名**，小写，与仓库历史一致。

---

## 按仓库约定（armino 工作区实测）

### AIAlarmClock（产品固件）

**模式：** `type(scope): 中文简述`

| 字段 | 示例 |
|------|------|
| scope | `app_event`、`vsm`、`audio_engine`、`board`、`ci`、`duer` |
| 标题 | `fix(vsm): 松键后延迟 heal 直至 uplink 排空，修复云端 ASR 空识别` |
| 标题 | `feat(ci): 新增 GitHub Actions、架构文档与 config.secrets 密钥分离` |

```bash
git commit -m "$(cat <<'EOF'
feat(ci): 新增 GitHub Actions、架构文档与 config.secrets 密钥分离

- 入库 config 清空 CLIENT_SECRET，本地 config.secrets 覆盖构建
- 增加 merge_config_secrets.sh 与 CI 静态审查
EOF
)"
```

**避免：** 纯英文标题 `Add CI, architecture docs...`；无 scope 的 `update files`。

---

### skill（FreeRTOS Embedded Architect Skill）

**模式：** `feat: Skill vX.Y.Z — 中文简述`（版本发布 / 较大迭代）

| 字段 | 说明 |
|------|------|
| 版本 | 与 `SKILL.md` frontmatter `version:` 一致 |
| 分隔 | 中文破折号 `—` |
| patch | 文案/小修可用 `docs:` / `fix:` + 简短中文 |

```bash
git commit -m "$(cat <<'EOF'
feat: Skill v2.15.0 — C9 密钥审查、工程 review workflow 与 lite 同步
EOF
)"
```

**skill 维护提交后：** 若改完整版且版本 bump → 运行 `python scripts/sync_lite.py`。

---

### AIAlarmClockSdk（Armino SDK fork）

**模式：** `type(scope): 中文简述`（可与简短正文）

| scope | `build`、`bk_duer`、`bk_audio_player`、`bk_voice_service` 等 |
|-------|--------------------------------------------------------------|
| 示例 | `fix(build): 去除硬编码工程路径，构建前合并 config.secrets` |
| 示例 | `fix(bk_audio_player): 修复分组设置并增加线程安全性` |

SDK 仓偶见长正文 bullet（历史遗留）；**新提交优先一行标题 + 可选 2–3 条要点**，避免整段英文。

---

## Agent 提交流程（checklist）

1. `git log -8 --oneline` — 确认目标仓库风格
2. `git status` / `git diff` — 范围与敏感文件
3. 按上表起草 **中文** message（HEREDOC 传 `-m`）
4. `git add` 仅相关文件 → `git commit` → `git status` 验证
5. 多仓工作区：**每个 git 根目录单独 commit**，禁止跨仓一个 commit

---

## 反例

```
Add CI and docs                    # 无 type、英文
fix: bug                           # 无 scope、无信息量
feat: update                       # 未说明改了什么
chore: WIP                         # 禁止
fix(build): fixed the build script. # 英文 + 句号
```

---

## 关联

- 密钥不入库 → [secrets_kconfig.txt](../prompts/secrets_kconfig.txt)（C9）
- Skill 版本发布 → [self_iterate.md](../workflows/self_iterate.md) Step 3
- Cursor 用户规则可引用本文件路径
