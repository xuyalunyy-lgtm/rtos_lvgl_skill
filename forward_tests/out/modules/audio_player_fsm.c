/**
 * @file audio_player_fsm.c
 * @brief audio_player 状态机骨架（C13 自动生成）
 */

#include "audio_player_contract.h"
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(audio_player, CONFIG_LOG_DEFAULT_LEVEL);

static audio_player_state_t s_state = AUDIO_PLAYER_STATE_UNINIT;
static audio_player_err_t s_last_error = AUDIO_PLAYER_OK;
static uint32_t s_last_error_line = 0;

#define SET_ERROR(err) do { \
    s_last_error = (err); \
    s_last_error_line = __LINE__; \
} while(0)

audio_player_err_t audio_player_init(void)
{
    if (s_state != AUDIO_PLAYER_STATE_UNINIT) {
        LOG_WRN("Already initialized");
        return AUDIO_PLAYER_ERR_STATE;
    }

    /* TODO: 初始化资源 */

    s_state = AUDIO_PLAYER_STATE_IDLE;
    LOG_INF("Module initialized");
    return AUDIO_PLAYER_OK;
}

audio_player_err_t audio_player_start(void)
{
    if (s_state != AUDIO_PLAYER_STATE_IDLE) {
        LOG_ERR("Cannot start from state %d", s_state);
        SET_ERROR(AUDIO_PLAYER_ERR_STATE);
        return AUDIO_PLAYER_ERR_STATE;
    }

    /* TODO: 启动任务/定时器 */

    s_state = AUDIO_PLAYER_STATE_RUNNING;
    LOG_INF("Module started");
    return AUDIO_PLAYER_OK;
}

audio_player_err_t audio_player_stop(void)
{
    if (s_state != AUDIO_PLAYER_STATE_RUNNING) {
        LOG_WRN("Not running, state=%d", s_state);
        return AUDIO_PLAYER_OK; /* 可重入 */
    }

    s_state = AUDIO_PLAYER_STATE_STOPPING;
    LOG_INF("Module stopping...");

    /* TODO: 通知任务退出 + 等待 */

    s_state = AUDIO_PLAYER_STATE_IDLE;
    LOG_INF("Module stopped");
    return AUDIO_PLAYER_OK;
}

audio_player_err_t audio_player_deinit(void)
{
    if (s_state == AUDIO_PLAYER_STATE_UNINIT) {
        return AUDIO_PLAYER_OK; /* 可重入 */
    }

    if (s_state == AUDIO_PLAYER_STATE_RUNNING) {
        audio_player_stop();
    }

    /* TODO: 释放资源 */

    s_state = AUDIO_PLAYER_STATE_UNINIT;
    LOG_INF("Module deinitialized");
    return AUDIO_PLAYER_OK;
}

audio_player_err_t audio_player_get_status(audio_player_status_t *status)
{
    if (status == NULL) return AUDIO_PLAYER_ERR_CONFIG;

    status->state = s_state;
    status->last_error = s_last_error;
    status->last_error_line = s_last_error_line;
    return AUDIO_PLAYER_OK;
}
