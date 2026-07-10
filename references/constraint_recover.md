# Iron Rule Constraint Shard: Fault Recovery and Engineering Resilience (Recover)

This file contains constraints for backpressure and degradation strategies, fault isolation and automatic recovery, configuration matrix constraints, one-click reproduction closed-loop, and regression sample prioritization.

> Corresponding Constraint IDs: C37–C41
> Other Shards: [constraint_review.md](constraint_review.md) | [constraint_memory.md](constraint_memory.md) | [constraint_rtos.md](constraint_rtos.md) | [constraint_platform.md](constraint_platform.md) | [constraint_media.md](constraint_media.md) | [constraint_ota.md](constraint_ota.md) | [constraint_bluetooth_protocol.md](constraint_bluetooth_protocol.md)

---

## Severity Definition

| Level | Meaning | Handling |
|-------|---------|----------|
| P0 | Must crash / Must leak / Must deadlock | Block merge, MUST attach fix diff or example reference |
| P1 | High-probability mass production issue | MUST fix or register risk in this iteration |
| P2 | Maintainability / Testability | Recommended fix, can be scheduled |

---

## C37 — Backpressure and Degradation Strategies

| ID | Constraint | Severity | Validation | Good Example | Bad Example |
|----|-----------|----------|------------|--------------|-------------|
| C37.1 | High-frequency producer, network, audio/video, logging, UI queues MUST declare backpressure strategy | P0 | Manual | `drop-oldest + count` | Infinite wait on full queue |
| C37.2 | Full queue MUST NOT wait infinitely, MUST choose drop/coalesce/overwrite/backpressure | P0 | `blocking_wait_checker.py` + `efficiency_budget_checker.py` + Manual | `xQueueOverwrite` [QUEUE_OVERWRITE] for state-type events | `portMAX_DELAY` [TIMEOUT_FOREVER] waiting for consumption |
| C37.3 | Downsampling, frame rate reduction, bitrate reduction, pausing non-critical tasks MUST have trigger conditions | P1 | Manual | queue high-water > 80% reduce frame rate | Temporarily change delay when stuttering |
| C37.4 | retry MUST be bounded, with backoff or circuit breaker | P1 | `efficiency_budget_checker.py` + Manual | `retry<=5, backoff<=60s` | while retry forever |
| C37.5 | Backpressure, degradation, recovery MUST have low-frequency telemetry | P2 | Manual | `degrade_enter_count` | Degradation invisible on-site |

**Symptom Table**:

| Symptom | Possible Constraints |
|---------|---------------------|
| System freeze after queue full | C37.1/C37.2 backpressure strategy missing |
| CPU saturated by retries under poor network | C37.4 retry unbounded |
| Degradation occurs but nobody knows | C37.5 missing telemetry |

---

## C38 — 故障隔离与自动恢复

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C38.1 | 关键模块必须声明 task/driver/protocol/cloud/UI 故障域 | P0 | 人工 | WSS 断链不影响 LVGL task | 一个错误全局 reset |
| C38.2 | 错误必须分类 recoverable/fatal，并声明恢复动作 | P0 | 人工 | timeout reconnect, config fatal | 全部返回 `-1` |
| C38.3 | retry/backoff/max retry/circuit open time 必须有上限 | P1 | 人工 | exponential backoff capped | 无限重连 |
| C38.4 | supervisor/watchdog/health counter 必须能发现卡死或半死 | P1 | 人工 | task heartbeat + stale detect | 任务还活着但不处理事件 |
| C38.5 | 恢复失败必须进入降级模式或安全停机，而非静默失败 | P2 | 人工 | offline mode + UI status | 失败后继续假装在线 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 外设异常后只能整机重启 | C38.1/C38.2 故障域和恢复动作不清 |
| 任务未死但业务不动 | C38.4 缺 health counter |
| 重连风暴 | C38.3 缺 backoff/circuit breaker |

---

## C39 — 配置矩阵约束

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C39.1 | Kconfig、feature flag、board、SDK 差异必须进入配置矩阵 | P0 | 人工 | `feature -> dependency -> resource` 表 | 宏散落在业务代码 |
| C39.2 | 每个 feature 必须声明 dependency、resource、default、test mode | P0 | 人工 | camera 依赖 DMA+PSRAM | 打开宏后才发现缺资源 |
| C39.3 | `#ifdef` 必须归类 platform/board/feature/debug，禁止无名散落 | P1 | 人工 | `CONFIG_FEATURE_AUDIO` | `#ifdef TEMP_FIX` |
| C39.4 | 配置变化必须同步 bring-up checklist、profile 和回归样本 | P1 | 人工 | 新 feature 同步 profile | 改宏不改测试 |
| C39.5 | 无效配置组合必须在 build 或初始化阶段 fail fast | P2 | 人工 | `#error` / init config check | 运行到一半崩溃 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 某配置组合没人敢改 | C39.1/C39.2 缺矩阵 |
| `#ifdef` 越写越多 | C39.3 未归类 |
| 新板编译过但运行崩 | C39.5 无效组合未 fail fast |

---

## C40 — 一键复现闭环

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C40.1 | 新模块、bring-up、复杂 bug 必须提供 build/flash/monitor 命令 | P0 | 人工 | `idf.py build flash monitor` 模板 | 只说"本地能跑" |
| C40.2 | crash/core dump 解码必须声明 symbol path、工具和输入日志 | P0 | 人工 | `addr2line -e build/app.elf ...` | 只有截图 |
| C40.3 | 最小配置、测试入口、预期输出必须可复制执行 | P1 | 人工 | test mode + expected log | 需要口头步骤 |
| C40.4 | 失败日志保存位置、脱敏规则和保留时间必须明确 | P1 | 人工 + C14 | `logs/failure_xxx.txt` | 日志散在聊天里 |
| C40.5 | 复现命令必须随平台脚本或 SDK 版本变化更新 | P2 | 人工 | SDK 升级同步脚本 | 命令过期无人发现 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 新人半天跑不起来 | C40.1/C40.3 缺一键复现 |
| crash 地址没人能解 | C40.2 缺 symbol/decode |
| 现场日志无法复盘 | C40.4 缺保存和脱敏规则 |

---

## C41 — 回归样本优先

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C41.1 | 新约束、新 checker、新 bugfix 必须优先沉淀 bad 样本 | P0 | 人工/自测 | `bad_timeout_budget.c` | 只改规则无样本 |
| C41.2 | 每个 bad 样本必须有对应 good 样本或推荐修复模式 | P0 | 人工/自测 | good/bad 成对 | 只知道错不知道怎么改 |
| C41.3 | 样本必须通用化，不包含产品名、客户名、密钥或私有路径 | P1 | residue scan | generic fixture | 带客户业务名 |
| C41.4 | checker/self-test/manual checklist 必须引用样本并说明预期结果 | P1 | `run_review.py --self-test` | expected exit 1 | 样本未纳入验证 |
| C41.5 | 样本覆盖失败路径、边界条件和恢复路径，不只覆盖 happy path | P2 | 人工 | timeout + recovery | 只测成功路径 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 同类 bug 反复出现 | C41.1/C41.2 缺回归样本 |
| checker 改坏没人发现 | C41.4 未纳入 self-test |
| 样本不能公开复用 | C41.3 未通用化 |
