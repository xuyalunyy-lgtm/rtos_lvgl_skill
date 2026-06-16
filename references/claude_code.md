# Claude Code 适配与省 token 指南

> **Skill 按需加载** — 正文仅在 invoke `/freertos-embedded-architect` 或任务匹配 description 时进入 context。本文档维护者/显式 `@` 时读。

## 安装

```powershell
# Windows
.\scripts\install_claude_code.ps1

# macOS / Linux
./scripts/install_claude_code.sh
```

目标：`~/.claude/skills/freertos-embedded-architect/`（个人）或项目 `.claude/skills/`（团队）。

固件工程根目录复制 [templates/CLAUDE.embedded.md](../templates/CLAUDE.embedded.md) → `CLAUDE.md`，并填编译命令。保持 **<500 token**。

项目根添加 [templates/claudeignore.embedded](../templates/claudeignore.embedded) → `.claudeignore`，排除 SDK 巨型目录。

---

## 加载原则（保能力、省 token）

```
❌ 禁止：Read/Glob 整个 skill 目录、全部 prompts/、platforms/ 四份、constraint_detail 全文
✅ 正确：1 workflow → 1 platform → 1–3 prompt → 必要时 1 个 example
```

| 级别 | 必读（按序） | 替代全文 |
|------|-------------|----------|
| L1 概念 | 无 | — |
| L2 审查 | `core_rules.md` + **`constraint_index.md`** | 勿读 constraint_detail，除非要正例路径 |
| L2 审查 | 1× `platforms/xxx.md` | 仅用户平台 |
| L2 审查 | 1–3× 嫌疑 `prompts/*.txt` | workflow/症状表指定 |
| L3 实现 | 上 + 1× workflow | `l3_new_module` / `debug_crash` 等 |
| L3 实现 | 范例用 **Grep/Read 单文件** | 如 `examples/good_wss_json_parse.c` |

**工具优先于读 checker 源码：** `python tools/run_review.py --dir ./src --platform jl`

---

## Workflow 最小文件集

| 意图 | Workflow | + 通常再读 |
|------|----------|-----------|
| Review | `workflows/l2_code_review.md` | constraint_index + 1 platform + 1–2 prompts |
| Crash | `workflows/debug_crash.md` | 症状表 1 prompt + crash_log_decode 可选 |
| 新模块 | `workflows/l3_new_module.md` | core_rules + boot_wdt 或 mbedtls 等 2 prompts |
| SDK 裁 | `workflows/l3_sdk_trim.md` | sdk_trim_prune + 1 platform |
| Skill 维护 | `workflows/self_iterate.md` | skill_structure |

索引 → [workflows/README.md](../workflows/README.md)

---

## Claude Code 会话习惯

| 习惯 | 作用 |
|------|------|
| 任务切换 `/clear` | 防 context 膨胀 |
| 大功能结束 `/compact` | 保留决策、丢中间尝试 |
| 项目 `CLAUDE.md` 只做索引 | 细节放 skill 路径，按需 Read |
| L3 **自主实施** | 改代码至编译通过，少来回确认（见 core_rules） |
| 少输出过程叙述 | 多 diff/命令/结论，少重复铁律全文 |

---

## 与 Cursor 差异

| 项 | Cursor | Claude Code |
|----|--------|-------------|
| Skill 入口 | `~/.cursor/skills/` | `~/.claude/skills/` |
| 常驻索引 | 用户 Rules | 项目 `CLAUDE.md`（宜短） |
| 审查工具 | 同 `tools/run_review.py` | 同左，用 Bash 跑 |
| Lite 包 | freertos-skill-lite | 可用 Lite 减 examples/tools 路径 |

---

## 维护

改铁律时同步 `constraint_index.md` 一行摘要；Claude 侧无需改 SKILL 体积。
