typedef struct {
    int state;
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

static sensor_status_t s_sensor_status;

int sensor_init(void)
{
    s_sensor_status.state = 0;
    return 0;
}

int sensor_start(void)
{
    s_sensor_status.state = 1;
    return 0;
}

int sensor_stop(void)
{
    s_sensor_status.state = 0;
    return 0;
}

int sensor_get_status(sensor_status_t *status)
{
    if (status == 0) {
        return -1;
    }
    *status = s_sensor_status;
    return 0;
}
