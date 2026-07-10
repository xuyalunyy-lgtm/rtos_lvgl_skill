# Iron Rule Constraint Shard: Memory Allocation and DMA Buffer (Memory)

This file contains constraints for general memory allocation optimization, media DMA/Cache/zero-copy Buffer lifecycle, data copy budget, etc.

> Corresponding constraint IDs: C7, C28, C36
> Other shards: [constraint_review.md](constraint_review.md) | [constraint_rtos.md](constraint_rtos.md) | [constraint_platform.md](constraint_platform.md) | [constraint_media.md](constraint_media.md) | [constraint_ota.md](constraint_ota.md) | [constraint_recover.md](constraint_recover.md)

---

## Severity Definitions

| Level | Meaning | Action |
|------|------|------|
| P0 | Will crash / will leak / will deadlock | Block merge, MUST attach fix diff or example reference |
| P1 | High probability production issue | MUST fix in this iteration or register risk |
| P2 | Maintainability / testability | Recommended fix, can be scheduled |

---

## C7 — Memory Allocation and Optimization (General)

| ID | Constraint | Severity | Validation | Good Example | Bad Example |
|----|------|--------|------|------|------|
| C7.1 | **Before** shrinking pool / stack / disabling module, MUST record baseline (heap low watermark, task stack watermark, Flash/RAM); without baseline, MUST NOT suggest specific numeric values | P0 | Process | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.2 | Optimization order: **First** fix leaks and ownership (C2/C3) → disable unused modules (C6) → shrink LwIP/TLS/LVGL pool → **Last** shrink task stack | P1 | Process | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.3 | Large buffers (>256B), certificate chains, JSON parse trees **MUST NOT** be placed on stack; MUST use heap allocation or static/object pool | P0 | Manual | — | — |
| C7.4 | Long-lived connections / high-frequency paths MUST prefer fixed block or object pool; MUST NOT `malloc` [HEAP_ALLOC]+`free` [HEAP_FREE] per frame / per packet | P1 | Manual | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.5 | WSS/TLS task stack MUST be measured at handshake peak, **MUST NOT be less than 4096 bytes** (recommended 6144–8192) | P0 | `stack_calculator.py` + Manual | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |
| C7.6 | Shrinking LwIP / mbedTLS / LVGL pool, **each step** MUST smoke test WiFi + WSS + business closed loop | P1 | Process | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | — |
| C7.7 | Main project MUST only link **one** TLS stack (choose one from mbedtls / wolfssl / psa) | P1 | Manual | — | — |
| C7.8 | ISR / DMA / real-time path buffers MUST be in SRAM (or fast RAM allowed by platform docs); MUST NOT default to PSRAM / external slow region without justification | P1 | Manual | `platforms/bk.md` etc. | — |
| C7.9 | Reconnection / error recovery MUST NOT use tight loop repeated TLS handshake; MUST use exponential backoff (cap recommended at 60s) | P1 | Manual | [good_wss_reconnect.c](../examples/good_wss_reconnect.c) | `bad_wss_blocking.c` |
| C7.10 | When platform supports external RAM/PSRAM and object is not DMA/ISR/real-time hot path, general heap allocation MUST **prefer external RAM**, fall back to internal SRAM on failure; allocator family / heap kind MUST be trackable to ensure matched free | P1 | Manual | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | Large cache defaults to occupying internal SRAM |
| C7.11 | Cross-module / cross-task objects MUST go through project-level unified allocator/free wrapper, uniformly handling external-first, DMA/internal classification, heap kind recording, failure logging, and matched free; business modules MUST NOT scatteredly directly call multi-family allocators | P1 | Manual | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | Business code mixes `malloc` / `psram_malloc` / `heap_caps_malloc` [HEAP_ALLOC] |
| C7.12 | Memory telemetry MUST collect free, minimum free, largest free block, alloc fail count by heap kind; only recording total free heap is insufficient to determine fragmentation and allocability | P1 | Manual | [l2_memory_analysis.md](../workflows/l2_memory_analysis.md) | Only printing `xPortGetFreeHeapSize()` |
| C7.13 | High-frequency / fixed-size objects MUST use boot-time pre-allocated fixed block pool or ring buffer, O(1) alloc/free, explicit drop/backpressure when full; MUST NOT expand at runtime or dynamically allocate per frame | P1 | Manual | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) | Per-packet `malloc/free`, temporary expansion when queue is full |

