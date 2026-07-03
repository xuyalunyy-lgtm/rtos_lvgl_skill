# C28 DMA/Cache 微分片

> ~1000 tokens。完整规则见 `constraint_memory.md`。

## 典型症状

- 花屏/坏帧
- DMA 传输数据不一致
- cache 脏数据

## 危险模式

```c
// ❌ DMA 写入后未 clean cache
dma_write(buf, size);
// CPU 读取 buf 时可能读到旧数据！

// ❌ DMA 读取后未 invalidate cache
dma_read(buf, size);
// CPU 读取 buf 时可能读到 cache 中的旧数据！
```

## Cache 操作规则

| 场景 | 操作 |
|---|---|
| CPU 写 → DMA 读 | cache clean (writeback) |
| DMA 写 → CPU 读 | cache invalidate |
| 双向 | clean + invalidate |

## DMA Buffer 规则

1. 必须用 MALLOC_CAP_DMA 分配
2. 必须 cache line 对齐（通常 32 bytes）
3. 不得与 CPU 共享未同步

## 相关 Checker

- `av_dma_buffer_checker.py` — 自动检测

## 升级到完整 Shard

需要 zero-copy 帧池、PSRAM DMA、多核 cache 一致性细节时 → 加载 `constraint_memory.md`
