/**
 * @file app_mvp.h
 * @brief test_voice MVP 事件类型定义
 */

#ifndef TEST_VOICE_APP_MVP_H
#define TEST_VOICE_APP_MVP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 事件类型 */
typedef enum {
    EVT_NONE = 0,
    EVT_HEARTBEAT,
    EVT_DATA_RECEIVED,
    EVT_STATUS_UPDATE,
    EVT_ERROR,
    EVT_MAX,
} event_type_t;

/* 事件结构体 */
typedef struct {
    uint32_t type;
    uint32_t timestamp;
    void *payload;  /* C29.3: 所有权声明 — 生产者 alloc，消费者 free */
} app_event_t;

#ifdef __cplusplus
}
#endif

#endif /* TEST_VOICE_APP_MVP_H */
