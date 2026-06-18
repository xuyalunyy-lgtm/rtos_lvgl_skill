/*
 * @file good_av_pipeline_sync.c
 * @brief C25 正例：audio clock master、带 PTS/seq 的帧、有界 ring、callback 隔离。
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

#define AV_VIDEO_QUEUE_DEPTH 4
#define AV_LATE_DROP_MS 45U

typedef struct {
    uint8_t *data;          /* owner: video pool, released by av_video_release() */
    size_t len;
    uint32_t pts_ms;
    uint32_t seq;
    uint16_t duration_ms;
} av_video_frame_t;

typedef struct {
    int16_t *pcm;           /* owner: audio pool, released by audio_frame_release() */
    size_t sample_count;
    uint32_t pts_ms;
    uint32_t seq;
    uint16_t duration_ms;
} av_audio_frame_t;

typedef struct {
    uint32_t dropped_frames;
    uint32_t late_frames;
    uint32_t audio_underrun;
    int32_t av_drift_ms;
} av_pipeline_stats_t;

static QueueHandle_t g_video_q;
static TaskHandle_t g_camera_task;
static av_pipeline_stats_t g_av_stats;
static uint32_t g_video_seq;

extern uint32_t audio_clock_get_pts_ms(void);
extern bool camera_dma_take_frame(av_video_frame_t *frame);
extern void av_video_release(av_video_frame_t *frame);
extern void render_video_frame(const av_video_frame_t *frame);

void camera_frame_isr(void)
{
    BaseType_t hp_task_woken = pdFALSE;

    vTaskNotifyGiveFromISR(g_camera_task, &hp_task_woken);
    portYIELD_FROM_ISR(hp_task_woken);
}

static void video_drop_oldest(void)
{
    av_video_frame_t old_frame;

    if (xQueueReceive(g_video_q, &old_frame, 0) == pdTRUE) {
        av_video_release(&old_frame);
        g_av_stats.dropped_frames++;
    }
}

static bool video_enqueue_frame(const av_video_frame_t *frame)
{
    if (xQueueSend(g_video_q, frame, 0) == pdTRUE) {
        return true;
    }

    video_drop_oldest();
    return xQueueSend(g_video_q, frame, 0) == pdTRUE;
}

void camera_capture_task(void *arg)
{
    (void)arg;

    for (;;) {
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(20));

        av_video_frame_t frame;
        if (!camera_dma_take_frame(&frame)) {
            continue;
        }

        frame.seq = g_video_seq++;
        frame.duration_ms = 33;
        if (!video_enqueue_frame(&frame)) {
            av_video_release(&frame);
            g_av_stats.dropped_frames++;
        }
    }
}

void av_sync_task(void *arg)
{
    (void)arg;

    for (;;) {
        av_video_frame_t frame;
        if (xQueueReceive(g_video_q, &frame, pdMS_TO_TICKS(5)) != pdTRUE) {
            continue;
        }

        uint32_t audio_clock_ms = audio_clock_get_pts_ms();
        g_av_stats.av_drift_ms = (int32_t)frame.pts_ms - (int32_t)audio_clock_ms;

        if (frame.pts_ms + AV_LATE_DROP_MS < audio_clock_ms) {
            g_av_stats.late_frames++;
            av_video_release(&frame);
            continue;
        }

        render_video_frame(&frame);
        av_video_release(&frame);
    }
}
