/* Bad C12: unchecked FreeRTOS return values */
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

void bad_return_check(void)
{
    /* C12.1: xTaskCreate return value unchecked */
    xTaskCreate(task_fn, "Task", 256, NULL, 5, NULL);

    /* C12.1: xQueueSend return value unchecked */
    xQueueSend(queue, &data, 0);

    /* C12.2: pvPortMalloc without NULL check */
    void *ptr = pvPortMalloc(128);
    memcpy(ptr, src, 128);
}
