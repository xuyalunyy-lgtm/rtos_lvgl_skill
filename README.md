# FreeRTOS Embedded Architect Skill

FreeRTOS/IoT 固件架构技能：代码审查、LVGL UI 生成、崩溃调试、OTA 安全、SDK 裁剪、模块契约、任务拓扑、DMA/ISR 安全、音视频同步、MCP 串口调试。约束系统 C1-C45（45 个约束域，248 条规则）。

第一次使用请从 [onboard.md](onboard.md) 开始。

---

## 5 分钟上手

### 1. 环境准备

```bash
# 需要 Python 3.10+，核心功能零依赖
# Windows 必设（PowerShell）
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'

# macOS / Linux
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
```

### 2. 一键审查你的代码

```bash
# 单文件审查
python tools/run_review.py your_code.c --platform esp32

# 整个目录审查
python tools/run_review.py --dir ./src --platform esp32

# 按项目实际 Kconfig 过滤已编译掉的分支（可重复指定配置文件）
python tools/run_review.py --dir ./src --platform esp32 --config ./sdkconfig
```

`exit=1` 表示发现问题，`exit=0` 表示全部通过。
`--platform` 可选：`esp32` / `stm32` / `jl` / `bk` / `freertos` / `zephyr`。
平台参数会传递给全部 SDK-aware checker：STM32 会审查 HAL 回调阻塞，JL/BK 会审查是否绕过各自任务封装，Zephyr 会审查 devicetree 设备就绪、Kconfig 所有权和 workqueue 阻塞；同一函数混用 FreeRTOS/Zephyr 原生 API 也会被标记为抽象层边界问题。

### 3. 项目初检

```bash
python tools/project_doctor.py ./your-project
```

自动识别 SDK/RTOS/构建系统，解析 ESP-IDF 的目标芯片或 Zephyr 的板型，并给出下一步建议。默认只读。
`--run-review` 会自动传递检测到的平台、构建系统及 `sdkconfig` / `prj.conf`，避免已禁用的 `CONFIG_*` 分支产生静态检查误报；JSON 审查结果会保存到目标项目的 `artifacts/review_history/`，并标记相对上一份报告是 improved、regressed 还是 unchanged。

```bash
# 将识别结果固化为项目级清单；不需要维护每个新芯片的全局表
python tools/project_doctor.py ./your-project --write-manifest

# 指定清单位置
python tools/project_doctor.py ./your-project --manifest ./artifacts/project_manifest.json

# 明确同意后才执行推断出的构建命令（ESP-IDF / 已识别板型的 Zephyr）
python tools/project_doctor.py ./your-project --verify-build
```

### 4. 发布前全量自测

```bash
python scripts/quick_gate.py
```

运行 review fixture、日志路由、安装边界、MCP 自测、单元测试等全部检查。

### 5. 串口调试（MCP）

在 `.mcp.json` 中配置串口：

```json
"serial-mcp": {
  "command": "python",
  "args": ["mcp/serial_server.py"],
  "env": {
    "SERIAL_ALLOWED_PORTS": "COM3",
    "SERIAL_LOG_DIR": "artifacts/serial-logs"
  }
}
```

然后使用 `serial_request(command="AT+RST", expect="ready", timeout=5.0)` 发并等。

### 6. 崩溃到验证闭环

```bash
# 生成症状计划 -> 定向审查 -> 修复建议 -> 定向复核；不自动修改固件
python tools/diagnostic_loop.py --log ./crash.log --dir ./src --platform esp32
```

每次 `run_review.py --json` 默认也会保存一份 UTF-8 JSON 报告到
`artifacts/review_history/`。如只做临时检查，可显式使用 `--no-history`。

### 7. 串口 AT 到 MQTT 的端到端验证

此桥接同时复用 serial MCP 与 MQTT MCP 的 allowlist：必须显式指定端口、broker、模组 AT 命令模板和 Wi-Fi 密码所在环境变量；不会扫描设备、不会在输出中回显命令或密码。

