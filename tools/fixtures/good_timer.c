/* Good timer: no blocking in callback, create has matching delete */
#include "FreeRTOS.h"
#include "timers.h"

static void my_timer_cb(TimerHandle_t xTimer) {
    int val = 1 + 2;
    (void)val;
}

void setup_timer(void) {
    TimerHandle_t tmr = xTimerCreate("t1", 1000, pdTRUE, NULL, my_timer_cb);
    xTimerStart(tmr, 0);
    xTimerStop(tmr, 0);
    xTimerDelete(tmr, 0);
}
