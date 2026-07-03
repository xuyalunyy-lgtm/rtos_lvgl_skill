# C31 超时预算微分片

> ~800 tokens。完整规则见 `constraint_rtos.md`。

## 典型症状

- WDT 复位
- 任务永久阻塞
- 系统无响应

## 危险模式

```c
// ❌ 永久等待
xSemaphoreTake(mutex, portMAX_DELAY);
xQueueReceive(queue, &item, portMAX_DELAY);
// 如果信号量/队列永远不就绪 → WDT 复位
```

## 修复规则

1. 所有等待必须有有限超时
2. 超时值必须有依据（不是随意数字）
3. 超时后必须有错误处理
4. 网络操作必须有 SO_RCVTIMEO

## 推荐超时值

| 场景 | 推荐超时 |
|---|---|
| 队列接收 | 100-1000ms |
| 信号量 | 100-5000ms |
| 网络 recv | 5-30s |
| TLS 握手 | 10-30s |

## 相关 Checker

- `blocking_wait_checker.py` — 自动检测

## 升级到完整 Shard

需要阻塞预算表、优先级反转防护、死锁检测细节时 → 加载 `constraint_rtos.md`
