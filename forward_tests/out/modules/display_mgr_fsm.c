/**
 * @file display_mgr_fsm.c
 * @brief display_mgr 状态机骨架（C13 自动生成）
 */

#include "display_mgr_contract.h"
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(display_mgr, CONFIG_LOG_DEFAULT_LEVEL);

static display_mgr_state_t s_state = DISPLAY_MGR_STATE_UNINIT;
static display_mgr_err_t s_last_error = DISPLAY_MGR_OK;
static uint32_t s_last_error_line = 0;

#define SET_ERROR(err) do { \
    s_last_error = (err); \
    s_last_error_line = __LINE__; \
} while(0)

display_mgr_err_t display_mgr_init(void)
{
    if (s_state != DISPLAY_MGR_STATE_UNINIT) {
        LOG_WRN("Already initialized");
        return DISPLAY_MGR_ERR_STATE;
    }

    /* TODO: 初始化资源 */

    s_state = DISPLAY_MGR_STATE_IDLE;
    LOG_INF("Module initialized");
    return DISPLAY_MGR_OK;
}

display_mgr_err_t display_mgr_start(void)
{
    if (s_state != DISPLAY_MGR_STATE_IDLE) {
        LOG_ERR("Cannot start from state %d", s_state);
        SET_ERROR(DISPLAY_MGR_ERR_STATE);
        return DISPLAY_MGR_ERR_STATE;
    }

    /* TODO: 启动任务/定时器 */

    s_state = DISPLAY_MGR_STATE_RUNNING;
    LOG_INF("Module started");
    return DISPLAY_MGR_OK;
}

display_mgr_err_t display_mgr_stop(void)
{
    if (s_state != DISPLAY_MGR_STATE_RUNNING) {
        LOG_WRN("Not running, state=%d", s_state);
        return DISPLAY_MGR_OK; /* 可重入 */
    }

    s_state = DISPLAY_MGR_STATE_STOPPING;
    LOG_INF("Module stopping...");

    /* TODO: 通知任务退出 + 等待 */

    s_state = DISPLAY_MGR_STATE_IDLE;
    LOG_INF("Module stopped");
    return DISPLAY_MGR_OK;
}

display_mgr_err_t display_mgr_deinit(void)
{
    if (s_state == DISPLAY_MGR_STATE_UNINIT) {
        return DISPLAY_MGR_OK; /* 可重入 */
    }

    if (s_state == DISPLAY_MGR_STATE_RUNNING) {
        display_mgr_stop();
    }

    /* TODO: 释放资源 */

    s_state = DISPLAY_MGR_STATE_UNINIT;
    LOG_INF("Module deinitialized");
    return DISPLAY_MGR_OK;
}

display_mgr_err_t display_mgr_get_status(display_mgr_status_t *status)
{
    if (status == NULL) return DISPLAY_MGR_ERR_CONFIG;

    status->state = s_state;
    status->last_error = s_last_error;
    status->last_error_line = s_last_error_line;
    return DISPLAY_MGR_OK;
}
