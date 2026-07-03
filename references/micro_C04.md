# C04 ISR/DMA 安全微分片

> ~800 tokens。完整规则见 `constraint_review.md`。

## 典型症状

- HardFault 在中断上下文
- ISR 中 printf 导致死锁
- ISR 中 malloc 导致堆损坏

## 危险模式

```c
// ❌ ISR 中阻塞
void GPIO_IRQHandler(void) {
    xSemaphoreTake(mutex, portMAX_DELAY);  // 禁止！
    printf("GPIO interrupt\n");             // 禁止！
    pvPortMalloc(100);                      // 禁止！
}
```

## ISR 安全 API

| 操作 | 禁止 | 允许 |
|---|---|---|
| 信号量 | xSemaphoreTake/Give | xSemaphoreGiveFromISR |
| 队列 | xQueueSend/Receive | xQueueSendFromISR |
| 延时 | vTaskDelay | 无（ISR 不延时） |
| 内存 | malloc/pvPortMalloc | 无（ISR 不分配） |
| 日志 | printf/ESP_LOGI | 无（ISR 不打印） |

## 相关 Checker

- `isr_safety_checker.py` — 自动检测

## 升级到完整 Shard

需要 DMA buffer 对齐、ISR 嵌套优先级、portYIELD_FROM_ISR 细节时 → 加载 `constraint_review.md`
