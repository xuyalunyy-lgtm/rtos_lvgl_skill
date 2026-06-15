/* fixture: 栈 payload 进 Queue — 期望 queue_ownership_checker 失败 */
#include "FreeRTOS.h"
#include "queue.h"
#include <string.h>

typedef struct {
    char *payload;
    size_t len;
} evt_t;

void model_emit_bad(QueueHandle_t q)
{
    char stack_payload[64];
    evt_t evt;

    strcpy(stack_payload, "dangling after return");
    evt.payload = stack_payload;
    evt.len = strlen(stack_payload);
    xQueueSend(q, &evt, portMAX_DELAY);
}
