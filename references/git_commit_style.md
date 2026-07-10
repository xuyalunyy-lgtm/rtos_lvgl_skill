# Git Commit Message Specification (Multi-repo Workspace)

Agent reads this file **when the user explicitly requests a commit**. Before committing, run `git log -8 --oneline` to align with the target repository's existing style.

---

## General Principles

| Rule | Description |
|------|------|
| **Language** | Use **English** for titles and body text (proper nouns, Kconfig/API names may remain in English) |
| **Format** | [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): brief description` |
| **One-line title** | Title ≤ 72 characters; imperative mood, no period at the end |
| **Body** | Add 2–4 `-` bullet points for multi-file/cross-module changes (explain why, not a per-file list) |
| **Before committing** | `git status` + `git diff`; **do not** commit secrets, `.env`, `*.secrets`, or debug logs |
| **amend** | Only when HEAD is not pushed and the user requests message change or hook auto-modifies files |
| **push** | **Do not push** unless the user explicitly requests it |

### type Values

| type | Purpose |
|------|------|
| `feat` | New feature, new module, new CI |
| `fix` | Bug fix, crash, regression |
| `chore` | Toolchain, scripts, miscellaneous with no behavior change |
| `docs` | Documentation only |
| `refactor` | Refactoring, no external behavior change |
| `test` | Tests, fixtures |
| `ci` | CI/CD specific |

### scope Values (General)

Use **module directory or subsystem name**, lowercase, consistent with the **target repository's** `git log` history. Common examples:

| scope Type | Example |
|------------|------|
| Audio | `audio`, `capture`, `prompt` |
| Network | `network`, `wss`, `mqtt` |
| UI | `ui`, `lvgl`, `board` |
| Engineering | `build`, `ci`, `config` |
| SDK Components | Component directory name within SDK repo |

```bash
git commit -m "$(cat <<'EOF'
fix(audio): detach playback path after prompt ends, fix second-round ASR empty recognition

- Dual-path detach for stop and FINISHED
- Add AEC settle before enabling uplink
EOF
)"
```

---

## skill Repo (FreeRTOS Embedded Architect Skill)

**Pattern:** `feat: Skill vX.Y.Z — brief description` (version release / major iteration)

| Field | Description |
|------|------|
| Version | Consistent with `SKILL.md` frontmatter `metadata.version` |
| Separator | Em dash `—` |
| patch | Text/minor fixes may use `docs:` / `fix:` + short description |

```bash
git commit -m "$(cat <<'EOF'
feat: Skill v2.19.0 — generalize C10 voice constraints and platform layering
EOF
)"
```

**After skill maintenance commit:** If the full version is modified and version is bumped → run `python scripts/sync_lite.py`.

---

## Pre-commit Status Protection (Multi-repo/Nested Repos)

| Rule | Description |
|------|------|
| **Only commit related files** | `git add` only files modified for the current task; `git add .` or `git add -A` are forbidden |
| **List uncommitted dirty files** | Before committing, `git status` to show unstaged files, explain why they are not committed |
| **Exclude build-generated files** | `build/`, `*.o`, `*.bin`, `gen_files_list.txt`, etc. are forbidden to commit |
| **Check nested repos separately** | If there are submodules or nested git repos (e.g., `projects/app/`), run `git status` for each repo separately |
| **Separate concerns** | Split changes for different features into separate commits; one commit does one thing only |

```bash
# Pre-commit check example
git status                    # View all changes
git diff --cached             # View staged content
git diff                      # View unstaged content

# Nested repo check
cd projects/app && git status
cd ../../skill && git status
```

**Do not** commit unrelated changes in one commit (e.g., modifying audio + ui + config simultaneously).

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
- Skill 版本发布 → [archived self_iterate.md](../archive/workflows/self_iterate.md) Step 3
- Cursor 用户规则可引用本文件路径
