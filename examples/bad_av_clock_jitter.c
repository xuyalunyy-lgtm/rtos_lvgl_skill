/*
 * @file bad_av_clock_jitter.c
 * @brief C27 反例：无主时钟、无水位、无界漂移校正、按 drift 硬等、underrun 路径分配和打印。
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define JITTER_QUEUE_LEN 64U

typedef void *QueueHandle_t;
typedef uint32_t TickType_t;

#define portMAX_DELAY ((TickType_t)0xffffffffUL)
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms))

typedef struct {
    uint32_t pts_ms;
    uint8_t *payload;
} video_frame_t;

typedef struct {
    uint32_t pts_ms;
    int16_t *pcm;
} audio_frame_t;

extern TickType_t xTaskGetTickCount(void);
extern void vTaskDelay(TickType_t ticks);
extern int xQueueReceive(QueueHandle_t queue, void *out, TickType_t ticks_to_wait);
extern void *pvPortMalloc(size_t size);
extern void vPortFree(void *ptr);
extern void resampler_set_rate(float ratio);
extern uint32_t audio_now_ms(void);

static QueueHandle_t g_jitter_queue;

void bad_jitter_buffer_pop(audio_frame_t *audio)
{
    if (!xQueueReceive(g_jitter_queue, audio, portMAX_DELAY)) {
        audio->pcm = pvPortMalloc(640);
        printf("audio underrun\n");
        memset(audio->pcm, 0, 640);
    }
}

void bad_av_render_frame(video_frame_t *video)
{
    video->pts_ms = xTaskGetTickCount();
    int32_t drift_error_ms = (int32_t)video->pts_ms - (int32_t)audio_now_ms();

    resampler_set_rate(1.0f + ((float)drift_error_ms / 1000.0f));
    if (drift_error_ms > 0) {
        vTaskDelay(pdMS_TO_TICKS((uint32_t)drift_error_ms));
    }

    printf("render drift=%ld\n", (long)drift_error_ms);
}

void bad_overrun_handler(audio_frame_t *audio)
{
    printf("jitter overrun\n");
    vPortFree(audio->pcm);
}
