#include "good_interface_contract.h"

int sensor_configure(const char *name, unsigned int timeout_ms)
{
    return (name != 0 && timeout_ms > 0U) ? 0 : -1;
}

void sensor_shutdown(void)
{
}
