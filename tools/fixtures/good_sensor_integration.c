#include <stdint.h>
#include <stdbool.h>

#define GENERIC_SENSOR_WHO_AM_I 0x00
#define GENERIC_SENSOR_CTRL1 0x10
#define GENERIC_SENSOR_DATA 0x20
#define GENERIC_SENSOR_ID 0x5A

typedef struct {
    int32_t value_milli_unit;
    uint32_t timestamp_ms;
    int32_t offset_milli_unit;
    int32_t scale_ppm;
    int32_t range_milli_unit;
} sensor_sample_t;

static int i2c_read_reg_timeout(uint8_t reg, uint8_t *data, uint32_t timeout_ms);
static int i2c_write_reg_timeout(uint8_t reg, uint8_t data, uint32_t timeout_ms);
static uint32_t sensor_time_ms(void);
static bool xTaskNotifyWait(uint32_t clear_on_entry, uint32_t clear_on_exit, uint32_t *value, uint32_t timeout_ticks);
static uint32_t pdMS_TO_TICKS(uint32_t ms);

/* datasheet: generic environmental sensor register map rev A */
int generic_sensor_init(void)
{
    const uint32_t timeout_ms = 5;
    uint8_t chip_id = 0;

    if (i2c_read_reg_timeout(GENERIC_SENSOR_WHO_AM_I, &chip_id, timeout_ms) != 0) {
        return -1;
    }
    if (chip_id != GENERIC_SENSOR_ID) {
        return -2;
    }

    return i2c_write_reg_timeout(GENERIC_SENSOR_CTRL1, 0x03, timeout_ms);
}

int generic_sensor_wait_ready(void)
{
    uint32_t notified = 0;
    if (!xTaskNotifyWait(0, 0, &notified, pdMS_TO_TICKS(20))) {
        return -1;
    }
    return 0;
}

int generic_sensor_read_sample(sensor_sample_t *out)
{
    const uint32_t timeout_ms = 5;
    uint8_t raw[2] = {0};

    if (i2c_read_reg_timeout(GENERIC_SENSOR_DATA, raw, timeout_ms) != 0) {
        return -1;
    }

    out->timestamp_ms = sensor_time_ms();
    out->scale_ppm = 1000;
    out->range_milli_unit = 200000;
    out->offset_milli_unit = 12;
    out->value_milli_unit = ((int32_t)((raw[0] << 8) | raw[1]) * out->scale_ppm) / 1000 - out->offset_milli_unit;
    return 0;
}
