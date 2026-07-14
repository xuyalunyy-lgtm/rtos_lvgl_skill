// Edge case: Hot path with correct static/pool allocation
// Tests that hotpath_checker does not false-positive on static buffers
#include "FreeRTOS.h"
#include "task.h"
#include <stdint.h>
#include <string.h>

// Static buffer — no malloc in hot path
static uint8_t frame_buffer[2048];
static volatile uint32_t frame_count = 0;

// LVGL flush callback — uses static buffer, no malloc/printf
static void my_lvgl_flush(void *disp, const void *area, uint8_t *px_map)
{
    // Copy to static buffer (no malloc)
    size_t len = 1024;  // simplified
    if (len <= sizeof(frame_buffer)) {
        memcpy(frame_buffer, px_map, len);
    }
    frame_count++;

    // Notify render task (lightweight)
    static TaskHandle_t render_handle;
    if (render_handle) {
        xTaskNotifyGive(render_handle);
    }
}

// Timer callback — only sets flag, no heavy work
static volatile int timer_flag = 0;
static void my_timer_cb(void *timer)
{
    (void)timer;
    timer_flag = 1;
}

// Audio callback — uses pool index, no malloc
#define POOL_SIZE 4
static uint8_t audio_pool[POOL_SIZE][1024];
static volatile int pool_idx = 0;

static void audio_dma_callback(void)
{
    int idx = pool_idx;
    pool_idx = (pool_idx + 1) % POOL_SIZE;
    // Only index manipulation, no allocation
    (void)audio_pool[idx];
}
