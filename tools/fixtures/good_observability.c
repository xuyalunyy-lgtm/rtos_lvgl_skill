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
