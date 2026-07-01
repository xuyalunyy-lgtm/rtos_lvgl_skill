/**
 * @file good_peripheral_shutdown.c
 * @brief C24 外设关闭安全 self-test 正例 fixture
 */
#include "driver/gpio.h"
#include "driver/ledc.h"

static bool s_peripheral_enabled = false;

/* 正例: init/deinit 对称 */
esp_err_t peripheral_init(void)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << GPIO_NUM_2),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&io_conf);
    ledc_timer_config_t timer_conf = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_13_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = 5000,
    };
    ledc_timer_config(&timer_conf);
    s_peripheral_enabled = true;
    return ESP_OK;
}

/* 正例: 有对应的 deinit */
esp_err_t peripheral_deinit(void)
{
    if (!s_peripheral_enabled) return ESP_OK; /* 可重入 */
    ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0);
    gpio_set_level(GPIO_NUM_2, 0);
    s_peripheral_enabled = false;
    return ESP_OK;
}