```powershell
$env:SERIAL_ALLOWED_PORTS = 'COM3'
$env:MQTT_ALLOWED_HOSTS = '192.168.1.20'
$env:WIFI_PASSWORD = 'replace-with-local-secret'

python tools/serial_mqtt_e2e.py --port COM3 --broker 192.168.1.20 --topic device/e2e --ssid lab-net --wifi-password-env WIFI_PASSWORD --mqtt-command '<module-specific MQTT setup using {broker}>' --publish-command '<module-specific publish using {topic} and {payload}>'
```

不同 AT 固件的 MQTT 建连序列不兼容，因此 `--mqtt-command` 可重复传入，且必须由操作者按目标模组明确提供。

---

## 入口一览

| 场景 | 入口 | 说明 |
|------|------|------|
| CLI / CI 审查 | `python tools/run_review.py` | 一键静态审查 |
| 约束查询 | `python tools/constraint_lookup.py C15` | 规则、checker、样例与平台差异 |
| 实时审查 | `python tools/run_review.py --dir ./src --watch` | 保存文件后增量重跑 |
| Claude Code / IDE | Skill | 读取 `SKILL.md` 与对应 workflow |
| 项目初检 | `python tools/project_doctor.py <project>` | 识别 SDK/RTOS/构建系统，生成可选项目清单 |
| 崩溃闭环 | `python tools/diagnostic_loop.py --log ... --dir ...` | 分诊、定向审查、修复建议与复核 |
| LVGL 页面生成 | 目标工程优先 | 遵循 `workflows/l3_lvgl_page.md` |
| 发布前自测 | `python scripts/quick_gate.py` | 全量检查 |
| 串口调试 | `serial_request` / `serial_watch` | MCP 串口工具 |
| AT + MQTT 验证 | `python tools/serial_mqtt_e2e.py ...` | 显式授权的端到端设备消息验证 |

控制平面：[SKILL.md](SKILL.md) · 结构总览：[references/skill_structure.md](references/skill_structure.md)

## 四层结构

```
L0  SKILL.md                 意图路由（<100 行）
L0  agents/openai.yaml       Codex/OpenAI UI 元数据
L1  workflows/               编排（见 workflows/README.md）
L2  references/              概览 / 约束矩阵 / 结构
L3  prompts/ + platforms/    场景 + 平台（按需 1-3 + 1）
L4  examples/ + tools/       完整版专属
```

| 路径 | 职责 |
|------|------|
| [workflows/](workflows/) | L2/L3/调试/自迭代步骤编排 |
| [agents/](agents/) | Codex/OpenAI UI 元数据 |
| [references/](references/) | core_rules、约束详情、技能结构、发布治理、迭代日志 |
| [prompts/](prompts/) | 场景链（按 C 域索引，见 skill_structure） |
| [platforms/](platforms/) | ESP32 / STM32 / JL / BK 平台文档 |
| [examples/](examples/) | 好/坏示例 + `app_mvp.h` |
| [tools/](tools/) | 检查器、代码生成、fixture、检查器注册表 |
| [scripts/](scripts/) | 迭代、安装、Lite 同步（含 `.cmd` 包装器） |

安装边界：Cursor / Claude Code / Codex 安装脚本排除仓库根目录的 `README.md`、`INSTALL.md`、`CHANGELOG.md`、`.github/`、`.vscode/`、`freertos-skill-lite/`、缓存和本地 SDK。

## 常用验证命令

