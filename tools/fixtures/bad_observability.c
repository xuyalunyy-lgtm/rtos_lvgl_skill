/**
 * @file bad_observability.c
 * @brief C32 可观测性 self-test 反例 fixture
 */
#include <stdint.h>

/* 反例 C32.1/C32.2: 缺少可观测性字段 */
typedef struct {
    int state;
    /* 缺少 last_error */
    /* 缺少 last_error_line */
    /* 缺少 timeout_count / drop_count */
} bad_module_status_t;

static bad_module_status_t s_status;
