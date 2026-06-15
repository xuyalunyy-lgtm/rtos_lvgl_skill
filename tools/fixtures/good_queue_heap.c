/* fixture: heap payload 进 Queue — 期望 queue_ownership_checker 通过 */
#include "FreeRTOS.h"
#include "queue.h"

typedef struct {
    char *payload;
    size_t len;
} evt_t;

void model_emit_good(QueueHandle_t q)
{
    char *heap = (char *)pvPortMalloc(64);
    if (heap == NULL) {
        return;
    }
    evt_t evt = { .payload = heap, .len = 64 };
    xQueueSend(q, &evt, portMAX_DELAY);
}
