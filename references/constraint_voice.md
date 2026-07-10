# 铁律约束分片：语音采集与 ASR（Voice）

本文件包含语音采集、云端 ASR、AEC 回声消除、uplink 上行等约束。

> 对应约束 ID：C10
> 其他分片：[constraint_review.md](constraint_review.md) | [constraint_memory.md](constraint_memory.md) | [constraint_rtos.md](constraint_rtos.md) | [constraint_platform.md](constraint_platform.md) | [constraint_media.md](constraint_media.md) | [constraint_ota.md](constraint_ota.md) | [constraint_recover.md](constraint_recover.md) | [constraint_bluetooth_protocol.md](constraint_bluetooth_protocol.md)

---

## 严重度定义

| 级别 | 含义 | 处理 |
|------|------|------|
| P0 | 必崩 / 必泄漏 / 必死锁 | 阻塞合并，须附修复 diff 或范例引用 |
| P1 | 高概率量产问题 | 本迭代必须修复或登记风险 |
| P2 | 可维护性 / 可测试性 | 建议修复，可排期 |

---

## C10 — 语音采集 / ASR / Uplink

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C10.1 | Prompt/TTS 播放结束后**必须** detach 播放路径（释放 AEC 参考路径），再开麦上行 | P0 | 人工 | [good_voice_prompt_uplink.c](../examples/good_voice_prompt_uplink.c) | TTS 结束后未 detach → AEC 参考路径污染 → 第二轮 peak 塌陷 |
| C10.2 | AEC settle 完成前**禁止**开始 ASR 上行（典型 settle 80–150ms） | P0 | 人工 | 同上 | TTS 结束立即开麦 → AEC 未收敛 → ASR 空 |
| C10.3 | 语音状态机必须互斥：`IDLE` / `CAPTURE` / `SPEAKER` 三态，旧 TTS chunk 在 capture pending/running 时**必须**丢弃 | P1 | 人工 | 同上 | capture 中收到旧 TTS chunk → 播放路径被重新 attach |
| C10.4 | Uplink frame index 必须单调递增；WSS send task 不得被 TTS/JSON 处理阻塞 | P1 | 人工 | 同上 | uplink frame 不增长但 WSS connected |
| C10.5 | 第二轮语音 peak 必须与第一轮同量级；如果下降，优先检查播放路径释放和 AEC 参考路径 | P0 | 人工 | 同上 | 第二轮 peak 从万级降到百级 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| ASR 返回空结果 / 没听清 | C10.1/C10.2 播放路径未释放或 AEC 未收敛 |
| 第二轮语音 peak 塌陷 | C10.1 未 detach 播放路径 |
| uplink frame 不增长 | C10.4 WSS send 被阻塞 |
| 录音失效但 peak>0 | C10.3 状态机未互斥 |

> 详细提示词：[voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt)