---

## C28 — Media DMA / Cache / Zero-Copy Buffer Lifecycle

| ID | Constraint | Severity | Validation | Good Example | Bad Example |
|----|------|--------|------|------|------|
| C28.1 | Camera/I2S/LCD/codec DMA buffer MUST be in DMA-capable memory and satisfy cache line or DMA controller alignment; MUST NOT use plain `malloc`/`pvPortMalloc` [HEAP_ALLOC] as media DMA buffer | P0 | `av_dma_buffer_checker.py` + Manual | [good_av_dma_buffer_lifecycle.c](../examples/good_av_dma_buffer_lifecycle.c) | [bad_av_dma_buffer_lifecycle.c](../examples/bad_av_dma_buffer_lifecycle.c) |
| C28.2 | Before DMA write and CPU read MUST invalidate; before CPU write and DMA/LCD/codec read MUST clean; wrong direction equals bad frame risk | P0 | `av_dma_buffer_checker.py` | Same as above | Same as above |
| C28.3 | Zero-copy frame pool MUST have owner/state/generation/release; producer MUST NOT reuse before consumer releases | P0 | `av_dma_buffer_checker.py` + Manual | Same as above | Same as above |
| C28.4 | Cross-task Queue SHOULD pass buffer index/handle/descriptor; MUST NOT pass raw DMA pointer across tasks and then have producer side continue read/write or reuse | P1 | `av_dma_buffer_checker.py` + Manual | Same as above | Same as above |
| C28.5 | cache clean/invalidate start address MUST be cache-line aligned downward, length MUST cover complete frame/stride/DMA half-buffer upward | P1 | `av_dma_buffer_checker.py` | Same as above | Same as above |
| C28.6 | MUST retain cache_clean/cache_invalidate, stale_frame, reuse_before_release, buffer_overrun/underrun telemetry, low-frequency output | P2 | Manual + checker reminder | Same as above | — |

**Symptom Table**:

| Symptom | Possible Constraints |
|------|----------|
| Camera preview occasional old frame / screen corruption | C28.2 invalidate missing or C28.5 range not covering stride |
| After LCD flush, color disorder / partial tearing | C28.2 clean missing, C28.1 buffer not in DMA-capable region |
| Zero-copy frame occasionally overwritten | C28.3 owner/generation missing, reuse before consumer release |
| After Queue full, bad frame or use-after-free | C28.4 raw pointer ownership unclear, C2.4 failure path not releasing |

---

## C36 — Data Copy Budget

| ID | Constraint | Severity | Validation | Good Example | Bad Example |
|----|------|--------|------|------|------|
| C36.1 | Cross-task, cross-core, DMA, network, audio/video frame MUST declare data movement strategy | P0 | Manual | Queue passes frame handle | Queue passes entire frame struct |
| C36.2 | Large payload MUST default to passing descriptor/index/handle, MUST NOT pass large struct into Queue without justification | P0 | `efficiency_budget_checker.py` + Manual + C2 | `frame_id` + pool owner | `xQueueSend(q, &frame, ...)` |
| C36.3 | Each data path MUST declare copy count, buffer owner, and release party | P1 | `efficiency_budget_checker.py` + Manual | `copy=1 producer alloc consumer release` | Multiple memcpy without knowing who releases |
| C36.4 | DMA/cache path MUST declare clean/invalidate, alignment, and ownership transfer | P1 | Manual + C28 | cache line aligned clean before TX | DMA reads cache dirty data |
| C36.5 | Buffer pool when full MUST have drop/backpressure/retry strategy and counting | P2 | `efficiency_budget_checker.py` + Manual | `pool_full_drop++` | malloc expansion when pool is full |

**Symptom Table**:

| Symptom | Possible Constraints |
|------|----------|
| Audio/video latency increases over time | C36.2/C36.5 excessive copying or no strategy when pool is full |
| DMA screen corruption / old frame | C36.4 cache/owner not declared |
| Heap fragmentation worsening | C36.1/C36.3 no budget for runtime copying and allocation |
