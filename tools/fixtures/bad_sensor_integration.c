#include <stdint.h>
#include <stdbool.h>

static int i2c_read_reg(uint8_t reg, uint8_t *data);
static int i2c_write_reg(uint8_t reg, uint8_t data);
static void calibrate_sensor_offsets(void);

typedef struct {
    int32_t raw_value;
} sensor_sample_t;

int bad_sensor_init(void)
{
    i2c_write_reg(0x10, 0x03);
    i2c_write_reg(0x11, 0x08);
    return 0;
}

int bad_sensor_read_sample(sensor_sample_t *out)
{
    uint8_t status = 0;
    uint8_t raw[2] = {0};

    while (!(status & 0x01)) {
        i2c_read_reg(0x1F, &status);
    }

    calibrate_sensor_offsets();
    i2c_read_reg(0x20, raw);
    out->raw_value = (int32_t)((raw[0] << 8) | raw[1]);
    return 0;
}
