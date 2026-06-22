/**
 * @file good_av_dma_buffer_lifecycle.c
 * @brief C28 正例：DMA-capable 对齐帧池、cache clean/invalidate、零拷贝 owner 生命周期和遥测。
 */

#include <stdbool.h>
#include <stdint.h>

#define CACHE_LINE_SIZE 32U
#define MEDIA_DMA_POOL_COUNT 3U
#define VIDEO_FRAME_BYTES (320U * 240U * 2U)
#define DMA_ALIGNED __attribute__((aligned(CACHE_LINE_SIZE)))
#define DMA_CAPABLE __attribute__((section(".dma_sram")))

typedef enum {
    MEDIA_BUF_FREE = 0,
    MEDIA_BUF_DMA_RX,
    MEDIA_BUF_CPU_OWNED,
    MEDIA_BUF_QUEUED,
    MEDIA_BUF_DISPLAY,
} media_buf_owner_t;

typedef struct {
    uint8_t *addr;
    uint32_t bytes;
    uint32_t seq;
    uint32_t generation;
    media_buf_owner_t owner;
} media_dma_buffer_t;

typedef struct {
    uint32_t cache_clean_count;
    uint32_t cache_invalidate_count;
    uint32_t stale_frame_count;
    uint32_t reuse_before_release_count;
    uint32_t buffer_overrun_count;
} media_dma_stats_t;

static DMA_ALIGNED DMA_CAPABLE uint8_t s_camera_pool[MEDIA_DMA_POOL_COUNT][VIDEO_FRAME_BYTES];
static media_dma_buffer_t s_camera_buffers[MEDIA_DMA_POOL_COUNT];
static media_dma_stats_t g_media_dma_stats;

static uintptr_t cache_align_down(uintptr_t value)
{
    return value & ~(uintptr_t)(CACHE_LINE_SIZE - 1U);
}

static uint32_t cache_align_up_size(uintptr_t aligned_addr, const void *ptr, uint32_t bytes)
{
    uintptr_t start = (uintptr_t)ptr;
    uintptr_t end = start + bytes;
    uintptr_t aligned_end = (end + CACHE_LINE_SIZE - 1U) & ~(uintptr_t)(CACHE_LINE_SIZE - 1U);
    return (uint32_t)(aligned_end - aligned_addr);
}

static void media_cache_invalidate_after_dma(void *ptr, uint32_t bytes)
{
    uintptr_t aligned_addr = cache_align_down((uintptr_t)ptr);
    uint32_t aligned_bytes = cache_align_up_size(aligned_addr, ptr, bytes);
    SCB_InvalidateDCache_by_Addr((void *)aligned_addr, aligned_bytes);
    g_media_dma_stats.cache_invalidate_count++;
}

static void media_cache_clean_before_dma(void *ptr, uint32_t bytes)
{
    uintptr_t aligned_addr = cache_align_down((uintptr_t)ptr);
    uint32_t aligned_bytes = cache_align_up_size(aligned_addr, ptr, bytes);
    SCB_CleanDCache_by_Addr((void *)aligned_addr, aligned_bytes);
    g_media_dma_stats.cache_clean_count++;
}

void media_dma_pool_init(void)
{
    for (uint32_t i = 0; i < MEDIA_DMA_POOL_COUNT; i++) {
        s_camera_buffers[i].addr = s_camera_pool[i];
        s_camera_buffers[i].bytes = VIDEO_FRAME_BYTES;
        s_camera_buffers[i].seq = 0U;
        s_camera_buffers[i].generation = 1U;
        s_camera_buffers[i].owner = MEDIA_BUF_FREE;
    }
}

bool media_camera_prepare_rx(uint8_t index)
{
    if (index >= MEDIA_DMA_POOL_COUNT) {
        return false;
    }
    media_dma_buffer_t *buf = &s_camera_buffers[index];
    if (buf->owner != MEDIA_BUF_FREE) {
        g_media_dma_stats.reuse_before_release_count++;
        return false;
    }
    buf->owner = MEDIA_BUF_DMA_RX;
    camera_dma_start(buf->addr, buf->bytes);
    return true;
}

void media_camera_rx_done_callback(uint8_t index)
{
    if (index >= MEDIA_DMA_POOL_COUNT) {
        return;
    }
    media_dma_buffer_t *buf = &s_camera_buffers[index];
    media_cache_invalidate_after_dma(buf->addr, buf->bytes);
    buf->seq++;
    buf->owner = MEDIA_BUF_CPU_OWNED;
}

bool media_queue_frame(void *queue, uint8_t index)
{
    if (index >= MEDIA_DMA_POOL_COUNT) {
        return false;
    }
    media_dma_buffer_t *buf = &s_camera_buffers[index];
    if (buf->owner != MEDIA_BUF_CPU_OWNED) {
        g_media_dma_stats.stale_frame_count++;
        return false;
    }
    buf->owner = MEDIA_BUF_QUEUED;
    return xQueueSend(queue, &index, 0) == pdTRUE;
}

bool media_lcd_submit(uint8_t index)
{
    if (index >= MEDIA_DMA_POOL_COUNT) {
        return false;
    }
    media_dma_buffer_t *buf = &s_camera_buffers[index];
    if (buf->owner != MEDIA_BUF_QUEUED) {
        g_media_dma_stats.stale_frame_count++;
        return false;
    }
    media_cache_clean_before_dma(buf->addr, buf->bytes);
    buf->owner = MEDIA_BUF_DISPLAY;
    lcd_dma_start_transfer(buf->addr, buf->bytes);
    return true;
}

void media_display_flush_done(uint8_t index)
{
    if (index >= MEDIA_DMA_POOL_COUNT) {
        return;
    }
    media_dma_buffer_t *buf = &s_camera_buffers[index];
    buf->generation++;
    buf->owner = MEDIA_BUF_FREE;
}