```bash
# 查看所有检查器
python tools/run_review.py --list-checkers

# 自测
python tools/run_review.py --self-test

# 验证示例
python tools/run_review.py --validate-examples

# 从日志症状生成并消费定向审查计划
python tools/context_router.py --symptom-text "task watchdog timeout" --json > plan.json
python tools/run_review.py --from-symptom-plan plan.json --dir ./src

# 预览审查计划（不执行 checker）
python tools/run_review.py --from-symptom-plan plan.json --dir ./src --dry-run

# 生成易读报告（同时可加 --json 输出机器可读摘要）
python tools/run_review.py --dir ./src --platform esp32 --markdown artifacts/review.md --html artifacts/review.html

# 实时审查；首次全量，随后仅检查保存的 C/C++ 文件
python tools/run_review.py --dir ./src --platform esp32 --watch

# 快速查询约束、关联 checker、fixture 与平台差异
python tools/constraint_lookup.py C15 --platform zephyr

# 架构规格驱动的模块代码生成（先生成规格，再生成可审查骨架）
python tools/firmware_architect.py --init-spec architecture.json
python tools/firmware_architect.py --spec architecture.json --outdir generated

# 只审查本次 Git 变更的 C/C++ 文件（CI 指定基线）
python tools/run_review.py --changed-only --changed-base origin/main

# 仅运行某项发布门禁；每步默认超时 300 秒
python scripts/quick_gate.py --only serial-mcp

# 项目诊断
python tools/project_doctor.py ./your-project
python tools/project_doctor.py ./your-project --run-review
python tools/project_doctor.py ./your-project --write-manifest
python tools/project_doctor.py ./your-project --verify-build

# 从故障日志跑到定向复核（不会自动应用修复）
python tools/diagnostic_loop.py --log ./crash.log --dir ./src --platform esp32

# JSON 审查结果默认记录趋势；临时审查可关闭
python tools/run_review.py --dir ./src --platform esp32 --json --no-history

# 运行时分布检查
python scripts/check_runtime_distribution.py

# 技能元数据检查
python scripts/check_skill_metadata.py
python scripts/check_skill_metadata.py --self-test

# 提交审计
python scripts/commit_audit.py --self-test
python scripts/commit_audit.py --max-log 12 --strict-release

# 迭代检查
python scripts/skill_iterate.py --check
```

## 关键示例

| 类型 | 文件 |
|------|------|
| 好示例 WSS Model | [examples/good_wss_json_parse.c](examples/good_wss_json_parse.c) |
| 好示例 Presenter | [examples/good_presenter_consumer.c](examples/good_presenter_consumer.c) |
| 好示例 语音 Uplink | [examples/good_voice_prompt_uplink.c](examples/good_voice_prompt_uplink.c) |
| 好示例 音视频同步 | [examples/good_av_pipeline_sync.c](examples/good_av_pipeline_sync.c) |
| 好示例 媒体格式 | [examples/good_media_format_contract.c](examples/good_media_format_contract.c) |
| 好示例 时钟/Jitter | [examples/good_av_clock_jitter.c](examples/good_av_clock_jitter.c) |
| 好示例 DMA/cache buffer | [examples/good_av_dma_buffer_lifecycle.c](examples/good_av_dma_buffer_lifecycle.c) |
| 好示例 C22 OTA | [examples/good_ota_update.c](examples/good_ota_update.c) |
| 坏示例 WSS 栈/重连 | [examples/bad_wss_blocking.c](examples/bad_wss_blocking.c) |
| 坏示例 音视频阻塞 | [examples/bad_av_pipeline_blocking.c](examples/bad_av_pipeline_blocking.c) |
| 坏示例 媒体格式 | [examples/bad_media_format_mismatch.c](examples/bad_media_format_mismatch.c) |
| 坏示例 时钟/Jitter | [examples/bad_av_clock_jitter.c](examples/bad_av_clock_jitter.c) |
| 坏示例 DMA/cache buffer | [examples/bad_av_dma_buffer_lifecycle.c](examples/bad_av_dma_buffer_lifecycle.c) |
| 坏示例 C12 返回值 | [examples/bad_unchecked_return.c](examples/bad_unchecked_return.c) |
| 坏示例 C14 日志 | [examples/bad_isr_printf.c](examples/bad_isr_printf.c) |
| 坏示例 C22 OTA | [examples/bad_ota_no_rollback.c](examples/bad_ota_no_rollback.c) |
| 共享类型 | [examples/app_mvp.h](examples/app_mvp.h) |

## 常见问题

**Q: Windows 下输出乱码？** 设置 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。

**Q: 想看某个 checker 的详细规则？** 查看 `references/constraint_quick_index.md` 找到对应约束 ID，再查对应分片文件。

**Q: 如何给自己的代码写 fixture？** 参考 `tools/fixtures/` 目录下的 `good_*.c` 和 `bad_*.c` 文件。

**Q: 串口 MCP 怎么用？** 见 [mcp/README.md](mcp/README.md)，核心是 `serial_request`（发并等）和 `serial_watch`（后台监控）。
