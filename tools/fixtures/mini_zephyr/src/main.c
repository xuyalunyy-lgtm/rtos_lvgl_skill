/**
 * @file main.c
 * @brief Mini Zephyr project for RTOS model extraction testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(mini_zephyr, LOG_LEVEL_INF);

/* ── Message queues ── */
K_MSGQ_DEFINE(sensor_msgq, sizeof(int), 8, 4);
K_MSGQ_DEFINE(ui_cmd_msgq, sizeof(int), 4, 4);

/* ── Semaphores ── */
K_SEM_DEFINE(spi_done_sem, 0, 1);
K_MUTEX_DEFINE(config_mutex);

/* ── Threads ── */
#define SENSOR_STACK_SIZE 2048
#define SENSOR_PRIORITY 5
K_THREAD_STACK_DEFINE(sensor_stack, SENSOR_STACK_SIZE);
static struct k_thread sensor_thread_data;

#define UI_STACK_SIZE 4096
#define UI_PRIORITY 3
K_THREAD_STACK_DEFINE(ui_stack, UI_STACK_SIZE);
static struct k_thread ui_thread_data;

/* ── Timer ── */
static void heartbeat_handler(struct k_timer *timer);
K_TIMER_DEFINE(heartbeat_timer, heartbeat_handler, NULL);

static void heartbeat_handler(struct k_timer *timer)
{
    LOG_INF("heartbeat");
}

static void sensor_thread(void *p1, void *p2, void *p3)
{
    LOG_INF("sensor_thread started");
    int data = 0;
    while (1) {
        data++;
        k_msgq_put(&sensor_msgq, &data, K_MSEC(100));
        k_msleep(100);
    }
}

static void ui_thread(void *p1, void *p2, void *p3)
{
    LOG_INF("ui_thread started");
    int cmd;
    while (1) {
        if (k_msgq_get(&ui_cmd_msgq, &cmd, K_MSEC(500)) == 0) {
            LOG_INF("ui cmd: %d", cmd);
        }
    }
}

int main(void)
{
    LOG_INF("mini_zephyr starting");

    k_thread_create(&sensor_thread_data, sensor_stack,
                    K_THREAD_STACK_SIZEOF(sensor_stack),
                    sensor_thread, NULL, NULL, NULL,
                    SENSOR_PRIORITY, 0, K_NO_WAIT);
    k_thread_create(&ui_thread_data, ui_stack,
                    K_THREAD_STACK_SIZEOF(ui_stack),
                    ui_thread, NULL, NULL, NULL,
                    UI_PRIORITY, 0, K_NO_WAIT);

    k_timer_start(&heartbeat_timer, K_SECONDS(1), K_SECONDS(1));

    LOG_INF("mini_zephyr initialized");
    return 0;
}
