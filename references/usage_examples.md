# Usage Examples — 使用示例

> 按需加载。用户或 Agent 不确定"怎么用这个 skill"时读取本文件。

---

## Quick Start

进入工程目录后，显式触发 skill：

```
使用 freertos-embedded-architect skill 审查这个 ESP32 项目
```

Agent 会：
1. 加载 `SKILL.md` 路由表
2. 选择 `l2_code_review` 工作流
3. 声明平台 `esp32`
4. 运行 `run_review.py --dir src --platform esp32`

---

## Strict Mode

启用严格模式后，每轮 RTOS/固件任务必须：选 workflow → 声明平台/框架 → 引用约束 → 给验证计划。

**激活：**
```
启用 freertos-embedded-architect 严格模式，本次对话后续都按该 skill 执行
```

**解除：**
```
解除 freertos skill 严格模式
```

**效果：**
- 代码审查：必须先选 `l2_code_review`，声明平台，引用 C1-C45
- 新模块：必须先选 `l3_new_module`，生成 contract header + state machine
- Crash：必须先选 `debug_crash`，加载症状表
- 非 RTOS 任务：说明"此任务不属于该 skill 约束范围"，正常回答

---

## Common Tasks

### 1. RTOS 系统审查

```
对这个项目做 RTOS 系统审查，分析任务拓扑、优先级、IPC 和内存
```

Agent 应：
- 选 `l2_rtos_system_review` 工作流
- 运行 `rtos_model.py --dir src`
- 运行 `task_graph_analyzer.py`、`scheduler_analyzer.py`、`ipc_contract_checker.py`
- 输出风险列表和约束域

### 2. 代码审查

```
审查 src/main.c 的 FreeRTOS 代码质量
```

Agent 应：
- 选 `l2_code_review` 工作流
- 运行 `run_review.py --dir src`
- 输出 `[P0] C3.1 — file:line — 问题描述`
- 给出修复建议和验证命令

### 3. 新模块设计

```
设计一个 audio_player 模块，ESP32 平台，I2S 输出
```

Agent 应：
- 选 `l3_new_module` 工作流
- 运行 `module_contract_gen.py --name audio_player`
- 生成 `audio_player_contract.h` + `audio_player_fsm.c`
- 引用 C29（模块契约）、C33（生命周期对称）

### 4. Crash 调试

```
设备启动后 5 秒 watchdog 复位，这是串口日志
```

Agent 应：
- 选 `debug_crash` 工作流
- 加载症状表，匹配 WDT 复位模式
- 引用 C31（阻塞等待）、C15（优先级）
- 给出排查步骤和验证命令

### 5. LVGL/DMA/ISR 安全检查

```
检查 LVGL 是否在正确的线程中调用
```

Agent 应：
- 选 `l2_code_review` 工作流
- 运行 `lvgl_thread_checker.py`
- 引用 C1（LVGL 线程安全）、C4（ISR 安全）

### 6. 发布前检查

```
准备发布，做全面检查
```

Agent 应：
- 选 `l2_release_qualification` 工作流
- 运行 `skill_iterate.py --check`
- 运行 `release_qualifier.py`
- 输出 pass/warn/fail 结论

---

## Daily Entry

将 `templates/AGENTS.freertos-strict.md` 复制为项目根目录的 `AGENTS.md`：

```bash
cp templates/AGENTS.freertos-strict.md AGENTS.md
```

效果：
- Codex/Claude 在本项目中自动遵守 FreeRTOS skill 纪律
- 默认平台和框架在 AGENTS.md 中声明
- 每次回答自动引用约束

---

## Expected Output

严格模式下，Agent 回答应包含：

| 元素 | 示例 |
|------|------|
| Workflow | `l2_code_review` |
| Platform | `esp32` |
| Framework | `ESP-IDF`, `LVGL` |
| Constraints | `C1`, `C4`, `C29` |
| Issues | `[P0] C3.1 — main.c:42 — cJSON 未释放` |
| Fix | `使用 goto cleanup 模板` |
| Verify | `python tools/run_review.py --self-test` |

---

## Framework-Aware 审查

```
检测这个项目用了哪些框架，然后做框架约束检查
```

Agent 应：
- 运行 `framework_profile.py --dir src`
- 运行 `framework_constraint_checker.py --auto`
- 输出框架矩阵和框架特定问题

---

## Supervisor 托管执行

```
用 supervisor 执行这个修复任务，低风险自动执行
```

Agent 应：
- 创建 `.codex/jobs/fix-xxx.json`
- 运行 `codex_supervisor.py run --job .codex/jobs/fix-xxx.json`
- 输出 supervisor_report.json
