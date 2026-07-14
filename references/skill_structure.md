# Skill 结构总览（维护 / L2+ 按需加载）

Agent 维护 skill 或不确定「该读哪个文件」时读取本文件。**L1 概念问答不必加载。**

## 四层加载模型

```
L0 控制平面   SKILL.md              意图路由 · 铁律索引 · rules（禁止膨胀）
L1 编排       workflows/*.md        选定 1 个 workflow，按 Step 顺序执行
L2 总纲       references/           core_rules · constraint_index · 本文件
L3 场景       prompts/*.txt         workflow 指定 1–3 个，禁止全加载
     平台     platforms/*.md        workflow Step 1 加载 1 个
L4 可执行     tools/                完整版 L2+；Lite 无此层
```

**铁律：** 每层只向下加载，禁止跳层把 prompt 全塞进 context。

---

## 四个域 + 三条主链路

SKILL.md 使用 **域检测（Domain Detection）** 路由用户意图到 4 个域之一。每个域有独立的加载规则，避免跨域加载浪费 token。

| 域 | 触发关键词 | 主链路 | 典型 workflow | 核心工具 |
|----|-----------|--------|--------------|---------|
| **review** | 审查, review, audit, ISR, DMA | review | l2_code_review, l2_project_review, hw_sw_cocodebug | run_review, context_router |
| **generate** | LVGL, UI, 页面, 新模块, bring-up | generate | l3_lvgl_page, l3_new_module, l3_bring_up, l3_sdk_trim | Target-project LVGL tooling |
| **debug** | crash, HardFault, 死机, 看门狗 | debug | debug_crash | log_triage, context_router |
| **app** | manifest, 多页, Router, Model | generate | l3_lvgl_page manifest sub-path | Target-project application tooling |

**铁律：** 每个域只加载自己域的文件，禁止跨域加载。详见 SKILL.md 各域的 Loading Rules。

---

## 工具分层

所有工具按职责分 4 类：

### Model（模型提取）
| 工具 | 职责 |
|------|------|
| `context_router.py` | 上下文路由器 — 根据 workflow/platform/constraints 输出最小读取计划 |
| `sdk_lookup.py` | SDK 抽象查询引擎 — 标准操作→平台 API 映射，所有 checker 共用 |
| `project_operating_model.py` | 统一项目事实源（RTOS + frameworks + platform + constraints） |
| `framework_profile.py` | 框架自动识别 |
| `product_profile.py` | 平台 profile 加载 |
| `platform_adapter.py` | 平台模板适配器 |

### Checkers（检查器）
| 工具 | 职责 |
|------|------|
| `run_review.py` | 一键静态审查（驱动 31 checker） |
| `constraint_discovery.py` | 约束发现 |

### Generators（生成器）
| 工具 | 职责 |
|------|------|
| `project_scaffold.py` | 项目脚手架生成 |
| `module_contract_gen.py` | 模块契约生成 |
| `mvp_codegen_tool.py` | MVP 代码生成 |

### Gates（门禁）
| 工具 | 职责 |
|------|------|
| `codegen_gate.py` | 代码生成门禁（manifest + forbidden patterns） |

### 辅助工具
| 工具 | 职责 |
|------|------|
| `auto_fix_engine.py` | 自动修复引擎 |
| `constraint_inference.py` | 约束推理引擎 |
| `efficiency_scorecard.py` | 效率度量 |
| `watch_mode.py` | 实时检查模式 |
| `check_links.py` | 链接检查 |
| `bump_version.py` | 版本号更新 |

> 治理工具（evidence/supervisor/HIL/telemetry 等）已归档至 `archive/tools/`。

---

## 统一 Gate 输出

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

---

## 目录职责

| 路径 | 职责 |
|------|------|
| `SKILL.md` | 控制平面（<100 行） |
| `workflows/` | 步骤编排（9 个用户 workflow） |
| `references/` | 总纲、约束、结构、日志 |
| `prompts/` | 场景专链 |
| `platforms/` | 芯片/SDK 事实 + SDK 映射 |
| `examples/` | good/bad 范例 |
| `tools/` | checker + 生成器 + 查询引擎 |
| `scripts/` | sync、iterate、审计 |
| `archive/` | 归档的治理工具/workflow/codex |
| `.codex/` | schemas、boards、jobs、runs | **无** |

---

## Workflow → 必读 / 按需加载

| 主链路 | Workflow | L2 必读 | L3 按需 |
|--------|----------|---------|---------|
| review | l2_code_review | core_rules + constraint_index | 嫌疑 prompt |
| review | l2_project_review | core_rules + constraint_index | 平台 prompt |
| review | hw_sw_cocodebug | core_rules + constraint_index | 平台 prompt |
| generate | l3_new_module | core_rules + codegen_contract | 模块 prompt |
| generate | l3_bring_up | core_rules + codegen_contract | boot_wdt prompt |
| generate | l3_sdk_trim | core_rules + sdk_abstraction | 平台 SDK prompt |
| generate | l3_lvgl_page | core_rules + target-project theme conventions | LVGL prompt |
| debug | debug_crash | constraint_detail 症状表 | 症状 prompt |
| debug | l2_memory_analysis | core_rules + constraint_index | memory prompt |
| — | **Session strict mode** | session_strict_mode.txt | — |
