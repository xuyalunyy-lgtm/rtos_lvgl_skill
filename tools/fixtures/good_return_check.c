/* Good C12: all return values checked */
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

void good_return_check(void)
{
    BaseType_t ret;

    /* C12.1: xTaskCreate return checked */
    ret = xTaskCreate(task_fn, "Task", 256, NULL, 5, NULL);
    if (ret != pdPASS) {
        LOG_ERR("Task create failed");
        return;
    }

    /* C12.1: xQueueSend return checked */
    ret = xQueueSend(queue, &data, pdMS_TO_TICKS(100));
    if (ret != pdTRUE) {
        LOG_ERR("Queue send failed");
        return;
    }

    /* C12.2: pvPortMalloc NULL check */
    void *ptr = pvPortMalloc(128);
    if (ptr == NULL) {
        LOG_ERR("malloc failed");
        return;
    }
    memcpy(ptr, src, 128);
    vPortFree(ptr);
}
