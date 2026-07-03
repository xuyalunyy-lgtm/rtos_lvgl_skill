# 安装说明（FreeRTOS Embedded Architect Skill — 完整版）

本仓库为 **完整版**：含 `SKILL.md`、平台专档、场景 prompt、`examples/` 正反范例、`tools/` checker/codegen。

## 分发边界

源码仓保留维护资料与发布资料；安装到 Cursor / Claude Code / Codex 时默认只复制 skill 运行所需文件。

安装脚本会排除：仓库根目录的 `README.md`、`INSTALL.md`、`CHANGELOG.md`，以及 `.github/`、`.vscode/`、`freertos-skill-lite/`、`__pycache__/`、本地 SDK 目录和常见缓存目录。完整版能力中的 `tools/`、`examples/`、`prompts/`、`platforms/`、`references/` 会保留，包括 `workflows/README.md`、`examples/README.md` 等运行时索引。

Windows 下运行标准 skill 校验或任何会读取中文 `SKILL.md` 的 Python 脚本时，建议固定 UTF-8：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
```

## 安装到 Cursor

### 个人 Skill（推荐，全项目可用）

本机路径 `~/.cursor/skills/`，**不**走 Cursor 云账号；全项目 Agent 可加载。

**Windows（推荐 `.cmd`，无需改 ExecutionPolicy）**

```powershell
cd C:\path\to\skill
.\scripts\install_skill.cmd
```

或 PowerShell（需 Bypass 或 RemoteSigned）：

```powershell
cd C:\path\to\skill
.\scripts\install_skill.ps1
```

**macOS / Linux**

```bash
cd /path/to/skill
chmod +x scripts/install_skill.sh
./scripts/install_skill.sh
```

手动复制（须排除 `fw-AC79_AIoT_SDK/` 与 `.git/`）：

```powershell
# Windows — 勿用裸 Copy-Item -Recurse，会把本地 SDK 参考目录一并装进 skill
.\scripts\install_skill.ps1
```

### 项目 Skill（团队共享）

```bash
mkdir -p .cursor/skills
cp -r /path/to/skill .cursor/skills/freertos-embedded-architect
```

重启 Cursor 或新开 Agent 对话。

### 提高命中率（DeepSeek / 弱路由模型）

Skill 自动发现依赖 `SKILL.md` 的 **description** 与用户话术匹配；DeepSeek 等模型路由较弱时，建议 **三层兜底**：

| 层级 | 做法 | 命中率 |
|------|------|--------|
| 1 | 固件仓 `.cursor/rules/` + [cursor-rule 模板](templates/cursor-rule.embedded.mdc) | 编辑 `.c/.h` 时自动 Read skill |
| 2 | 固件仓 `.cursor/skills/` 项目级 skill（见上） | 比仅个人 skill 更稳 |
| 3 | 对话 `@freertos-embedded-architect` 或「按 freertos skill …」 | 100% |

**安装 Cursor Rule（固件工程根目录）：**

```powershell
# Windows
New-Item -ItemType Directory -Force -Path .cursor\rules | Out-Null
Copy-Item C:\path\to\skill\templates\cursor-rule.embedded.mdc .cursor\rules\freertos-embedded.mdc
```

```bash
# macOS / Linux
mkdir -p .cursor/rules
cp /path/to/skill/templates/cursor-rule.embedded.mdc .cursor/rules/freertos-embedded.mdc
```

Rule 使用 `globs: **/*.{c,h}`，打开/编辑 C 源文件时触发，不要求 `alwaysApply: true`。

**更新 skill 后务必重装**（否则本机仍是旧版 description）：

```powershell
cd C:\path\to\skill
.\scripts\install_skill.cmd
```

## 触发示例

```
按 freertos-embedded-architect skill，帮我 review 这段 WSS + LVGL 代码
```

```
JL AC79 带屏音箱，从 SDK Demo 做需求驱动裁剪，设计 MVP 任务优先级
```

## CI

Push 到 `tools/`、`scripts/`、`examples/` 时 GitHub Actions 自动运行：

```bash
python tools/run_review.py --self-test
python tools/run_review.py --validate-examples
python scripts/skill_iterate.py --check --skip-self-test
```

Skill 自我迭代闭环：

```bash
python scripts/skill_iterate.py --check --sync
```

Windows（无需 Python，元数据检查；checker 步骤跳过，依赖 CI）：

```powershell
# 若提示“禁止运行脚本”，用 .cmd 包装（无需改 ExecutionPolicy）：
.\scripts\skill_iterate.cmd -Sync

# 或单次 Bypass（将路径换成你的 skill 目录）：
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File .\scripts\skill_iterate.ps1 -Sync
```

含铁律 #2：`queue_ownership_checker.py`（L2 一键审查已串联）。

记录变更 → `references/iteration_log.md`、`CHANGELOG.md`；历史自迭代流程见 [archive/workflows/self_iterate.md](archive/workflows/self_iterate.md)。

## 工具（L2 Review / L3 生成后校验）

在项目源码目录执行（Python 3.8+，无第三方依赖）：

**Windows 若 `python` 命令找不到**（已安装但未进 PATH）：

```powershell
# 方式 A：用 .cmd 包装（推荐，无需改 ExecutionPolicy）
.\scripts\skill_iterate.cmd -Sync

# 方式 A2：PowerShell 脚本（需 Bypass 或 RemoteSigned）
.\scripts\skill_iterate.ps1 -Sync

# 方式 B：把 Python 加入当前会话 PATH（按本机安装路径调整）
$env:Path += ";$env:LOCALAPPDATA\Programs\Python\Python312;$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
python --version

# 方式 C：设置 → 应用 → 高级应用设置 → 应用执行别名 → 关闭 python.exe / python3.exe 商店别名
```

```bash
# 一键审查（推荐；默认排除 bad_*.c 反例）
python path/to/skill/tools/run_review.py --dir ./src --platform jl

# checker 自测（CI / 本地验证工具链）
python path/to/skill/tools/run_review.py --self-test

# v31 起 Lite 不在源码树维护；无生成目标时该命令为 no-op
python path/to/skill/scripts/sync_lite.py
# Windows（无需 Python）:
.\scripts\sync_lite.cmd

# 单项
python path/to/skill/tools/stack_calculator.py --describe "WSS TLS cJSON" --platform esp32
python path/to/skill/tools/cjson_leak_checker.py network_wss_task.c
python path/to/skill/tools/isr_safety_checker.py --dir src/
python path/to/skill/tools/lvgl_thread_checker.py src/
python path/to/skill/tools/mvp_codegen_tool.py Network --platform bk -o ./generated
```

## BK 编译脚本（可选）

将仓库根目录的 `bk_build.ps1` / `bk_build.sh` 复制到与 `bk_avdk_smp` **同级**的工作区根目录。详见 [platforms/bk.md](platforms/bk.md)。

## Lite 版

v31 起 Lite 版不在源码树维护；若只需规则与 prompt，应由发布流水线生成轻量包。

## Claude Code

```powershell
.\scripts\install_claude_code.ps1
# 可选：同时生成固件工程 CLAUDE.md / .claudeignore
.\scripts\install_claude_code.ps1 -ProjectRoot C:\path\to\firmware
```

- Skill → `~/.claude/skills/freertos-embedded-architect/`，invoke `/freertos-embedded-architect`
- 省 token 指南 → [references/claude_code.md](references/claude_code.md)
- 项目模板 → [templates/CLAUDE.embedded.md](templates/CLAUDE.embedded.md)

## Codex

```powershell
python scripts\install_multi_ide.py --ide codex
```

安装目标为 `$CODEX_HOME\skills\freertos-embedded-architect`；未设置 `CODEX_HOME` 时使用 `~\.codex\skills\freertos-embedded-architect`。UI 元数据见 `agents/openai.yaml`。

| 完整版 | Lite 版 |
|--------|---------|
| `examples/` + `tools/` | 无，Step 5 用 SKILL.md 人工清单 |
| `run_review.py` 一键审查 | 人工 checklist |

## 平台路由

| 芯片 / SDK | 读取 |
|------------|------|
| ESP32 / ESP-IDF | [platforms/esp32.md](platforms/esp32.md) |
| STM32 / CubeMX | [platforms/stm32.md](platforms/stm32.md) |
| JL 杰理 / **AC79 / WL82 / AC791N** | [platforms/jl.md](platforms/jl.md) |
| BK / BK7258 / Armino | [platforms/bk.md](platforms/bk.md) |
