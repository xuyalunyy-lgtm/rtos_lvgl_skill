# 安装说明（FreeRTOS Embedded Architect Skill — Lite 版）

本包为 **Lite 分发版**：含架构规则、平台专档、场景 prompt；**不含** `examples/` 范例源码与 `tools/` 自动化脚本。

## 安装（Cursor）

### Windows

```powershell
# 解压后将整个 freertos-skill-lite 文件夹复制为：
Copy-Item -Recurse freertos-skill-lite "$env:USERPROFILE\.cursor\skills\freertos-embedded-architect"
```

### macOS / Linux

```bash
cp -r freertos-skill-lite ~/.cursor/skills/freertos-embedded-architect
```

重启 Cursor 或新开 Agent 对话。触发示例：

> 按 freertos-embedded-architect skill，帮我设计 BK7258 WSS + LVGL MVP 架构

## BK 编译脚本（可选）

将 `bk_build.ps1` / `bk_build.sh` 复制到与 `bk_avdk_smp` **同级**的工作区根目录使用。详见 `platforms/bk.md`。

## 与完整版差异

| 完整版 | Lite 版 |
|--------|---------|
| `examples/` 正反范例 .c | Agent 按 prompt 内嵌规则生成代码 |
| `tools/*.py` checker/codegen | Step 5 人工审查清单（见 SKILL.md） |

维护者在完整版仓库根目录运行 `python scripts/sync_lite.py` 可同步 `prompts/` 与 `platforms/`（含 AC79 `jl.md`）。

## 授权

见 [LICENSE](LICENSE)。禁止再分发、反编译或用于训练第三方模型。
