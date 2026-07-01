/**
 * @file bad_peripheral_shutdown.c
 * @brief C24 外设关闭安全 self-test 反例 fixture
 */
#include "driver/gpio.h"
#include "driver/ledc.h"

/* 反例 C24.1: 有 init 但无 deinit */
esp_err_t bad_peripheral_init(void)
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
    return ESP_OK;
}

/* 反例: 没有 deinit 函数，异常路径无法收尾 */
void bad_peripheral_do_work(void)
{
    gpio_set_level(GPIO_NUM_2, 1);
}
