# 安装说明（FreeRTOS Embedded Architect Skill — 完整版）

本仓库为 **完整版**：含 `SKILL.md`、平台专档、场景 prompt、`examples/` 正反范例、`tools/` checker/codegen。

## 安装到 Cursor

### 个人 Skill（推荐，全项目可用）

本机路径 `~/.cursor/skills/`，**不**走 Cursor 云账号；全项目 Agent 可加载。

**Windows（推荐脚本，自动排除 `.git` / 本地 SDK 参考目录）**

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

Windows（无需 Python，元数据 + Lite 同步；checker 步骤跳过，依赖 CI）：

```powershell
# 若提示“禁止运行脚本”，用 .cmd 包装（无需改 ExecutionPolicy）：
.\scripts\skill_iterate.cmd -Sync

# 或单次 Bypass（将路径换成你的 skill 目录）：
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File .\scripts\skill_iterate.ps1 -Sync
```

含铁律 #2：`queue_ownership_checker.py`（L2 一键审查已串联）。

记录变更 → `references/iteration_log.md`、`CHANGELOG.md`；流程见 `workflows/self_iterate.md`。

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

# 同步 Lite 分发包（生成 SKILL.md + 同步 prompts/platforms/workflows/references）
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

若只需规则与 prompt、不需要范例与脚本，使用 [freertos-skill-lite/INSTALL.md](freertos-skill-lite/INSTALL.md)。

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
