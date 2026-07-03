# 铁律约束分片：内存分配与 DMA 缓冲（Memory）

本文件包含通用内存分配优化、媒体 DMA/Cache/零拷贝 Buffer 生命周期、数据拷贝预算等约束。

> 对应约束 ID：C7, C28, C36
> 其他分片：[constraint_review.md](constraint_review.md) | [constraint_rtos.md](constraint_rtos.md) | [constraint_platform.md](constraint_platform.md) | [constraint_media.md](constraint_media.md) | [constraint_ota.md](constraint_ota.md) | [constraint_recover.md](constraint_recover.md)

---

## 严重度定义

| 级别 | 含义 | 处理 |
|------|------|------|
| P0 | 必崩 / 必泄漏 / 必死锁 | 阻塞合并，须附修复 diff 或范例引用 |
| P1 | 高概率量产问题 | 本迭代必须修复或登记风险 |
| P2 | 可维护性 / 可测试性 | 建议修复，可排期 |

---

## C7 — 内存分配与优化（通用）

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C7.1 | 缩池 / 缩栈 / 关模块**前**须记录基线（堆最低水位、任务 stack watermark、Flash/RAM）；无基线禁止给具体数值建议 | P0 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.2 | 优化顺序：**先**修泄漏与所有权（C2/C3）→ 关未用模块（C6）→ 缩 LwIP/TLS/LVGL 池 → **最后**缩任务栈 | P1 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.3 | 大 buffer（>256B）、证书链、JSON 解析树**禁止**放栈上；须堆分配或静态/对象池 | P0 | 人工 | — | — |
| C7.4 | 长连接 / 高频路径优先固定块或对象池；禁止每帧 / 每包 `malloc` [HEAP_ALLOC]+`free` [HEAP_FREE] | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.5 | WSS/TLS 任务栈须按握手峰值实测，**不得低于 4096 bytes**（建议 6144–8192） | P0 | `stack_calculator.py` + 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |
| C7.6 | 缩 LwIP / mbedTLS / LVGL 池**每步**须冒烟 WiFi + WSS + 业务闭环 | P1 | 流程 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.7 | 主工程只链入**一个** TLS 栈（mbedtls / wolfssl / psa 择一） | P1 | 人工 | — | — |
| C7.8 | ISR / DMA / 实时路径缓冲须在 SRAM（或平台文档允许的 fast RAM）；禁止无依据默认放 PSRAM / 外部慢速区 | P1 | 人工 | `platforms/bk.md` 等 | — |
| C7.9 | 重连 / 错误恢复禁止 tight loop 反复 TLS 握手；须指数退避（cap 建议 60s） | P1 | 人工 | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |
| C7.10 | 普通堆申请在平台支持外部 RAM/PSRAM 且对象非 DMA/ISR/实时热路径时，须**优先外部 RAM**，失败再回退 internal SRAM；allocator family / heap kind 须可追踪以保证 matched free | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | 大缓存默认占用 internal SRAM |
| C7.11 | 跨模块 / 跨任务对象须经项目级统一 allocator/free 封装，统一处理 external-first、DMA/internal 分类、heap kind 记录、失败日志和 matched free；业务模块禁止散落直接调用多族 allocator | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | 业务代码混用 `malloc` / `psram_malloc` / `heap_caps_malloc` [HEAP_ALLOC] |
| C7.12 | 内存遥测须按 heap kind 采集 free、minimum free、largest free block、alloc fail 计数；仅记录总 free heap 不足以判断碎片和可分配性 | P1 | 人工 | [l2_memory_analysis.md](../workflows/l2_memory_analysis.md) | 只打印 `xPortGetFreeHeapSize()` |
| C7.13 | 高频 / 固定尺寸对象须使用启动期预分配固定块池或 ring buffer，O(1) alloc/free，满时明确 drop/backpressure；禁止运行期扩容或每帧动态分配 | P1 | 人工 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | 每包 `malloc/free`，队列满后临时扩容 |

