# C07 内存分配微分片

> ~1000 tokens。完整规则见 `constraint_memory.md`。

## 典型症状

- 堆持续下降
- malloc 返回 NULL 导致崩溃
- PSRAM 分配但 DMA 无法访问

## 危险模式

```c
// ❌ 未检查返回值
char *buf = pvPortMalloc(size);
memcpy(buf, data, size);  // NULL 解引用！

// ❌ PSRAM 用于 DMA
char *dma_buf = heap_caps_malloc(sz, MALLOC_CAP_SPIRAM);
i2s_write(dma_buf);  // DMA 无法访问 PSRAM！
```

## ESP32 堆分区

| 用途 | API | 标志 |
|---|---|---|
| 通用 | heap_caps_malloc | MALLOC_CAP_8BIT |
| DMA | heap_caps_malloc | MALLOC_CAP_DMA |
| PSRAM | heap_caps_malloc | MALLOC_CAP_SPIRAM |

## 修复规则

1. malloc 后必须检查 NULL
2. DMA buffer 用 MALLOC_CAP_DMA
3. PSRAM 用于大块非实时数据
4. free 必须与 malloc 配对

## 相关 Checker

- `stack_alloc_checker.py` — 栈分配检查
- `efficiency_budget_checker.py` — 拷贝预算

## 升级到完整 Shard

需要池分配、外部 RAM 优先策略、allocator 封装细节时 → 加载 `constraint_memory.md`
