/*
 * @file bad_media_format_mismatch.c
 * @brief C26 反例：音频格式不一致、帧长 magic、RGB565 stride 错、每帧创建 codec。
 */

#include <stddef.h>
#include <stdint.h>

#define I2S_SAMPLE_RATE_HZ       48000U
#define AEC_SAMPLE_RATE_HZ       16000U
#define ASR_SAMPLE_RATE_HZ       16000U
#define I2S_CHANNELS             2U
#define ASR_CHANNELS             1U
#define PCM_BITS_PER_SAMPLE      16U
#define ENCODER_BITS_PER_SAMPLE  24U
#define AUDIO_FRAME_MS           20U
#define AUDIO_FRAME_SAMPLES      512U

#define VIDEO_WIDTH              320U
#define VIDEO_HEIGHT             240U
#define VIDEO_PIXEL_FORMAT_RGB565 1U
#define VIDEO_STRIDE_BYTES       320U

typedef struct {
    uint16_t width;
    uint16_t height;
    uint16_t stride_bytes;
    uint8_t *data;
} bad_video_frame_t;

extern void *opus_encoder_create(int sample_rate, int channels, int app, int *err);
extern int opus_encode(void *enc, const int16_t *pcm, int frame_size, uint8_t *out, int out_len);
extern void opus_encoder_destroy(void *enc);

int audio_encode_frame(const int16_t *pcm)
{
    int err = 0;
    void *encoder = opus_encoder_create(16000, 1, 0, &err);
    uint8_t *packet = pvPortMalloc(4096);

    printf("encode frame samples=%u\n", AUDIO_FRAME_SAMPLES);
    int bytes = opus_encode(encoder, pcm, AUDIO_FRAME_SAMPLES, packet, 4096);
    opus_encoder_destroy(encoder);
    vPortFree(packet);
    return bytes;
}

void video_convert_frame(bad_video_frame_t *frame)
{
    uint8_t *line = malloc(VIDEO_STRIDE_BYTES);

    printf("convert %ux%u\n", frame->width, frame->height);
    memcpy(line, frame->data, VIDEO_STRIDE_BYTES);
    free(line);
}