---

## C28 — 媒体 DMA / Cache / 零拷贝 Buffer 生命周期

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C28.1 | Camera/I2S/LCD/codec DMA buffer 必须位于 DMA-capable 内存，并满足 cache line 或 DMA 控制器对齐；禁止普通 `malloc`/`pvPortMalloc` [HEAP_ALLOC] 作为媒体 DMA buffer | P0 | `av_dma_buffer_checker.py` + 人工 | [good_av_dma_buffer_lifecycle.c](../examples/good_av_dma_buffer_lifecycle.c) | [bad_av_dma_buffer_lifecycle.c](../examples/bad_av_dma_buffer_lifecycle.c) |
| C28.2 | DMA 写、CPU 读前必须 invalidate；CPU 写、DMA/LCD/codec 读前必须 clean；方向错等同坏帧风险 | P0 | `av_dma_buffer_checker.py` | 同上 | 同上 |
| C28.3 | 零拷贝 frame pool 必须有 owner/state/generation/release；consumer 未 release 前禁止 producer 复用 | P0 | `av_dma_buffer_checker.py` + 人工 | 同上 | 同上 |
| C28.4 | 跨任务 Queue 推荐传 buffer index/handle/descriptor；禁止裸 DMA 指针跨任务后 producer 侧继续读写或复用 | P1 | `av_dma_buffer_checker.py` + 人工 | 同上 | 同上 |
| C28.5 | cache clean/invalidate 起始地址向下 cache-line 对齐，长度向上覆盖完整 frame/stride/DMA half-buffer | P1 | `av_dma_buffer_checker.py` | 同上 | 同上 |
| C28.6 | 保留 cache_clean/cache_invalidate、stale_frame、reuse_before_release、buffer_overrun/underrun 等遥测，低频输出 | P2 | 人工 + checker 提醒 | 同上 | — |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| Camera preview 偶发旧帧 / 花屏 | C28.2 invalidate 缺失或 C28.5 范围未覆盖 stride |
| LCD flush 后颜色错乱 / 局部撕裂 | C28.2 clean 缺失，C28.1 buffer 不在 DMA-capable 区域 |
| 零拷贝帧偶发被覆盖 | C28.3 owner/generation 缺失，consumer 未 release 前复用 |
| Queue 满后坏帧或 use-after-free | C28.4 裸指针所有权不清，C2.4 失败路径未释放 |

---

## C36 — 数据拷贝预算

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C36.1 | 跨 task、跨核、DMA、网络、音视频 frame 必须声明数据移动策略 | P0 | 人工 | Queue 传 frame handle | Queue 传整帧结构体 |
| C36.2 | 大 payload 默认传 descriptor/index/handle，禁止无理由传大结构体进 Queue | P0 | `efficiency_budget_checker.py` + 人工 + C2 | `frame_id` + pool owner | `xQueueSend(q, &frame, ...)` |
| C36.3 | 每条数据路径必须声明 copy count、buffer owner 和 release 方 | P1 | `efficiency_budget_checker.py` + 人工 | `copy=1 producer alloc consumer release` | 多处 memcpy 不知道谁释放 |
| C36.4 | DMA/cache 路径必须声明 clean/invalidate、对齐和 ownership transfer | P1 | 人工 + C28 | cache line aligned clean before TX | DMA 读 cache 脏数据 |
| C36.5 | buffer pool 满时必须有 drop/backpressure/retry 策略和计数 | P2 | `efficiency_budget_checker.py` + 人工 | `pool_full_drop++` | 满池后 malloc 扩容 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 音视频延迟随时间增加 | C36.2/C36.5 拷贝过多或满池无策略 |
| DMA 花屏/旧帧 | C36.4 cache/owner 未声明 |
| 堆碎片越来越严重 | C36.1/C36.3 运行期拷贝和分配无预算 |
