# Workflow: L2 内存专项分析

**触发：** 内存不足、堆持续下降、栈溢出、缩池/缩栈需求、OOM 复位、内存优化专项。

<thinking>
1. 内存问题是最常见的嵌入式量产杀手——必须先有基线数据，再谈优化
2. 遵循 C7.1：无基线禁止给具体数值建议
3. 遵循 C7.2：先修泄漏 → 关未用模块 → 缩池 → 最后缩栈
4. 静态分析（stack_calculator）+ 运行时采集（watermark/heap）交叉验证
</thinking>

## Step 0 — 基线采集（必做，不可跳过）

**铁律（C7.1）：无基线数据，Agent 禁止给出任何具体数值的优化建议。**

### 0.1 堆基线

在用户源码中添加采集点，或指导用户执行：

```c
/* 在 app_main 末尾、各任务启动后、业务稳定运行 30s 后分别采集 */
void memory_dump_baseline(const char *stage)
{
    LOG_I(TAG, "=== Memory Baseline: %s ===", stage);
    LOG_I(TAG, "  Free heap: %u bytes", xPortGetFreeHeapSize());
    LOG_I(TAG, "  Min free heap: %u bytes", xPortGetMinimumEverFreeHeapSize());

#if CONFIG_SPIRAM
    LOG_I(TAG, "  Free PSRAM: %u bytes",
          heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
#endif

#if CONFIG_FREERTOS_USE_TRACE_FACILITY
    /* 逐任务栈 watermark */
    TaskStatus_t *tasks;
    uint32_t count = uxTaskGetNumberOfTasks();
    tasks = pvPortMalloc(count * sizeof(TaskStatus_t));
    if (tasks != NULL) {
        count = uxTaskGetSystemState(tasks, count, NULL);
        for (uint32_t i = 0; i < count; i++) {
            LOG_I(TAG, "  Task[%s] stack watermark: %u bytes",
                  tasks[i].pcTaskName,
                  tasks[i].usStackHighWaterMark * sizeof(StackType_t));
        }
        vPortFree(tasks);
    }
#endif
}
```

### 0.2 基线采集时机

| 时机 | 采集内容 | 目的 |
|------|----------|------|
| **冷启动后** | 堆总量、各任务初始 watermark | 系统开销基线 |
| **WiFi 连接后** | 堆变化 | 协议栈开销 |
| **WSS 握手峰值** | 堆最低水位 | TLS 握手栈/堆需求（C7.5） |
| **业务稳定 30s** | 堆最低水位 + 各任务 watermark | 业务开销基线 |
| **连续运行 30min** | 堆最低水位趋势 | 泄漏检测 |

### 0.3 基线记录模板

```markdown
## 内存基线

### 堆
| 时机 | Free Heap | Min Free Heap | Free PSRAM |
|------|-----------|---------------|------------|
| 冷启动 | __ B | __ B | __ B |
| WiFi 连接后 | __ B | __ B | __ B |
| WSS 握手峰值 | __ B | __ B | __ B |
| 业务稳定 30s | __ B | __ B | __ B |
| 连续 30min | __ B | __ B | __ B |

### 任务栈（按 watermark 升序排列）
| 任务名 | 栈大小 | Watermark | 使用率 | 状态 |
|--------|--------|-----------|--------|------|
| __ | __ B | __ B | __% | ✅ 充裕 / 🟡 偏紧 / 🔴 危险 |

### Flash
- 应用固件：__ / __ bytes（__%）
- NVS：__ / __ bytes
```

---

## Step 1 — 泄漏排查（最高优先级）

**C7.2 顺序：先修泄漏，再谈优化。**

### 1.1 cJSON 泄漏（C3）

```bash
python tools/cjson_leak_checker.py --dir ./src --platform <平台>
```

常见泄漏模式：
- `cJSON_Parse` 后 early return 无 `cJSON_Delete`（C3.1/C3.2）
- 循环内 Parse 不 Delete（C3.4）
- `strdup` 失败路径泄漏 root（C3.5）

