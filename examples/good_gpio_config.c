/**
 * @file good_gpio_config.c
 * @brief C18 外设驱动安全正例：GPIO 方向配置 + I2C 地址文档
 *
 * 约束覆盖：
 *   C18.1 — GPIO 方向必须在使用前配置
 *   C18.2 — I2C 设备地址必须来自 datasheet
 */

#include "driver/gpio.h"
#include "driver/i2c.h"
#include "esp_log.h"

static const char *TAG = "gpio_config";

/* C18.2: I2C 地址来自 datasheet */
#define OLED_I2C_ADDR    0x3C  /* SSD1306 datasheet Table 8-1 */
#define SENSOR_I2C_ADDR  0x68  /* MPU6050 datasheet Section 9.2 */

/**
 * @brief C18.1 — GPIO 方向先配置再使用
 */
esp_err_t good_gpio_setup(void)
{
    /* C18.1: 先配置方向 */
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << GPIO_NUM_2) | (1ULL << GPIO_NUM_4),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&io_conf);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "GPIO config failed: %s", esp_err_to_name(err));
        return err;
    }

    /* C18.1: 配置后才能使用 */
    gpio_set_level(GPIO_NUM_2, 1);
    gpio_set_level(GPIO_NUM_4, 0);

    return ESP_OK;
}

/**
 * @brief C18.2 — I2C 地址来自 datasheet
 */
esp_err_t good_i2c_read_sensor(uint8_t reg, uint8_t *data, size_t len)
{
    /* C18.2: 使用 datasheet 定义的地址 */
    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (SENSOR_I2C_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write(cmd, &reg, 1, true);
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (SENSOR_I2C_ADDR << 1) | I2C_MASTER_READ, true);
    i2c_master_read(cmd, data, len, I2C_MASTER_LAST_NACK);
    i2c_master_stop(cmd);

    esp_err_t err = i2c_master_cmd_begin(I2C_NUM_0, cmd, pdMS_TO_TICKS(1000));
    i2c_cmd_link_delete(cmd);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "I2C read failed: %s", esp_err_to_name(err));
    }
    return err;
}
