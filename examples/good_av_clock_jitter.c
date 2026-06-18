/*
 * @file good_av_clock_jitter.c
 * @brief C27 正例：audio clock master、有界 jitter buffer、漂移限幅、underrun 补静音与遥测。
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define AV_MASTER_CLOCK_AUDIO       1U
#define AV_TIMEBASE_US              1000000LL
#define AV_AUDIO_SAMPLE_RATE_HZ     16000U
#define AV_AUDIO_FRAME_MS           20U
#define AV_AUDIO_FRAME_SAMPLES      (AV_AUDIO_SAMPLE_RATE_HZ * AV_AUDIO_FRAME_MS / 1000U)
#define AV_AUDIO_FRAME_DURATION_US  (AV_AUDIO_FRAME_MS * 1000U)
#define AV_VIDEO_FRAME_DURATION_US  33333U

#define AV_JITTER_CAPACITY_FRAMES   8U
#define AV_JITTER_LOW_WATERMARK     2U
#define AV_JITTER_HIGH_WATERMARK    6U
#define AV_TARGET_DELAY_MS          80U
#define AV_DRIFT_PPM_LIMIT          500
#define AV_VIDEO_DROP_THRESHOLD_US  45000
#define AV_VIDEO_HOLD_THRESHOLD_US  20000

typedef struct {
    int64_t pts_us;
    uint32_t seq;
    uint32_t duration_us;
    uint16_t sample_count;
    uint32_t owner;
    int16_t pcm[AV_AUDIO_FRAME_SAMPLES];
} av_audio_frame_t;

typedef struct {
    int64_t pts_us;
    uint32_t seq;
    uint32_t duration_us;
    uint32_t owner;
    const uint8_t *data;
} av_video_frame_t;

typedef struct {
    int32_t drift_ms;
    int32_t drift_ppm;
    uint8_t jitter_depth;
    uint8_t jitter_low_water;
    uint8_t jitter_high_water;
    uint32_t underrun_count;
    uint32_t overrun_count;
    uint32_t late_frame_count;
    uint32_t dropped_frame_count;
    uint32_t inserted_silence_count;
    uint32_t resync_count;
} av_clock_stats_t;

typedef enum {
    AV_RENDER_NOW = 0,
    AV_RENDER_DROP,
    AV_RENDER_HOLD_LAST,
} av_render_decision_t;

static av_audio_frame_t g_audio_jitter_ring[AV_JITTER_CAPACITY_FRAMES];
static uint8_t g_audio_jitter_head;
static uint8_t g_audio_jitter_tail;
static uint8_t g_audio_jitter_depth;
static av_clock_stats_t g_av_clock_stats = {
    .jitter_low_water = AV_JITTER_LOW_WATERMARK,
    .jitter_high_water = AV_JITTER_HIGH_WATERMARK,
};

static int32_t av_sync_clamp_ppm(int32_t ppm)
{
    if (ppm > AV_DRIFT_PPM_LIMIT) {
        return AV_DRIFT_PPM_LIMIT;
    }
    if (ppm < -AV_DRIFT_PPM_LIMIT) {
        return -AV_DRIFT_PPM_LIMIT;
    }
    return ppm;
}

static int64_t av_audio_clock_pts_us(uint64_t rendered_samples)
{
    return (int64_t)((rendered_samples * AV_TIMEBASE_US) / AV_AUDIO_SAMPLE_RATE_HZ);
}

static int32_t av_sync_calc_drift_ms(int64_t video_pts_us, int64_t audio_pts_us)
{
    return (int32_t)((video_pts_us - audio_pts_us) / 1000);
}

static int32_t av_sync_update_drift_ppm(int32_t drift_ms, int32_t window_ms)
{
    int32_t ppm = 0;
    if (window_ms > 0) {
        ppm = (drift_ms * 1000) / window_ms;
    }
    ppm = av_sync_clamp_ppm(ppm);
    g_av_clock_stats.drift_ms = drift_ms;
    g_av_clock_stats.drift_ppm = ppm;
    return ppm;
}

bool av_jitter_buffer_push(const av_audio_frame_t *frame)
{
    if (g_audio_jitter_depth >= AV_JITTER_HIGH_WATERMARK) {
        g_audio_jitter_tail = (uint8_t)((g_audio_jitter_tail + 1U) % AV_JITTER_CAPACITY_FRAMES);
        g_audio_jitter_depth--;
        g_av_clock_stats.overrun_count++;
        g_av_clock_stats.dropped_frame_count++;
    }

    g_audio_jitter_ring[g_audio_jitter_head] = *frame;
    g_audio_jitter_head = (uint8_t)((g_audio_jitter_head + 1U) % AV_JITTER_CAPACITY_FRAMES);
    g_audio_jitter_depth++;
    g_av_clock_stats.jitter_depth = g_audio_jitter_depth;
    return true;
}

bool av_jitter_buffer_pop(av_audio_frame_t *out)
{
    if (g_audio_jitter_depth == 0U) {
        memset(out, 0, sizeof(*out));
        out->duration_us = AV_AUDIO_FRAME_DURATION_US;
        out->sample_count = AV_AUDIO_FRAME_SAMPLES;
        g_av_clock_stats.underrun_count++;
        g_av_clock_stats.inserted_silence_count++;
        return false;
    }

    *out = g_audio_jitter_ring[g_audio_jitter_tail];
    g_audio_jitter_tail = (uint8_t)((g_audio_jitter_tail + 1U) % AV_JITTER_CAPACITY_FRAMES);
    g_audio_jitter_depth--;
    g_av_clock_stats.jitter_depth = g_audio_jitter_depth;
    return true;
}

av_render_decision_t av_sync_video_decide(const av_video_frame_t *video,
                                          uint64_t rendered_audio_samples)
{
    int64_t audio_pts_us = av_audio_clock_pts_us(rendered_audio_samples);
    int32_t drift_ms = av_sync_calc_drift_ms(video->pts_us, audio_pts_us);
    (void)av_sync_update_drift_ppm(drift_ms, AV_TARGET_DELAY_MS);

    int64_t drift_us = video->pts_us - audio_pts_us;
    if (drift_us < -AV_VIDEO_DROP_THRESHOLD_US) {
        g_av_clock_stats.late_frame_count++;
        g_av_clock_stats.dropped_frame_count++;
        return AV_RENDER_DROP;
    }
    if (drift_us > AV_VIDEO_HOLD_THRESHOLD_US) {
        return AV_RENDER_HOLD_LAST;
    }
    return AV_RENDER_NOW;
}

void av_sync_resync_if_needed(int32_t drift_ms)
{
    if (drift_ms > AV_TARGET_DELAY_MS || drift_ms < -(int32_t)AV_TARGET_DELAY_MS) {
        g_av_clock_stats.resync_count++;
        g_audio_jitter_head = 0U;
        g_audio_jitter_tail = 0U;
        g_audio_jitter_depth = 0U;
        g_av_clock_stats.jitter_depth = 0U;
    }
}