### 1.2 Queue payload 泄漏（C2）

```bash
python tools/queue_ownership_checker.py --dir ./src
```

常见问题：
- `xQueueSend` 失败时未释放 payload（C2.4）
- Presenter 收到 payload 后未 `vPortFree`（C2.3）
- `cJSON*` 或栈指针进 Queue（C2.1/C2.2）

### 1.3 通用资源泄漏

| 资源类型 | 检查方法 |
|----------|----------|
| Task handle | `xTaskCreate` 后是否有 `vTaskDelete` 路径 |
| Semaphore/Mutex | 是否有 `vSemaphoreDelete` 路径 |
| Timer | 是否有 `xTimerStop` + `xTimerDelete` 路径（C16.2） |
| Socket/FD | `close()` 是否覆盖所有 error path（C12.4） |
| LVGL async | `lv_async_call` 的 `user_data` 是否在回调内 free（C1.3） |

### 1.4 泄漏检测运行时方法

```c
/* 周期性打印堆水位，观察趋势 */
static void heap_monitor_task(void *arg)
{
    (void)arg;
    size_t prev = xPortGetFreeHeapSize();
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(10000));
        size_t cur = xPortGetFreeHeapSize();
        int32_t diff = (int32_t)cur - (int32_t)prev;
        LOG_I(TAG, "Heap: %u (delta: %+d)", cur, diff);
        if (diff < -100) {
            LOG_W(TAG, "Possible leak! Heap dropping %d bytes/10s", -diff);
        }
        prev = cur;
    }
}
```

---

## Step 2 — 未用模块关闭（C6）

**C7.2 第二步：关未用模块，释放 Flash + RAM。**

走 [l3_sdk_trim.md](l3_sdk_trim.md) 或增量问卷：

```markdown
## 模块关闭候选

| 模块 | 当前状态 | 是否使用 | 关闭后释放 |
|------|----------|----------|-----------|
| BT/BLE | 开启 | 否 | ~100KB RAM |
| OTA | 开启 | 否 | ~20KB Flash |
| HTTP Server | 开启 | 否 | ~30KB Flash |
| mDNS | 开启 | 否 | ~15KB Flash |
| 多余 log level | INFO | WARN 即可 | ~5KB Flash |
| LVGL demo | 开启 | 否 | ~50KB Flash |
```

关闭后重新采集基线（Step 0），对比释放量。

---

## Step 3 — 堆/池优化

### 3.1 LwIP 池优化

```c
/* sdkconfig 或 Kconfig 调整 */
CONFIG_LWIP_MAX_SOCKETS=4          /* 默认 10，按实际需要 */
CONFIG_LWIP_TCP_MSS=1024           /* 默认 1460，缩到 1024 节省 ~4KB */
CONFIG_LWIP_TCP_SND_BUF=4096       /* 默认 5744 */
CONFIG_LWIP_TCP_WND=4096           /* 默认 5744 */
```

**C7.6：每步缩完必须冒烟 WiFi + WSS + 业务闭环。**

### 3.2 mbedTLS 池优化

```c
/* 仅保留需要的 cipher suite */
CONFIG_MBEDTLS_SSL_MAX_CONTENT_LEN=4096  /* 默认 16384 */
CONFIG_MBEDTLS_KEY_EXCHANGE_ECDHE_RSA=y
CONFIG_MBEDTLS_KEY_EXCHANGE_ECDHE_ECDSA=y
/* 关闭不需要的 */
CONFIG_MBEDTLS_KEY_EXCHANGE_DHE_RSA=n
CONFIG_MBEDTLS_KEY_EXCHANGE_RSA=n
```

### 3.3 LVGL 内存池

```c
CONFIG_LV_MEM_CUSTOM=y                   /* 使用自定义分配器 */
CONFIG_LV_MEM_CUSTOM_ALLOC=heap_caps_malloc  /* 放 PSRAM */
CONFIG_LV_MEM_SIZE=0                     /* 使用系统堆 */
```

### 3.4 对象池（高频路径）

