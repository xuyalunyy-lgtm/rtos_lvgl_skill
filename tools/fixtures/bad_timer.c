/* Bad timer: blocking call in callback, create without delete */
#include "FreeRTOS.h"
#include "timers.h"

static void my_timer_cb(TimerHandle_t xTimer) {
    vTaskDelay(100);
    printf("tick\n");
}

void setup_timer(void) {
    TimerHandle_t tmr = xTimerCreate("t1", 1000, pdTRUE, NULL, my_timer_cb);
    xTimerStart(tmr, 0);
}
