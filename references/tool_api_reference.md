# Tool API Reference — CLI 工具接口参考

所有工具均为纯 Python stdlib，零外部依赖。用法：`python tools/<name>.py [options]`。

> MCP 工具见 [mcp_tool_reference.md](mcp_tool_reference.md)。

## 入口工具

### run_review.py — 一键静态审查

驱动 31+ checker 的主入口。

```bash
python tools/run_review.py --dir ./src --platform esp32
python tools/run_review.py --dir ./src --platform esp32 --json
python tools/run_review.py --dir ./src --platform esp32 --suggest-fixes --fix-detail full
python tools/run_review.py --dir ./src --platform esp32 --scan-secrets
python tools/run_review.py --self-test
python tools/run_review.py --list-checkers
python tools/run_review.py --validate-examples
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `--dir <path>` | 必选（二选一） | 源码目录 |
| `<file>` | 必选（二选一） | 单个文件路径 |
| `--platform <x>` | 必选 | `esp32` / `stm32` / `jl` / `bk` / `freertos` / `zephyr` |
| `--json` | 可选 | 输出 JSON 格式 |
| `--include-bad` | 可选 | 包含 `bad_*.c` 反例 |
| `--suggest-fixes` | 可选 | 输出修复建议 FixPlan |
| `--fix-detail` | 可选 | `summary`（默认）/ `full` |
| `--scan-secrets` | 可选 | 附加密钥扫描（C9） |
| `--strict-field` | 可选 | P0 现场诊断阻断 exit code |
| `--self-test` | 可选 | 自测模式 |
| `--list-checkers` | 可选 | 列出所有 checker |
| `--validate-examples` | 可选 | 验证 examples/ 正反例 |

- **Exit code**：0=全部通过，1=发现问题
- **JSON 输出**：`{checkers: [{name, issues: [{severity, constraint, file, line, message}]}], summary: {total, p0, p1, p2}}`
- **依赖**：`checker_registry.py` → 各 checker 模块 → `checker_io.py` → `static_c_scan.py`

### context_router.py — 上下文路由器

根据 workflow/platform/constraints 输出最小读取计划。

```bash
python tools/context_router.py --workflow code_review --platform esp32 --json
python tools/context_router.py --workflow crash_debug --platform esp32 --rtos freertos --constraints C2 C3 --json
python tools/context_router.py --workflow code_review --platform esp32 --budget full --json
python tools/context_router.py --symptom-text "HardFault in audio task" --json
python tools/context_router.py --self-test
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `--workflow <id>` | 必选（二选一） | `code_review` / `project_review` / `crash_debug` / `memory_analysis` / `sdk_trim` / `new_module` / `bring_up` / `lvgl_page` / `hw_sw_debug` |
| `--symptom-text <text>` | 必选（二选一） | 自然语言症状描述（自动推断 workflow） |
| `--symptom-file <path>` | 可选 | 症状文件路径 |
| `--platform <x>` | 必选 | `esp32` / `stm32` / `jl` / `bk` |
| `--rtos <x>` | 可选 | `freertos`（默认）/ `zephyr` |
| `--budget <level>` | 可选 | `compact`（默认）/ `standard` / `full` |
| `--constraints <Cx...>` | 可选 | 指定约束 ID |
| `--json` | 可选 | 输出 JSON 格式 |
| `--self-test` | 可选 | 自测模式 |

- **Exit code**：0=成功
- **JSON 输出**：`{required_files, forbidden_by_default, constraint_shards, estimated_tokens, budget_mode, workflow, platform}`

## 门禁工具

### codegen_gate.py — 代码生成门禁

检查 manifest 完整性、文件存在性、约束覆盖、禁止模式。

```bash
python tools/codegen_gate.py --manifest <path> --platform esp32
python tools/codegen_gate.py --manifest <path> --platform esp32 --json
```

### project_gate.py — 工程门禁

包装 run_review + profile 预设 + log triage。

```bash
python tools/project_gate.py --dir ./src --platform esp32 --profile <name>
```

## 生成器工具

### project_scaffold.py — 项目脚手架生成

```bash
python tools/project_scaffold.py --platform esp32 --module-name sensor --output ./src/sensor
```