```c
/* 高频分配/释放路径（如每帧 JSON 或每包网络数据）用固定块池 */
#define POOL_BLOCK_SIZE  256
#define POOL_BLOCK_COUNT 8

static uint8_t s_pool[POOL_BLOCK_COUNT][POOL_BLOCK_SIZE] __attribute__((aligned(4)));
static StaticQueue_t s_pool_queue;
static QueueHandle_t s_pool_free_queue;

void pool_init(void)
{
    s_pool_free_queue = xQueueCreateStatic(POOL_BLOCK_COUNT, sizeof(void *), (uint8_t *)&s_pool_queue + sizeof(QueueHandle_t), /* ... */);
    for (int i = 0; i < POOL_BLOCK_COUNT; i++) {
        void *p = &s_pool[i][0];
        xQueueSend(s_pool_free_queue, &p, 0);
    }
}
```

---

## Step 4 — 栈优化（最后一步）

**C7.2：栈优化是最后手段，缩栈前必须有 watermark 基线。**

### 4.1 栈计算器评估

```bash
python tools/stack_calculator.py --describe "WSS TLS cJSON" --platform <平台>
```

### 4.2 栈缩减策略

| 任务 | 当前栈 | Watermark | 可缩至 | 备注 |
|------|--------|-----------|--------|------|
| WSS | 6144 B | 1200 B | 4096 B | TLS 握手峰值，不可低于 4096（C7.5） |
| LVGL | 8192 B | 3000 B | 6144 B | 大屏刷新峰值 |
| Presenter | 3072 B | 1800 B | 2048 B | 逻辑简单 |

### 4.3 栈缩减冒烟

**每缩一个任务，必须冒烟验证：**
1. 该任务正常运行（无 stack overflow）
2. 该任务的高负载路径正常（如 WSS 断线重连、LVGL 全屏刷新）
3. `uxTaskGetStackHighWaterMark` > 200 bytes（留 20% 余量）

---

## Step 5 — 冒烟验证（缩完后）

```markdown
## 内存优化冒烟验证

### 优化前后对比
| 指标 | 优化前 | 优化后 | 变化 |
|------|--------|--------|------|
| 堆最低水位 | __ B | __ B | +__ B |
| 最紧任务 watermark | __ B (__ task) | __ B (__ task) | +__ B |
| Flash 占用 | __ KB | __ KB | -__ KB |

### 冒烟 checklist
- [ ] WiFi 连接 + WSS 握手 + 业务闭环
- [ ] 连续 10 轮语音交互无异常
- [ ] 无 stack overflow / WDT / HardFault
- [ ] 堆水位无持续下降
- [ ] 断网重连正常
```

---

## Step 6 — 输出

```markdown
## 内存分析报告

### 基线（Step 0）
（基线记录表）

### 泄漏排查（Step 1）
- [ ] cJSON：无泄漏 / 已修复（C3）
- [ ] Queue payload：无泄漏 / 已修复（C2）
- [ ] 其他资源：无泄漏 / 已修复

### 模块关闭（Step 2）
- 关闭模块：____
- 释放：__ KB Flash / __ KB RAM

### 堆/池优化（Step 3）
- LwIP：____
- mbedTLS：____
- LVGL：____

### 栈优化（Step 4）
| 任务 | 原栈 | 新栈 | watermark |
|------|------|------|-----------|
| __ | __ B | __ B | __ B |

### 最终基线
（冒烟后采集）

### 优化总结
- 堆释放：__ bytes
- Flash 释放：__ bytes
- 最紧任务栈余量：__ bytes（__%）
```

---

## 与其他 Workflow 的关系

| 前置 | 后续 | 联动 |
|------|------|------|
| **l2_code_review** | 本 workflow | Review 发现 C2/C3/C7 问题后走内存分析 |
| **l3_bring_up** | 本 workflow | Bring-up 采集的基线是分析输入 |
| 本 workflow | **l3_sdk_trim** | 关未用模块（Step 2） |
| 本 workflow | **debug_crash** | 栈溢出 → crash 诊断 |