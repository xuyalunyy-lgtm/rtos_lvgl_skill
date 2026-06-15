# 安装说明（FreeRTOS Embedded Architect Skill — 完整版）

本仓库为 **完整版**：含 `SKILL.md`、平台专档、场景 prompt、`examples/` 正反范例、`tools/` checker/codegen。

## 安装到 Cursor

### 个人 Skill（推荐，全项目可用）

**Windows**

```powershell
Copy-Item -Recurse "C:\path\to\skill" "$env:USERPROFILE\.cursor\skills\freertos-embedded-architect"
```

**macOS / Linux**

```bash
cp -r /path/to/skill ~/.cursor/skills/freertos-embedded-architect
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

## 工具（L2 Review / L3 生成后校验）

在项目源码目录执行（Python 3.8+，无第三方依赖）：

```bash
# 一键审查（推荐）
python path/to/skill/tools/run_review.py --dir ./src --platform jl

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
