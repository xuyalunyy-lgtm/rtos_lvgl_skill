/**
 * 反例 — C10 语音/Uplink 违规
 *
 * 违反约束:
 *   C10.1 — prompt stop 后未 detach playback（FINISHED 路径遗漏）
 *   C10.2 — prompt 刚停即 start uplink，无 AEC settle
 *   C10.5 — 旧 FINISHED 回调未用 session generation 过滤
 *
 * 对照正例: good_voice_prompt_uplink.c
 */

#include "app_mvp.h"
#include <string.h>
#include <stdio.h>

/* ========== 反例 1: stop 路径 detach 但 FINISHED 路径遗漏 (C10.1) ========== */

typedef struct {
    int audio_handle;
    int playback_slot_id;
    int playback_attached;
    void (*on_done)(void *);
    void *user_data;
} bad_prompt_tone_t;

/* ❌ stop 时 detach 了，但 FINISHED 回调未 detach */
void bad_prompt_tone_stop(bad_prompt_tone_t *pt)
{
    if (pt == NULL) {
        return;
    }
    /* 只在 stop 路径 detach，FINISHED 路径遗漏 */
    if (pt->playback_attached) {
        /* audio_detach_playback(pt->audio_handle, pt->playback_slot_id); */
        pt->playback_attached = 0;
    }
}

/* ❌ FINISHED 回调未 detach playback，AEC 参考路径污染 */
static void bad_on_playback_finished(void *user)
{
    bad_prompt_tone_t *pt = (bad_prompt_tone_t *)user;
    /* 遗漏: 未调用 audio_detach_playback */
    /* 遗漏: 未设置 pt->playback_attached = 0 */
    if (pt->on_done) {
        pt->on_done(pt->user_data);
    }
}

/* ========== 反例 2: 无 AEC settle 直接开 uplink (C10.2) ========== */

typedef struct {
    int audio_handle;
    int capture_gen;
} bad_voice_session_t;

/* ❌ prompt 刚停就 start uplink，AEC 未 settle */
static void bad_on_prompt_done(void *ctx)
{
    bad_voice_session_t *s = (bad_voice_session_t *)ctx;

    /* 未检查 session generation (C10.5) */
    /* 未等待 AEC settle (C10.2) */
    /* 未调用 wait_mic_capture_ready */

    /* 直接开 uplink — AEC 参考路径仍残留播放信号 */
    /* audio_start_uplink(s->audio_handle); */
    printf("[BAD] start uplink immediately, no AEC settle\n");
}

/* ========== 反例 3: 无 session generation 过滤 (C10.5) ========== */

/* ❌ 旧 FINISHED 回调未校验 generation，cancel 后仍触发 capture */
static void bad_stale_callback(void *ctx)
{
    bad_voice_session_t *s = (bad_voice_session_t *)ctx;

    /* 未检查 session_is_current_generation(s, gen) */
    /* 旧回调在新会话中仍然触发，导致乱序 */
    printf("[BAD] stale callback still triggers capture\n");
    /* audio_start_uplink(s->audio_handle); */
}

/* ❌ 旧 timer 回调未校验 generation */
static void bad_stale_timer_callback(void *ctx)
{
    bad_voice_session_t *s = (bad_voice_session_t *)ctx;

    /* 未检查 generation */
    /* 未检查 session 是否已 cancel/结束 */
    printf("[BAD] stale timer callback, no generation check\n");
}