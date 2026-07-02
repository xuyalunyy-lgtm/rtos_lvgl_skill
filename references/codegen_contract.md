# Codegen Contract — 代码生成契约

> 所有 L3 代码生成任务必须先声明生成契约，再生成代码，最后通过 codegen gate。

## 契约字段

生成前必须声明：

| 字段 | 必填 | 说明 |
|------|------|------|
| workflow | ✅ | 使用的 L3 workflow（l3_new_module / l3_bring_up / l3_sdk_trim） |
| platform | ✅ | 目标平台（esp32/stm32/zephyr/jl/bk） |
| frameworks | ✅ | 涉及框架（esp-idf/lvgl/mbedtls 等） |
| module_type | ✅ | 模块类型（driver/service/controller/ui） |
| tasks | ✅ | 要创建的任务列表（name/stack/priority/core） |
| queues | ✅ | 要创建的队列列表（name/depth/item_size/backpressure/timeout） |
| locks | ⬚ | 要创建的 mutex/semaphore |
| timers | ⬚ | 要创建的 software timer |
| constraints.required | ✅ | 必须满足的约束 ID（如 C1,C4,C29,C33） |
| constraints.forbidden | ⬚ | 禁止模式列表 |
| verification_commands | ✅ | 验证命令 |

## 禁止模式（默认）

生成代码不得包含以下模式，除非 manifest 中显式声明理由：

| 模式 | 约束 | 禁止场景 |
|------|------|----------|
| `portMAX_DELAY` 无理由 | C31 | 默认禁止，除非 `allowed_infinite_waits` 有 reason |
| ISR 中 blocking API | C4 | ISR/hot path 中 xQueueReceive、sem Take、vTaskDelay |
| ISR 中 malloc/free | C4 | ISR 中 pvPortMalloc、cJSON_Parse |
| ISR 中 printf/重日志 | C4 | ISR 中 ESP_LOGI、printf |
| queue 传栈指针 | C2 | xQueueSend 传局部变量地址 |
| queue 传 cJSON* | C3 | 直接传 cJSON 指针，应传序列化后的 buffer |
| queue 传裸 DMA 指针 | C28 | 应传 pool buffer handle |
| LVGL 跨线程调用 | C1 | 非 UI 任务中调用 lv_ 函数 |
| 只有 init 没有 stop | C33 | 缺少 deinit/stop 对称 |
| queue 无 backpressure | C37 | 深度 > 0 但无 drop/block/timeout 策略 |

## 生成后验证

1. 生成器输出 `generation_manifest.json`
2. `codegen_gate.py` 检查 manifest 完整性、文件存在、约束覆盖、禁止模式
3. `run_review.py` 检查生成代码质量
4. 失败则阻断交付，输出原因和对应约束
