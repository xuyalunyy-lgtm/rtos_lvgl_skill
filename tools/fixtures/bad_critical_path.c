/**
 * @file bad_critical_path.c
 * @brief C35 关键路径 self-test 反例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/* 反例 C35.2: 启动路径无超时 */
void bad_boot_init(void)
{
    /* 无超时保护 */
    vTaskDelay(portMAX_DELAY);
}

/* 反例 C35.2: 网络连接无 deadline */
int bad_net_connect(void)
{
    vTaskDelay(portMAX_DELAY);
    return 0;
}
