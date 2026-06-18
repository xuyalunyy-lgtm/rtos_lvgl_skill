/**
 * 反例 — C18 外设驱动安全违规
 *
 * 违反约束:
 *   C18.1 — GPIO 方向未配置直接使用
 *   C18.2 — I2C 地址硬编码猜测
 *   C18.4 — DMA 通道分配无文档
 *
 * 对照正例: peripheral_driver_safety.txt
 */

#include "app_mvp.h"
#include <string.h>

/* ========== 反例 1: GPIO 未配置方向直接 set_level (C18.1) ========== */

/* ❌ 复位后立即输出高电平，方向寄存器未配置 */
static void bad_lcd_reset(void)
{
    gpio_set_level(LCD_RST_PIN, 0);  /* GPIO 方向未知，行为未定义 */
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(LCD_RST_PIN, 1);
}

/* ❌ 背光控制前无 gpio_config */
static void bad_backlight_on(void)
{
    gpio_set_level(LCD_BL_PIN, 1);  /* 方向可能还是输入模式 */
}

/* ========== 反例 2: I2C 地址硬编码猜测 (C18.2) ========== */

/* ❌ 地址 0x60 无 datasheet 依据，可能是 0x68 或 0x76 */
static void bad_i2c_read_sensor(void)
{
    uint8_t data[6];
    i2c_master_read(i2c_dev, 0x60, data, sizeof(data));  /* 硬编码猜测 */
}

/* ❌ 宏定义无来源注释 */
#define OLED_ADDR  0x3C  /* 应标注 datasheet 页码或寄存器表 */

/* ========== 反例 3: DMA 通道分配无文档 (C18.4) ========== */

/* ❌ I2S 和 SPI 可能共享 DMA 通道，无注释说明 */
static void bad_dma_init(void)
{
    /* DMA 通道 0 — 无注释说明用途 */
    i2s_dma_chan = 0;

    /* DMA 通道 0 — 与 I2S 冲突！ */
    spi_dma_chan = 0;
}

/* ========== 正例对照 ========== */

/* ✅ 正确: 先配置方向，再使用 */
static void good_lcd_reset(void)
{
    gpio_config_t rst_conf = {
        .pin_bit_mask = (1ULL << LCD_RST_PIN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&rst_conf);

    gpio_set_level(LCD_RST_PIN, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(LCD_RST_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(120));
}

/* ✅ 正确: I2C 地址用宏，标注来源 */
#define BME280_ADDR  0x76  /* datasheet Table 17, SDO → GND */

static void good_i2c_read_sensor(void)
{
    uint8_t data[6];
    esp_err_t ret = i2c_master_read(i2c_dev, BME280_ADDR, data, sizeof(data));
    if (ret != ESP_OK) {
        LOG_E(TAG, "I2C read failed: %s", esp_err_to_name(ret));
    }
}

/* ✅ 正确: DMA 通道分配有注释 */
static void good_dma_init(void)
{
    /* DMA 通道 0: I2S RX（音频采集，优先级最高） */
    i2s_dma_chan = 0;

    /* DMA 通道 1: SPI LCD（显示刷新，优先级中） */
    spi_dma_chan = 1;
}
