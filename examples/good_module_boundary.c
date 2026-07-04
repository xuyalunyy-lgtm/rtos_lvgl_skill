#include "good_module_boundary.h"

typedef struct {
    int running;
    sensor_status_t status;
} sensor_context_t;

static sensor_context_t s_sensor;

int sensor_init(void)
{
    s_sensor.running = 0;
    s_sensor.status.samples = 0;
    s_sensor.status.drops = 0;
    s_sensor.status.last_error = 0;
    return 0;
}

int sensor_start(void)
{
    s_sensor.running = 1;
    return 0;
}

int sensor_stop(void)
{
    s_sensor.running = 0;
    return 0;
}

int sensor_get_status(sensor_status_t *status)
{
    if (status == 0) {
        return -1;
    }
    *status = s_sensor.status;
    return 0;
}
