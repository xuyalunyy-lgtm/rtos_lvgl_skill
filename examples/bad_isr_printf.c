/**
 * 反例 — C14 日志规范违规
 *
 * 违反约束:
 *   C14.1 — 裸 printf 而非 LOG_* 宏
 *   C14.3 — ISR / DMA 回调中打日志（阻塞 + 性能灾难）
 *   C14.4 — 日志明文打印密码/token
 *
 * 对照正例: logging_debug.txt 模板
 */

#include "app_mvp.h"
#include <stdio.h>

/* ========== 反例 1: 裸 printf (C14.1) ========== */

/* ❌ 裸 printf：无法分级、无法关闭、无法重定向 */
static void bad_network_handler(const char *msg)
{
    printf("received: %s\n", msg);  /* 应改用 LOG_I(TAG, ...) */
    puts("processing...");           /* 同上 */
}

/* ========== 反例 2: ISR 中打日志 (C14.3) ========== */

/* ❌ ISR 中 printf：阻塞 + 可能重入 UART 驱动 */
void HAL_I2S_RxCpltCallback(void)
{
    printf("DMA complete\n");  /* 禁止：ISR 中阻塞 UART */
    /* 更严重：若 UART 驱动内部有 mutex，可能死锁 */
}

/* ❌ DMA 回调中日志 */
static void dma_transfer_complete(void)
{
    /* 每次 DMA 完成都打印，16kHz 采样 = 每秒 16000 条日志 */
    printf("DMA frame done, samples=256\n");
}

/* ❌ LVGL timer handler 中高频日志 */
static void bad_lvgl_task(void *arg)
{
    for (;;) {
        printf("lvgl tick\n");  /* 每 5ms 一次 = 日志洪水 */
        lv_timer_handler();
    }
}

/* ========== 反例 3: 日志明文打印凭证 (C14.4) ========== */

/* ❌ 明文打印 token 和密码 */
static void bad_auth_log(const char *token, const char *wifi_pass)
{
    printf("auth token: %s\n", token);        /* token 明文泄露到日志 */
    printf("wifi password: %s\n", wifi_pass);  /* 密码明文泄露 */

    /* 正确做法: */
    /* LOG_I(TAG, "token: %.4s****", token); */
    /* LOG_I(TAG, "wifi connected"); */  /* 密码不打印 */
}