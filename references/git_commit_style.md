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
| **提交前** | `git status` + `git diff`；**禁止**提交 secret、`.env`、`*.secrets`、调试日志 |
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
| `ci` | CI/CD 专用 |

### scope 取值（通用）

用**模块目录或子系统名**，小写，与**目标仓库** `git log` 历史一致。常见示例：

| scope 类型 | 示例 |
|------------|------|
| 音频 | `audio`、`capture`、`prompt` |
| 网络 | `network`、`wss`、`mqtt` |
| UI | `ui`、`lvgl`、`board` |
| 工程 | `build`、`ci`、`config` |
| SDK 组件 | SDK 仓内组件目录名 |

```bash
git commit -m "$(cat <<'EOF'
fix(audio): prompt 结束后 detach 播放路径，修复第二轮 ASR 空识别

- stop 与 FINISHED 双路径 detach
- 开 uplink 前增加 AEC settle
EOF
)"
```

---

## skill 仓（FreeRTOS Embedded Architect Skill）

**模式：** `feat: Skill vX.Y.Z — 中文简述`（版本发布 / 较大迭代）

| 字段 | 说明 |
|------|------|
| 版本 | 与 `SKILL.md` frontmatter `metadata.version` 一致 |
| 分隔 | 中文破折号 `—` |
| patch | 文案/小修可用 `docs:` / `fix:` + 简短中文 |

```bash
git commit -m "$(cat <<'EOF'
feat: Skill v2.19.0 — 通用化 C10 语音约束与平台分层
EOF
)"
```

**skill 维护提交后：** 若改完整版且版本 bump → 运行 `python scripts/sync_lite.py`。

---

## 提交前状态保护（多仓/嵌套仓库）

| 规则 | 说明 |
|------|------|
| **只提交相关文件** | `git add` 仅当前任务修改的文件，禁止 `git add .` 或 `git add -A` |
| **列出未提交的脏文件** | 提交前 `git status` 输出未暂存文件，说明为何不提交 |
| **构建生成文件不纳入** | `build/`、`*.o`、`*.bin`、`gen_files_list.txt` 等禁止提交 |
| **嵌套仓库分别检查** | 若有 submodule 或嵌套 git 仓库（如 `projects/app/`），每个仓库单独 `git status` |
| **分离关注点** | 不同功能的改动分开提交，一个 commit 只做一件事 |

```bash
# 提交前检查示例
git status                    # 查看所有改动
git diff --cached             # 查看已暂存内容
git diff                      # 查看未暂存内容

# 嵌套仓库检查
cd projects/app && git status
cd ../../skill && git status
```

**禁止**一次提交包含不相关改动（如同时改 audio + ui + config）。

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
