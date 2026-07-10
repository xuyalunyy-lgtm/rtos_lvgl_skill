/* Bad C14: bare printf in non-ISR, no rate limiting */
#include <stdio.h>

void bad_logging(void)
{
    /* C14.1: bare printf instead of LOG_* */
    printf("sensor value: %d\n", val);
    puts("starting calibration");
}

void ISR_Handler(void)
{
    /* C14.3: printf inside ISR */
    printf("interrupt fired\n");
}
