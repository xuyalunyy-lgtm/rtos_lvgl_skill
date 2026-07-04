#ifndef GOOD_MODULE_BOUNDARY_H
#define GOOD_MODULE_BOUNDARY_H

#include <stdint.h>

typedef struct {
    uint32_t samples;
    uint32_t drops;
    int last_error;
} sensor_status_t;

/* module_boundary:
 * responsibility: collect sensor samples and publish normalized events
 * public_api: sensor_init, sensor_start, sensor_stop, sensor_get_status
 * dependencies: i2c_bus, app_event_bus
 * forbidden_dependencies: lvgl, network_wss, storage_nvs
 * events_in: SENSOR_CMD_START, SENSOR_CMD_STOP
 * events_out: SENSOR_EVT_SAMPLE_READY, SENSOR_EVT_FAULT
 * owned_resources: i2c0, sensor_task, sensor_queue
 */

int sensor_init(void);
int sensor_start(void);
int sensor_stop(void);
int sensor_get_status(sensor_status_t *status);

#endif /* GOOD_MODULE_BOUNDARY_H */
