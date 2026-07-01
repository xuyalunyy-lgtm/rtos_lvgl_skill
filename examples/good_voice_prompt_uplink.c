/**
 * @file good_voice_prompt_uplink.c
 * @brief C10 正例：prompt 结束 detach + AEC settle + 再开 uplink（示意，非可编译单元）
 *
 * 场景：共享 mic+spk engine，唤醒「叮」后云端 ASR。
 * 约束：C10.1 detach · C10.2 settle · C10.4 串行 · C10.5 generation · C10.6 动态 slot id
 *
 * 平台映射（勿在本文件硬编码产品名）→ platforms/bk.md / jl.md / esp32.md
 */

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    void *audio;
    int playback_slot_id;
    bool playback_attached;
    void (*on_done)(void *user);
    void *user_data;
} prompt_tone_t;

typedef struct {
    prompt_tone_t *prompt;
    void *audio;
    uint32_t capture_gen;
} voice_session_t;

/* --- platform stubs (rename in product code) --- */
extern void audio_detach_playback(void *audio, int playback_slot_id);
extern void wait_mic_capture_ready(void *audio, int timeout_ms);
extern void audio_heal_mic_path_if_needed(void *audio);
extern void session_begin_capture(voice_session_t *s);
extern void session_delay_ms(int ms);

#define PROMPT_DONE_AEC_SETTLE_MS  120
#define MIC_READY_TIMEOUT_MS       500

static void prompt_detach_playback(prompt_tone_t *pt)
{
    if (pt == NULL || !pt->playback_attached) {
        return;
    }
    audio_detach_playback(pt->audio, pt->playback_slot_id);
    pt->playback_attached = false;
}

void prompt_tone_stop(prompt_tone_t *pt)
{
    /* stop underlying stream ... */
    prompt_detach_playback(pt);
}

static void prompt_on_playback_finished(void *user)
{
    prompt_tone_t *pt = (prompt_tone_t *)user;
    prompt_detach_playback(pt);
    if (pt->on_done) {
        pt->on_done(pt->user_data);
    }
}

static bool session_is_current_generation(voice_session_t *s, uint32_t gen)
{
    return s != NULL && gen == s->capture_gen;
}

static void session_handle_prompt_done(void *user)
{
    voice_session_t *s = (voice_session_t *)user;
    uint32_t gen = s->capture_gen;

    if (!session_is_current_generation(s, gen)) {
        return;
    }

    session_delay_ms(PROMPT_DONE_AEC_SETTLE_MS);
    wait_mic_capture_ready(s->audio, MIC_READY_TIMEOUT_MS);
    audio_heal_mic_path_if_needed(s->audio);

    if (!session_is_current_generation(s, gen)) {
        return;
    }
    session_begin_capture(s);
}

void session_on_wake(voice_session_t *s)
{
    s->capture_gen++;
    s->prompt->on_done = session_handle_prompt_done;
    s->prompt->user_data = s;
    /* prompt_play(s->prompt); — 须在 start_uplink 之前 */
}

void session_on_tts_interrupt(voice_session_t *s)
{
    s->capture_gen++;
    /*
     * Platform code should stop speaker only when the shared backend is in
     * SPEAKER mode. Incoming stale TTS chunks carrying the old generation are
     * dropped while capture is pending/running.
     */
}