### module_contract_gen.py — 模块契约生成

```bash
python tools/module_contract_gen.py --platform esp32 --module-name sensor --json
```

### mvp_codegen_tool.py — MVP 代码生成

```bash
python tools/mvp_codegen_tool.py --contract <path> --output ./src
```

## 分析工具

### log_triage.py — 日志分类

```bash
python tools/log_triage.py --log <path> --platform esp32 --json
python tools/log_triage.py --symptom-text "HardFault" --json
```

### constraint_discovery.py — 约束发现

```bash
python tools/constraint_discovery.py --dir ./src --json
```

### sdk_lookup.py — SDK 抽象查询

```bash
python tools/sdk_lookup.py --platform esp32 --info gpio_set
python tools/sdk_lookup.py --platform esp32 --category i2c
python tools/sdk_lookup.py --platform esp32 --list spi
python tools/sdk_lookup.py --platform esp32 --all-ops
python tools/sdk_lookup.py --platform esp32 --all-categories
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `--platform <x>` | 必选 | `esp32` / `stm32` / `jl` / `bk` / `zephyr` |
| `--info <op>` | 可选 | 查询单个操作详情 |
| `--category <cat>` | 可选 | 查询分类下所有操作 |
| `--list <keyword>` | 可选 | 关键词搜索 |
| `--regex <pattern>` | 可选 | 正则搜索 |
| `--all-ops` | 可选 | 列出所有操作 |
| `--all-categories` | 可选 | 列出所有分类 |

### auto_fix_engine.py — 自动修复引擎

```bash
python tools/auto_fix_engine.py --plan <review_json> --json
python tools/auto_fix_engine.py --apply <fix_plan_json>
```

## LVGL 工具

### generate_lvgl_from_design.py — 设计稿转 LVGL

```bash
python tools/generate_lvgl_from_design.py --design <path> --assets <dir> --output <dir>
```

### run_lvgl_regression.py — LVGL 回归测试

```bash
python tools/run_lvgl_regression.py --baseline <path> --actual <path> --json
```

### validate_cutout_audit.py — 切图审计

```bash
python tools/validate_cutout_audit.py --assets <dir> --json
```

## 维护工具

### check_links.py — 链接检查

```bash
python tools/check_links.py
```

扫描所有 .md 文件，验证内部链接有效性。

## 脚本工具（scripts/）

### quick_gate.py — 快速门禁

```bash
python scripts/quick_gate.py
python scripts/quick_gate.py --strict
```

依次运行 15 项检查：self-test、example 验证、log triage、text encoding、runtime distribution、link check、LVGL regression 等。

### skill_iterate.py — Skill 迭代检查

```bash
python scripts/skill_iterate.py --check
python scripts/skill_iterate.py --check --strict-release
```

### check_skill_metadata.py — 元数据验证

```bash
python scripts/check_skill_metadata.py
python scripts/check_skill_metadata.py --self-test
```

### commit_audit.py — 提交审计

```bash
python scripts/commit_audit.py --self-test
python scripts/commit_audit.py --max-log 12 --strict-release
```

## 统一 Gate 输出格式

所有 gate 类工具输出兼容结构：

```json
{
  "passed": true,
  "severity": "P0",
  "violations": [],
  "warnings": [],
  "constraints": ["C1", "C4"],
  "verification_commands": ["python tools/run_review.py --self-test"],
  "evidence_files": []
}
```

## 工具依赖图

```
run_review.py
├── checker_registry.py (31+ checker 注册)
├── checker_io.py (共享 I/O)
├── static_c_scan.py (C 代码扫描)
└── 各 checker 模块 (cjson_leak_checker.py, isr_safety_checker.py, ...)

context_router.py
├── references/log_symptom_routes.json
└── references/constraint_quick_index.md

codegen_gate.py
├── tools/manifest_normalizer.py
└── references/codegen_contract.md

auto_fix_engine.py
└── run_review.py (JSON 输出)

quick_gate.py
├── check_skill_metadata.py
├── check_text_encoding.py
├── check_runtime_distribution.py
├── check_links.py
├── check_lvgl_regression.py
└── run_review.py --self-test
```
