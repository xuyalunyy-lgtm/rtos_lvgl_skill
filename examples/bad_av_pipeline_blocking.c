/*
 * @file bad_av_pipeline_blocking.c
 * @brief C25 反例：camera callback 里直接 UI/codec/log/阻塞队列，帧缺少 PTS/seq。
 */

#include <stddef.h>
#include <stdint.h>

#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

typedef struct {
    uint8_t *data;
    size_t len;
} bad_video_frame_t;

static QueueHandle_t g_video_q;
static QueueHandle_t g_audio_q;
static void *g_preview_img;

extern void lv_img_set_src(void *obj, const void *src);
extern void video_decode_h264(uint8_t *data, size_t len);
extern void render_next_video_frame(void);

void camera_frame_callback(uint8_t *buf, size_t len)
{
    bad_video_frame_t frame = {
        .data = buf,
        .len = len,
    };

    lv_img_set_src(g_preview_img, buf);
    video_decode_h264(buf, len);
    printf("camera frame len=%u\n", (unsigned)len);
    xQueueSend(g_video_q, &frame, portMAX_DELAY);
}

void audio_process_frame(const int16_t *pcm, size_t samples)
{
    int16_t *copy = pvPortMalloc(samples * sizeof(int16_t));

    memcpy(copy, pcm, samples * sizeof(int16_t));
    printf("audio samples=%u\n", (unsigned)samples);
    xQueueSend(g_audio_q, &copy, portMAX_DELAY);
}

void av_render_task(void *arg)
{
    (void)arg;

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(33));
        render_next_video_frame();
    }
}
