# Iron Rule Constraint Shard: Key Security and OTA Updates (OTA)

This file contains constraints for key/credential/repo hygiene, OTA/firmware upgrade safety, and peripheral shutdown safety.

> Corresponding constraint IDs: C9, C22, C24
> Other shards:[constraint_review.md](constraint_review.md) | [constraint_memory.md](constraint_memory.md) | [constraint_rtos.md](constraint_rtos.md) | [constraint_platform.md](constraint_platform.md) | [constraint_media.md](constraint_media.md) | [constraint_recover.md](constraint_recover.md)

---

## Severity Definitions

| Level | Meaning | Handling |
|-------|---------|----------|
| P0 | Guaranteed crash / leak / deadlock | Blocks merge; MUST attach fix diff or example reference |
| P1 | High-probability production issue | MUST fix this iteration or register risk |
| P2 | Maintainability / testability | Recommended fix, can be scheduled |

---

## C9 — Key / Credential / Repo Hygiene

| ID | Constraint | Severity | Validation | Good Example | Bad Example |
|----|-----------|----------|------------|--------------|-------------|
| C9.1 | `CONFIG_*SECRET*` / `*PASSWORD*` / `*TOKEN*` / `*API_KEY*` **MUST NOT** write non-empty values to committed config | P0 | `secret_scan_checker.py` | `config.secrets` + `config.secrets.example` | Plaintext sdkconfig |
| C9.2 | Git remote URL **MUST NOT** embed `user:pass@` / token | P0 | `secret_scan_checker.py --git-remotes` | SSH remote | HTTPS + token |
| C9.3 | Runtime logs **MUST NOT** print WiFi passwords, RTC tokens, or full auth headers | P1 | Manual + grep | Sanitized logs | Plaintext LOGI |
| C9.4 | Key files MUST be `.gitignore`d (`config.secrets`, `config.local`, `.env`) | P1 | Manual | Project `.gitignore` | — |
| C9.5 | Build MUST support `config.secrets` local override (`CONFIG_SUBSTITUTE_FILE` or equivalent) | P2 | Process | `merge_config_secrets.sh` | Manual menuconfig only |
| C9.6 | L2 engineering review MUST scan `projects/**/config` and `--git-remotes` | P2 | `run_review.py --scan-secrets` | — | — |

---

## C22 — OTA / 固件升级安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C22.1 | OTA 镜像必须经过签名验证后才能写入 Flash；版本降级必须拒绝 | P0 | `ota_safety_checker.py` | [good_ota_update.c](../examples/good_ota_update.c) | [bad_ota_no_rollback.c](../examples/bad_ota_no_rollback.c) |
| C22.2 | OTA 升级后首次启动必须调用 `mark_valid_cancel_rollback()` [OTA_MARK_VALID]；失败必须可回滚到旧固件 | P0 | `ota_safety_checker.py` | 同上 | 同上 |
| C22.3 | OTA 产品分区表必须含 `ota_0` + `ota_1`；NVS 分区不可删除 | P1 | 人工 | [ota_update_safety.txt](../prompts/ota_update_safety.txt) | — |
| C22.4 | OTA 断电恢复：新固件写入非活动分区，断电后旧固件仍可运行；禁止擦除当前运行分区 | P0 | 人工 | 同上 | 同上 |
| C22.5 | OTA HTTP 下载必须有连接超时和读取超时；重试必须有上限和退避 | P1 | `ota_safety_checker.py` | 同上 | 同上 |
| C22.6 | 差分升级必须校验 patch 完整性，失败必须能回退到全量升级 | P2 | 人工 | — | — |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| OTA 后设备变砖 | C22.1 未验证签名，C22.4 覆盖了当前分区 |
| OTA 后重启回滚到旧固件 | C22.2 未调用 mark_valid_cancel_rollback |
| OTA 下载卡死不超时 | C22.5 HTTP 无超时配置 |
| OTA 反复重试不放弃 | C22.5 重试无上限 |
| 分区表缺少 ota_1 | C22.3 分区表不完整 |

---

## C24 — 外设关闭安全（硬件收尾）

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C24.1 | 异常退出路径必须与正常完成路径调用相同的收尾函数（goto cleanup） | P0 | 人工 | [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) | 异常 return 跳过收尾 |
| C24.2 | 外设 stop 函数必须可重入（有状态检查） | P1 | 人工 | `if (!s_enabled) return;` | 无状态检查重复关闭 |
| C24.3 | abort/timeout/skip 路径必须释放所有硬件资源 | P0 | 人工 | `goto cleanup` 统一收尾 | 超时直接 return |
| C24.4 | 外设 stop/deinit 前必须等待 DMA/任务 idle；音频/媒体链路须区分 `idle` 与 `deinit/free` | P1 | 人工 | `while (dma_is_busy())` / `stop_playback` 只进 idle | DMA 传输中关闭 / speaker stop 释放 capture backend |
| C24.5 | 执行器停止后必须关闭加热/电源门控/外设使能 | P0 | 人工 | `actuator_stop_motion()` → `peripheral_power_disable()` | 只停执行器不关电源 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 执行器停转但加热/电源门控仍开启 | C24.5 收尾不完整 |
| 异常后外设未关闭 | C24.1 异常路径未收尾 |
| 重复调用 stop 出错 | C24.2 不可重入 |
| 超时后硬件仍在运行 | C24.3 超时路径未释放 |
| 关闭时 DMA 报错 | C24.4 未等待 DMA 完成 |
| 停 speaker 后 MIC 不工作 | C24.4 shared backend 被错误 deinit/free |
