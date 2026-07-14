// Edge case: Queue full handling with proper ownership
// Tests that queue_ownership_checker does not false-positive on correct patterns
#include "FreeRTOS.h"
#include "queue.h"
#include <stdlib.h>

typedef struct {
    int event_type;
    char *payload;  // heap-allocated
} event_t;

static QueueHandle_t event_q;

// Correct: Model allocates, sends with timeout, frees on failure
void model_send_event(int type, const char *data)
{
    event_t *evt = malloc(sizeof(event_t));
    if (!evt) return;

    evt->event_type = type;
    evt->payload = malloc(strlen(data) + 1);
    if (!evt->payload) {
        free(evt);
        return;
    }
    strcpy(evt->payload, data);

    // Send with timeout — if queue full, free payload
    if (xQueueSend(event_q, &evt, pdMS_TO_TICKS(100)) != pdPASS) {
        // Queue full — Model still owns payload, must free
        free(evt->payload);
        free(evt);
    }
    // After successful send, Model must NOT touch payload
}

// Correct: Presenter receives and frees
void presenter_process_events(void)
{
    event_t *evt;
    if (xQueueReceive(event_q, &evt, pdMS_TO_TICKS(20)) == pdPASS) {
        // Presenter owns evt now
        // process evt->payload
        free(evt->payload);
        free(evt);
    }
}

void queue_init(void)
{
    event_q = xQueueCreate(8, sizeof(event_t *));
}
