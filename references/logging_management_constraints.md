# Logging Management Constraints (C14)

Used for L2/L3 review of logging architecture, production profiles, field observability, and crash post-mortem capability. For basic writing conventions, see [logging_debug.txt](../prompts/logging_debug.txt); for fine-grained IDs, see [constraint_detail.md](constraint_detail.md).

---

## Objectives

The logging system must simultaneously satisfy:

- **Diagnosable**: In the field, traces can be linked by event_id, module, state, error code, and seq/generation.
- **Controllable Overhead**: Hot paths must not flood output; UART/flash/network uploads must not drag down real-time tasks.
- **Releasable**: Production profiles default to WARN/ERROR, with no sensitive fields or verbose logs.
- **Post-mortem Capable**: After a crash, the most recent critical logs can be dumped, not just the last panic line.

---

## Profile 分层

| Profile | 默认级别 | 允许内容 | 禁止 |
|---------|----------|----------|------|
| Debug | DEBUG/VERBOSE | 开发现场、详细状态、一次性 dump | 明文密码/token、ISR 阻塞日志 |
| Release | INFO/WARN | 关键状态变化、错误码、性能摘要 | 高频 DEBUG、全量 payload |
| Production | WARN/ERROR | 异常、降级、crash 摘要、计数器 | verbose、敏感字段、默认远程全量上传 |

Profile 必须来自 Kconfig / build config / runtime policy，禁止业务代码里散落 `#ifdef DEBUG` 魔法开关。

---

## TAG 与级别

每个模块必须有稳定 TAG，建议 3–12 个字符：

```c
#define TAG "WSS"
LOG_W(TAG, "evt=WSS_RETRY state=%d err=%d delay_ms=%u", state, err, delay_ms);
```

级别约定：

| 级别 | 用途 | 示例 |
|------|------|------|
| ERROR | 功能失败、不可自动恢复、crash 前摘要 | TLS 证书校验失败 |
| WARN | 降级、重试、丢帧、背压、水位异常 | WSS retry / queue full |
| INFO | 低频生命周期与状态变化 | boot done / connected |
| DEBUG | 开发期细节，默认量产关闭 | packet len / parser branch |

禁止用 INFO 打循环心跳、per-frame、per-packet 细节。

---

## 上下文安全

| 上下文 | 允许 | 禁止 |
|--------|------|------|
| ISR / DMA callback | 递增计数、置 flag、notify | `printf`、阻塞 LOG、flash 写、网络上传 |
| audio/video hot path | 计数器、状态变化限频日志 | per-sample/per-frame 日志 |
| LVGL timer loop | 低频异常计数 | 每 tick 打印 |
| 网络回调 | 非阻塞日志、事件投递 | 持锁打印大 payload |
| 普通任务 | 分级日志、批量 flush | 无界字符串拼接、无限重试上传 |

如果必须观察 ISR/hot path，先记录 counter / last_err / timestamp，在普通任务中限频输出。

---

## 限频与预算

高频日志必须满足至少一项：

- 状态变化触发：只有 state / err / generation 改变时打印。
- 限频：同一 TAG + event_id 至少 1s 或更长间隔。
- 聚合：周期性输出 counter、水位、last_err，而不是每次打印。
- 编译期关闭：DEBUG/VERBOSE 在 release/profile 中被裁掉。

建议日志预算：

```markdown
| 模块 | Debug | Release | Production |
|------|-------|---------|------------|
| WSS | INFO + retry DEBUG | INFO/WARN | WARN/ERROR |
| Audio | 水位摘要 1Hz | WARN/ERROR | ERROR + counters |
| UI | 状态变化 | WARN | ERROR |
```

---

## 结构化事件

关键链路日志必须可机器检索，至少包含：

- `evt=` 稳定事件 ID
- `state=` 当前状态
- `err=` 平台/协议错误码
- `seq=` / `generation=` / `session=` 用于跨任务关联
- `task=` 或 tick/uptime，用于定位上下文

推荐格式：

```c
LOG_W(TAG, "evt=WSS_RETRY state=%d err=%d seq=%u delay_ms=%u",
      state, err, seq, delay_ms);
```

反例：

```c
LOG_E(TAG, "failed");
LOG_I(TAG, "data: %s", payload);
```

---

## 敏感数据

禁止日志输出：

- 密码、token、secret、private key、完整鉴权头
- 完整 URL query 中的 credential
- 音频原始内容、用户隐私文本、完整云端响应

允许输出脱敏摘要：

- token 前 4 位 + hash / length
- payload 长度、JSON type、错误码
- audio peak/rms、frame count，而不是原始样本

---

## Crash Ring Buffer

系统应有最近日志 ring buffer，用于 HardFault / WDT / assert 时 dump：

| 约束 | 要求 |
|------|------|
| 有界 | 固定条数或固定字节数，启动期分配 |
| 非阻塞 | ISR 不写 flash，不等待锁；必要时只记 counter |
| 分级 | ring 至少保留 WARN/ERROR，Debug profile 可保留 INFO |
| 可 dump | crash handler 输出 PC/LR/寄存器 + 最近 N 条事件 |
| 可清理 | reboot 后不会无限增长或破坏 NVS/Flash 寿命 |

持久化 crash 日志时，写 flash 必须放在安全任务或下次 boot 阶段，不能在异常上下文长时间阻塞。

---

## 远程上传

远程日志上传只允许在明确开关打开时启用，并满足：

- 有速率限制和每日/每会话配额。
- 敏感字段在本地脱敏后再上传。
- 网络差时降级为本地 ring，不允许阻塞业务或 tight loop 重传。
- 上传失败只记录 counter + last_err，不打印或缓存无限 payload。

---

## 审查清单

- [ ] 每模块有稳定 TAG 和可配置日志级别。
- [ ] Debug / Release / Production profile 明确，量产默认 WARN/ERROR。
- [ ] ISR、DMA、LVGL timer、音视频热路径没有阻塞日志。
- [ ] 高频日志已限频、状态变化触发或计数聚合。
- [ ] 关键链路有 event_id、state、err、seq/generation。
- [ ] token/password/audio 原始内容等敏感数据不入日志。
- [ ] crash ring buffer 有界、可 dump、不会在异常上下文阻塞写 flash。
- [ ] 远程日志有开关、配额、脱敏和失败降级策略。
