# Skill 结构总览（维护 / L2+ 按需加载）

Agent 维护 skill 或不确定「该读哪个文件」时读取本文件。**L1 概念问答不必加载。**

## 四层加载模型

```
L0 控制平面   SKILL.md              意图路由 · 铁律索引 · rules（禁止膨胀）
L1 编排       workflows/*.md        选定 1 个 workflow，按 Step 顺序执行
L2 总纲       references/           core_rules · constraint_detail · 本文件
L3 场景       prompts/*.txt         workflow 指定 1–3 个，禁止全加载
     平台     platforms/*.md        workflow Step 1 加载 1 个
L4 可执行     examples/ · tools/    完整版 L2+；Lite 无此层
```

**铁律：** 每层只向下加载，禁止跳层把 12 个 prompt 塞进 context。

---

## 目录职责

| 路径 | 职责 | 谁维护 | Lite |
|------|------|--------|------|
| `SKILL.md` | 控制平面（<100 行） | 人工 | 自动生成 |
| `workflows/` | 步骤编排、输出模板 | 人工 | 同步 + patch |
| `references/` | 总纲、约束矩阵、结构、日志 | 人工 | 同步 |
| `prompts/` | 场景专链（深细节） | 人工 | 同步 |
| `platforms/` | 芯片/SDK 事实 | 人工 | 同步 |
| `examples/` | good/bad 范例、`app_mvp.h` | 人工 + checker | **无** |
| `tools/` | checker、codegen、fixtures | 人工 + CI | **无** |
| `scripts/` | sync、iterate、install | 人工 | 部分复制 |
| `freertos-skill-lite/` | Lite 分发包 | **sync 生成** | — |

---

## Workflow → 必读 / 按需加载

| Workflow | L2 必读 | L3 按需（1–3） | L4 完整版 |
|----------|---------|----------------|-----------|
| L1 无 | — | — | — |
| [l2_code_review](../workflows/l2_code_review.md) | core_rules + constraint_detail | 嫌疑场景 prompt | run_review + examples 反例 |
| [debug_crash](../workflows/debug_crash.md) | constraint_detail 症状表 | 症状对应 prompt | run_review + 反例 |
| [l3_sdk_trim](../workflows/l3_sdk_trim.md) | core_rules | sdk_trim_prune | — |
| [l3_new_module](../workflows/l3_new_module.md) | core_rules | 模块表 prompt | mvp_codegen / good_* |
| [self_iterate](../workflows/self_iterate.md) | **本文件** + iteration_log | 受影响层 prompt | skill_iterate |

Workflow 索引 → [workflows/README.md](../workflows/README.md)

---

## 场景 Prompt 目录（C 域 → 文件）

| C 域 | 场景 | 文件 |
|------|------|------|
| C1 | LVGL 线程 / v8v9 | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) · [lvgl_v8_v9_diff.txt](../prompts/lvgl_v8_v9_diff.txt) |
| C2 | Queue / 所有权 / 死锁 | [memory_ownership.txt](../prompts/memory_ownership.txt) · [queue_event_bus.txt](../prompts/queue_event_bus.txt) · [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) |
| C3 | cJSON | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) |
| C4 | 音频 DMA / ISR | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) |
| C5 | 测试宏 | [test_mode_macro.txt](../prompts/test_mode_macro.txt) |
| C6 | SDK 裁剪 | [sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt) |
| 网络 | WSS / mbedTLS / 栈 | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) |
| Crash | 日志解读 | [crash_log_decode.txt](../prompts/crash_log_decode.txt) |
| 同步 | FreeRTOS 原语 | [freertos_sync_primitives.txt](../prompts/freertos_sync_primitives.txt) |

约束 ID 细则 → [constraint_detail.md](constraint_detail.md)

---

## 工具目录（完整版 · workflow 内调用）

| 用途 | 命令 |
|------|------|
| 一键 L2 | `python tools/run_review.py --dir src/ --platform xxx` |
| 自测 | `python tools/run_review.py --self-test` |
| 铁律范例约束 | `python tools/run_review.py --validate-examples` |
| Lite 同步 | `python scripts/sync_lite.py` · Windows：`.\scripts\sync_lite.cmd` |
| 迭代验证 | `python scripts/skill_iterate.py --check --sync` · Windows：`.\scripts\skill_iterate.cmd -Sync` |
| 安装 Cursor | `.\scripts\install_skill.ps1`（见 [INSTALL.md](../INSTALL.md)） |
| MVP 骨架 | `python tools/mvp_codegen_tool.py Module --platform jl -o ./generated` |

Checker 与 C#.# 映射 → [examples/README.md](../examples/README.md)

---

## 维护：改哪一层

```
改铁律/约束 ID     → core_rules.md + constraint_detail.md (+ 必要时 prompt 一句)
改场景深细节       → prompts/xxx.txt（检查 workflow 引用）
改步骤/输出格式    → workflows/xxx.md（检查 SKILL 路由表）
改平台事实         → platforms/xxx.md
改范例/checker     → examples/ + tools/fixtures/（跑 validate-examples）
改控制平面         → SKILL.md（保持 <100 行）+ skill_lite_body.md → sync
改 Skill 结构说明  → 本文件 + workflows/README.md + README.md
```

**禁止：** 拆多个 skill；未问卷扩 SDK 删除清单；手改 `freertos-skill-lite/` 正文。

---

## 完整版 vs Lite 结构差

| 层 | 完整版 | Lite |
|----|--------|------|
| L0 | SKILL.md | sync 生成 |
| L1 | 全部 workflow | l2 用 lite 子 workflow |
| L2–L3 | 同左 | 同左（无 examples 链接） |
| L4 | examples + tools | 用 lite_manual_checklist 替代 |
