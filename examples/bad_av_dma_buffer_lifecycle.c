/**
 * @file bad_av_dma_buffer_lifecycle.c
 * @brief C28 反例：普通堆 DMA buffer、cache 方向错误、裸指针进 Queue、回调内过早复用。
 */

#include <stdint.h>

#define VIDEO_FRAME_BYTES (320U * 240U * 2U)

static uint8_t *s_dma_buf;
static void *g_video_queue;

void media_camera_start_bad(void)
{
    s_dma_buf = (uint8_t *)pvPortMalloc(VIDEO_FRAME_BYTES);
    camera_dma_start(s_dma_buf, VIDEO_FRAME_BYTES);
}

void media_camera_rx_done_callback_bad(void)
{
    video_decode_rgb565(s_dma_buf, VIDEO_FRAME_BYTES);
    xQueueSend(g_video_queue, &s_dma_buf, portMAX_DELAY);
    camera_dma_start(s_dma_buf, VIDEO_FRAME_BYTES);
}

void media_lcd_submit_bad(void)
{
    SCB_InvalidateDCache_by_Addr(s_dma_buf, VIDEO_FRAME_BYTES);
    lcd_dma_start_transfer(s_dma_buf, VIDEO_FRAME_BYTES);
}
