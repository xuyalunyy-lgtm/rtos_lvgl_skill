# Framework Conflict Matrix

> 框架间冲突管理。当项目同时使用多个框架时，以下冲突需要特别注意。

## 冲突矩阵

| Framework A | Framework B | 冲突类型 | 严重度 | 缓解方案 |
|-------------|-------------|----------|--------|----------|
| LVGL | mbedTLS | 资源竞争 | P1 | LVGL render task 和 TLS 握手不应在同一任务；mbedTLS 握手栈 ≥6KB |
| FatFS | LVGL | 时序冲突 | P1 | Flash 写入可能阻塞数百毫秒，不要在 UI 任务中写文件 |
| mbedTLS | ESP-IDF | 堆冲突 | P1 | mbedTLS 使用大量堆，PSRAM 分配需确认 DMA 兼容性 |
| lwIP | LVGL | 任务模型 | P2 | lwIP 回调在 lwIP 任务中，禁止直接调用 LVGL API |
| STM32 HAL | CMSIS-RTOS | API 不兼容 | P0 | 禁止 HAL_Delay，必须用 osDelay；IRQ callback 中禁止 RTOS API |
| TinyUSB | 任意 | 阻塞 IO | P1 | USB callback 中禁止阻塞，buffer 必须在 callback 返回前有效 |
| FatFS | Audio | 时序冲突 | P1 | Flash 写入可能阻塞实时音频路径，需用独立任务 |
| lwIP | mbedTLS | 堆/栈 | P1 | TLS 握手需要大栈（≥6KB）和大量堆，需在 budget 中预留 |

## 使用方法

1. 运行 `framework_profile.py --dir src` 检测项目使用的框架
2. 如果检测到冲突组合，在审查报告中列出
3. 根据缓解方案调整任务拓扑、栈大小、优先级

## 注意事项

- 冲突矩阵不是禁止组合，而是提醒需要额外设计
- 同一项目使用多个框架是常见场景，关键是正确隔离
- 优先级、栈大小、超时配置需要整体考虑
