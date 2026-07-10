/* Good C14: proper LOG_* macros, no ISR logging */
#include "log.h"

void good_logging(void)
{
    /* C14.1: proper LOG macro */
    LOG_I("sensor value: %d", val);
    LOG_I("starting calibration");
}

void ISR_Handler(void)
{
    /* C14.3: ISR does not log */
    BaseType_t wake = pdFALSE;
    xSemaphoreGiveFromISR(sem, &wake);
    portYIELD_FROM_ISR(wake);
}
