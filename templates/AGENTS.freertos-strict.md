# AGENTS.md — FreeRTOS Embedded Architect (Strict Mode)

> 将此文件放入项目根目录作为 `AGENTS.md`，让 Codex/Claude 在本项目中自动遵守 FreeRTOS skill 纪律。

## 项目约束

本项目使用 `freertos-embedded-architect` skill 管理所有 RTOS/固件/嵌入式相关任务。

### 默认平台

- 平台：`esp32`（可在项目配置中修改）
- 框架：`ESP-IDF`、`LVGL`、`mbedTLS`

### 必须遵守的规则

1. **代码审查**：必须使用 `l2_code_review` 工作流，运行 `run_review.py`
2. **新模块**：必须使用 `l3_new_module` 工作流，生成 `*_contract.h` + `*_fsm.c`
3. **Crash 分析**：必须使用 `debug_crash` 工作流
4. **自动修复**：必须使用 `l2_auto_repair` 工作流，输出 `--plan` 不直接改代码
5. **发布**：必须使用 `l2_release_qualification` 工作流

### 约束体系

- RTOS 核心约束：C1-C45
- 框架约束：LVGL-1~5, ESP-IDF-1~7, MBEDTLS-1~4, LWIP-1~4
- 每次回答必须引用相关约束域

### 验证命令

```bash
# 代码审查
python tools/run_review.py --dir src --platform esp32

# RTOS 系统审查（通过 run_review.py 集成）
python tools/run_review.py --dir src --platform esp32

# 框架检查
python tools/framework_constraint_checker.py --dir src --auto

# 发布门禁
python scripts/skill_iterate.py --check
python scripts/commit_audit.py --strict-release
```

### 严格模式激活

在对话中说："启用 freertos-embedded-architect 严格模式"

严格模式下：
- 每轮必须选 workflow
- 必须声明平台/框架
- 必须引用约束
- 必须有验证计划
