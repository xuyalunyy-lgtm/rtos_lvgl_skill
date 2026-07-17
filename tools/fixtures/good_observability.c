/**
 * @file good_observability.c
 * @brief C32 可观测性 self-test 正例 fixture
 */
#include <stdint.h>

/* 正例: 模块状态结构体包含可观测性字段 */
typedef struct {
    int state;
    int last_error;
    uint32_t last_error_line;
    uint32_t timeout_count;
    uint32_t drop_count;
} module_status_t;

static module_status_t s_status;

typedef struct {
    uint32_t flush_max_ms;
    uint32_t render_max_ms;
} ui_display_metrics_t;

static ui_display_metrics_t s_display_metrics;

void good_lcd_flush_cb(lv_disp_drv_t *drv)
{
    s_display_metrics.flush_max_ms = 4U;
    lv_disp_flush_ready(drv);
}
