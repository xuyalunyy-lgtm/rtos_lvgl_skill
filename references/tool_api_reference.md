# Tool API Reference — CLI 工具接口参考

所有工具均为纯 Python stdlib，零外部依赖。用法：`python tools/<name>.py [options]`。

> 工具说明以各工作流和目标工程的构建文档为准。

## 入口工具

### run_review.py — 一键静态审查

驱动 31+ checker 的主入口。

```bash
python tools/run_review.py --dir ./src --platform esp32
python tools/run_review.py --dir ./src --platform esp32 --json
python tools/run_review.py --dir ./src --platform esp32 --suggest-fixes --fix-detail full
python tools/run_review.py --dir ./src --platform esp32 --scan-secrets
python tools/run_review.py --dir ./src --platform esp32 --config ./sdkconfig
python tools/context_router.py --symptom-text "task watchdog timeout" --json > plan.json
python tools/run_review.py --from-symptom-plan plan.json --dir ./src
python tools/run_review.py --from-symptom-plan plan.json --dir ./src --dry-run --json
python tools/run_review.py --changed-only --changed-base origin/main
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
| `--from-symptom-plan <file>` | 可选 | 只运行 `context_router` / `log_triage --json` 计划内的 `checker_targets` |
| `--dry-run` | 可选 | 输出实际会调用的辅助工具和 checker，不执行它们 |
| `--changed-only` | 可选 | 仅审查相对 `HEAD` 的 Git diff 内 C/C++ 源与头文件 |
| `--changed-base <rev>` | 可选 | 对比 `<rev>...HEAD`；用于 CI/PR 的明确基线，须与 `--changed-only` 联用 |
| `--config <file>` | 可选，可重复 | 加载 `sdkconfig` / `prj.conf`；对已知禁用的单一 `CONFIG_*` 条件分支跳过扫描 |
| `--self-test` | 可选 | 自测模式 |
| `--list-checkers` | 可选 | 列出所有 checker |
| `--validate-examples` | 可选 | 验证 examples/ 正反例 |

- **Exit code**：0=全部通过，1=发现问题
- **JSON 输出**：`{checkers: [{name, issues: [{severity, constraint, file, line, message}]}], summary: {total, p0, p1, p2}}`
- **Checker 协议**：`run_review` 以 `checker-result/v1` JSON Lines 接收每个 checker 的 `{violations, issues}`，不再解析人类 stdout 计数。
- **C29 接口契约**：`module_boundary_checker` 会比较本地 quoted include / 同名 `.h` 与 `.c` 的同名函数签名；未在审查范围找到实现的外部库声明不会报错。
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

### quick_gate.py — 快速发布门禁

```bash
python scripts/quick_gate.py --strict
python scripts/quick_gate.py --only serial-mcp
python scripts/quick_gate.py --filter "project doctor" --timeout 120
```

每个步骤默认最多运行 300 秒；超时会作为失败步骤明确报告。成功、失败和超时步骤都会输出耗时，末尾汇总逐步耗时、累计耗时和墙钟耗时。`--only` 与 `--filter` 可重复使用，按显示名或短横线 slug 筛选步骤。

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
```

`--json` 输出包含 `diagnostic_plan`；可直接保存后传给
`run_review.py --from-symptom-plan`，执行症状关联的最小 checker 集合。

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

运行当前仓库中真实存在的发布检查：review fixture、日志路由、安装边界、MCP 自测、项目 Doctor、单元测试和链接/编码检查。输出会显示实际检查项数；所有项均为阻塞项。

### skill_iterate.py — Skill 迭代检查

```bash
python scripts/skill_iterate.py --check
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
├── check_release_contract.py
├── project_doctor.py --self-test
├── unittest tests/
├── mqtt_server.py / ota_server.py / serial_server.py --self-test
├── check_links.py
└── run_review.py --self-test
```

### project_doctor.py

项目诊断与 manifest 生成统一入口。默认离线、只读；不会写文件或触发编译。

```bash
python tools/project_doctor.py <project>
python tools/project_doctor.py <project> --write-manifest
python tools/project_doctor.py <project> --manifest <path>
python tools/project_doctor.py <project> --verify-build
python tools/project_doctor.py <project> --run-review
```

`--run-review` 会将检测到的 Kconfig 配置文件传给 `run_review`；manifest 的
`configuration.enabled` 列出已启用的 `CONFIG_*`，供 CI 和后续诊断复用。

当前内置 ESP-IDF 与 Zephyr 解析器：ESP-IDF 从 `sdkconfig` 提取 `CONFIG_IDF_TARGET`，Zephyr 从 `build/zephyr/.config` 或项目配置提取 `CONFIG_BOARD`。因此同一 SDK 家族的新芯片通常无需更新工具；只有新增 SDK 家族时才需要增加解析器。

`--verify-build` 是显式副作用操作：ESP-IDF 执行 `idf.py build`；Zephyr 仅在已识别板型时执行 `west build -b <board> .`。构建产物会记录在输出的 `project_manifest` 中。
