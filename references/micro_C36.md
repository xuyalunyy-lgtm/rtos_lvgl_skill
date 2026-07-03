# C36 拷贝预算微分片

> ~800 tokens。完整规则见 `constraint_memory.md`。

## 典型症状

- 热路径延迟高
- CPU 利用率异常
- 内存抖动

## 危险模式

```c
// ❌ 热路径中多次拷贝
void audio_task(void *arg) {
    while (1) {
        buf = malloc(size);        // 分配
        memcpy(buf, src, size);    // 拷贝
        xQueueSend(q, buf, ...);   // 入队（又拷贝）
        free(buf);                 // 释放
    }
}
```

## 修复规则

1. 热路径禁止 malloc/free
2. 用零拷贝传递指针
3. 减少 memcpy 次数
4. 预分配 buffer pool

## 零拷贝模式

```c
// ✅ 传递指针，不拷贝数据
typedef struct { void *data; size_t len; } msg_t;
msg_t msg = { .data = pre_allocated_buf, .len = size };
xQueueSend(q, &msg, 0);  // 只拷贝指针，不拷贝数据
```

## 相关 Checker

- `efficiency_budget_checker.py` — 自动检测

## 升级到完整 Shard

需要背压策略、队列满处理、DMA 零拷贝细节时 → 加载 `constraint_memory.md`
