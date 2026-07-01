/**
 * @file good_critical_path.c
 * @brief C35 关键路径 self-test 正例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/* 正例: 启动路径有超时 */
void good_boot_init(void)
{
    /* 有超时保护 */
    vTaskDelay(pdMS_TO_TICKS(100));
}

/* 正例: 网络连接有 deadline */
int good_net_connect(void)
{
    /* 有超时 */
    vTaskDelay(pdMS_TO_TICKS(1000));
    return 0;
}
