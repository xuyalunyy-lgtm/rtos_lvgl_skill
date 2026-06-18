/*
 * @file good_media_format_contract.c
 * @brief C26 正例：统一音频格式、公式化帧长、正确 RGB565 stride、codec 生命周期独立。
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define MEDIA_SAMPLE_RATE_HZ      16000U
#define MEDIA_CHANNELS            1U
#define MEDIA_BITS_PER_SAMPLE     16U
#define MEDIA_FRAME_MS            20U
#define MEDIA_FRAME_SAMPLES       (MEDIA_SAMPLE_RATE_HZ * MEDIA_FRAME_MS / 1000U)

#define VIDEO_WIDTH               320U
#define VIDEO_HEIGHT              240U
#define VIDEO_PIXEL_FORMAT_RGB565 1U
#define VIDEO_BYTES_PER_PIXEL     2U
#define VIDEO_STRIDE_BYTES        (VIDEO_WIDTH * VIDEO_BYTES_PER_PIXEL)

typedef struct {
    uint32_t sample_rate_hz;
    uint8_t channels;
    uint8_t bits_per_sample;
    uint16_t frame_ms;
    uint16_t frame_samples;
} media_audio_format_t;

typedef struct {
    uint16_t width;
    uint16_t height;
    uint16_t stride_bytes;
    uint8_t pixel_format;
} media_video_format_t;

typedef struct {
    uint32_t format_mismatch_count;
    uint32_t codec_error_count;
    uint32_t max_encode_time_us;
    uint32_t last_frame_size;
} media_codec_stats_t;

static const media_audio_format_t k_audio_format = {
    .sample_rate_hz = MEDIA_SAMPLE_RATE_HZ,
    .channels = MEDIA_CHANNELS,
    .bits_per_sample = MEDIA_BITS_PER_SAMPLE,
    .frame_ms = MEDIA_FRAME_MS,
    .frame_samples = MEDIA_FRAME_SAMPLES,
};

static const media_video_format_t k_video_format = {
    .width = VIDEO_WIDTH,
    .height = VIDEO_HEIGHT,
    .stride_bytes = VIDEO_STRIDE_BYTES,
    .pixel_format = VIDEO_PIXEL_FORMAT_RGB565,
};

static media_codec_stats_t g_media_stats;
static void *g_opus_encoder;
static uint8_t g_encode_packet_pool[512];

extern void *opus_encoder_create(int sample_rate, int channels, int app, int *err);
extern int opus_encode(void *enc, const int16_t *pcm, int frame_size, uint8_t *out, int out_len);
extern void opus_encoder_destroy(void *enc);

static bool media_audio_format_match(const media_audio_format_t *a, const media_audio_format_t *b)
{
    return a->sample_rate_hz == b->sample_rate_hz &&
           a->channels == b->channels &&
           a->bits_per_sample == b->bits_per_sample &&
           a->frame_samples == b->frame_samples;
}

bool media_codec_open(const media_audio_format_t *i2s_format,
                      const media_audio_format_t *asr_format)
{
    if (!media_audio_format_match(i2s_format, &k_audio_format) ||
        !media_audio_format_match(asr_format, &k_audio_format)) {
        g_media_stats.format_mismatch_count++;
        return false;
    }

    int err = 0;
    g_opus_encoder = opus_encoder_create(
        (int)k_audio_format.sample_rate_hz,
        (int)k_audio_format.channels,
        0,
        &err);
    if (g_opus_encoder == NULL || err != 0) {
        g_media_stats.codec_error_count++;
        return false;
    }
    return true;
}

int media_encode_frame(const int16_t *pcm)
{
    int bytes = opus_encode(
        g_opus_encoder,
        pcm,
        (int)k_audio_format.frame_samples,
        g_encode_packet_pool,
        (int)sizeof(g_encode_packet_pool));
    if (bytes < 0) {
        g_media_stats.codec_error_count++;
        return bytes;
    }

    g_media_stats.last_frame_size = (uint32_t)bytes;
    return bytes;
}

void media_codec_close(void)
{
    if (g_opus_encoder != NULL) {
        opus_encoder_destroy(g_opus_encoder);
        g_opus_encoder = NULL;
    }
}

bool media_video_format_validate(void)
{
    return k_video_format.width == VIDEO_WIDTH &&
           k_video_format.height == VIDEO_HEIGHT &&
           k_video_format.stride_bytes >= VIDEO_WIDTH * VIDEO_BYTES_PER_PIXEL;
}
