# Zephyr RTOS 平台专档

> Zephyr RTOS 差异化特性、开发规范与 FreeRTOS 迁移指南。

---

## 目录

- [关键差异](#关键差异)
- [线程模型](#线程模型)
- [设备驱动框架](#设备驱动框架)
- [Device Tree (DTS)](#device-tree-dts)
- [Kconfig 配置](#kconfig-配置)
- [内存管理](#内存管理)
- [网络/WiFi](#网络wifi)
- [LVGL 集成](#lvgl-集成)
- [音频/I2S](#audioi2s)
- [看门狗](#看门狗)
- [低功耗](#低功耗)
- [Crash 诊断](#crash-诊断)
- [SDK 裁剪](#sdk-裁剪)
- [FreeRTOS → Zephyr 迁移](#freertos--zephyr-迁移)
- [快速参考](#快速参考)

---

## 关键差异

| 维度 | FreeRTOS | Zephyr |
|------|----------|--------|
| 线程 API | `xTaskCreate` / `vTaskDelete` | `k_thread_create` / `k_thread_abort` |
| 同步原语 | `xSemaphoreTake` / `xQueueReceive` | `k_sem_take` / `k_msgq_get` |
| 定时器 | `xTimerCreate` / `xTimerStart` | `k_timer_start` / `k_timer_stop` |
| 内存分配 | `pvPortMalloc` / `vPortFree` | `k_malloc` / `k_free` 或 heap 池 |
| 设备模型 | 手动初始化 | Device Tree + `device_is_ready()` |
| 配置系统 | Kconfig (ESP-IDF 风格) | Kconfig (原生) + DTS overlay |
| 构建系统 | CMake + idf.py / make | CMake + west |
| 多核 | 手动绑核 | IPC 服务 + AMP 支持 |

---

## 线程模型

### 线程创建

```c
/* Zephyr 线程创建 */
K_THREAD_STACK_DEFINE(my_stack, 4096);
static struct k_thread my_thread_data;

void my_thread_entry(void *p1, void *p2, void *p3) {
    /* 线程主循环 */
    while (1) {
        /* 处理事件 */
        k_msleep(100);
    }
}

k_tid_t tid = k_thread_create(
    &my_thread_data,
    my_stack,
    K_THREAD_STACK_SIZEOF(my_stack),
    my_thread_entry,
    NULL, NULL, NULL,
    5,  /* 优先级 */
    0,  /* 选项 */
    K_NO_WAIT  /* 启动延迟 */
);
```

### FreeRTOS 对照

| FreeRTOS | Zephyr | 说明 |
|----------|--------|------|
| `xTaskCreate(func, name, stack, param, prio, &handle)` | `k_thread_create(...)` | 栈由 `K_THREAD_STACK_DEFINE` 分配 |
| `vTaskDelete(handle)` | `k_thread_abort(tid)` | Zephyr 用 `abort` 语义 |
| `vTaskDelay(ms)` | `k_msleep(ms)` | 单位相同 |
| `vTaskDelayUntil(&tick, period)` | `k_msleep(period)` 或 `k_timer` | Zephyr 推荐用 timer |
| `xTaskNotifyGive(tid)` | `k_sem_give(&sem)` 或 `k_event_post()` | Notification → Semaphore/Event |
| `ulTaskNotifyTake(...)` | `k_sem_take(&sem, ...)` 或 `k_event_wait()` | 同上 |

### 优先级

- Zephyr：**数字越小优先级越高**（与 STM32 FreeRTOS 相同）
- `K_PRIO_PREEMPT(5)` = 优先级 5，可抢占
- `K_PRIO_COOP(5)` = 优先级 5，协作式

---

## 设备驱动框架

### 设备获取

```c
/* Device Tree 方式 */
const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(i2c0));
if (!device_is_ready(dev)) {
    LOG_ERR("I2C device not ready");
    return -ENODEV;
}
```

### GPIO

```c
#include <zephyr/drivers/gpio.h>

static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(DT_NODELABEL(led0), gpios);

/* 初始化 */
gpio_pin_configure_dt(&dev, GPIO_OUTPUT_ACTIVE);

/* 控制 */
gpio_pin_set_dt(&led, 1);
```

### I2C

```c
#include <zephyr/drivers/i2c.h>

const struct device *i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c0));

uint8_t reg = 0x75;
uint8_t chip_id;
i2c_burst_read(i2c_dev, 0x68, reg, &chip_id, 1);
```

### SPI

```c
#include <zephyr/drivers/spi.h>

const struct device *spi_dev = DEVICE_DT_GET(DT_NODELABEL(spi1));

struct spi_config cfg = {
    .frequency = 1000000,
    .operation = SPI_WORD_SET(8) | SPI_OP_MODE_MASTER,
};
```

---

## Device Tree (DTS)

### 基本结构

```dts
/* boards/my_board.overlay */
/ {
    chosen {
        zephyr,console = &uart0;
        zephyr,shell-uart = &uart0;
    };
};

&i2c0 {
    status = "okay";
    clock-frequency = <I2C_BITRATE_FAST>;

    sensor@68 {
        compatible = "vendor,sensor";
        reg = <0x68>;
    };
};
```

### DTS → C 绑定

```c
/* 获取 DTS 节点设备 */
#define SENSOR_NODE DT_NODELABEL(sensor)
const struct device *sensor = DEVICE_DT_GET(SENSOR_NODE);

/* 获取 DTS 属性 */
#define SENSOR_LABEL DT_LABEL(SENSOR_NODE)
```

---

## Kconfig 配置

### 常用配置

```kconfig
# 启用 GPIO
CONFIG_GPIO=y

# 启用 I2C
CONFIG_I2C=y

# 启用 SPI
CONFIG_SPI=y

# 启用 LVGL
CONFIG_LVGL=y
CONFIG_LV_Z_HOR_RES_MAX=240
CONFIG_LV_Z_VER_RES_MAX=320

# 网络
CONFIG_NETWORKING=y
CONFIG_NET_IPV4=y
CONFIG_NET_TCP=y
CONFIG_WIFI=y

# 低功耗
CONFIG_PM=y
CONFIG_PM_DEVICE=y
```

### 条件编译

```c
#include <zephyr/kernel.h>

#ifdef CONFIG_WIFI
    /* WiFi 相关代码 */
#endif

#ifdef CONFIG_LVGL
    /* LVGL 相关代码 */
#endif
```

---

## 内存管理

### 堆分配

```c
#include <zephyr/kernel.h>

/* 动态分配 */
void *buf = k_malloc(1024);
if (buf == NULL) {
    LOG_ERR("malloc failed");
    return -ENOMEM;
}
k_free(buf);
```

### 静态内存池

```c
K_MEM_POOL_DEFINE(my_pool, 64, 1024, 4, 4);

void *block;
k_mem_pool_alloc(&my_pool, &block, 256, K_MSEC(100));
/* 使用 block */
k_mem_pool_free(&block);
```

### 栈空间

```c
/* 获取当前线程栈使用 */
size_t unused = k_thread_stack_space_get(k_current_get());
LOG_INF("Unused stack: %zu bytes", unused);
```

---

## 网络/WiFi

### Socket API

```c
#include <zephyr/net/socket.h>

int sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);

struct sockaddr_in addr = {
    .sin_family = AF_INET,
    .sin_port = htons(8080),
};
inet_pton(AF_INET, "192.168.1.1", &addr.sin_addr);

connect(sock, (struct sockaddr *)&addr, sizeof(addr));

/* 设置超时 */
struct timeval tv = { .tv_sec = 10 };
setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
```

### WiFi 连接

```c
#include <zephyr/net/wifi_mgmt.h>

struct wifi_connect_req_params params = {
    .ssid = "MySSID",
    .ssid_length = 7,
    .psk = "password",
    .psk_length = 8,
    .security = WIFI_SECURITY_TYPE_PSK,
    .channel = WIFI_CHANNEL_ANY,
};

net_mgmt(NET_REQUEST_WIFI_CONNECT, iface, &params, sizeof(params));
```

---

## LVGL 集成

### 启用 LVGL

```kconfig
CONFIG_LVGL=y
CONFIG_LV_Z_HOR_RES_MAX=240
CONFIG_LV_Z_VER_RES_MAX=320
CONFIG_LV_Z_BITS_PER_PIXEL=16
CONFIG_LV_Z_VDB_SIZE=240
```

### 初始化

```c
#include <lvgl.h>

void main(void) {
    /* LVGL 由 Zephyr 自动初始化 */
    /* 在主循环中调用 lv_task_handler */
    while (1) {
        lv_task_handler();
        k_msleep(10);
    }
}
```

---

## 音频/I2S

### I2S 配置

```c
#include <zephyr/drivers/i2s.h>

const struct device *i2s_dev = DEVICE_DT_GET(DT_NODELABEL(i2s0));

struct i2s_config cfg = {
    .word_size = 16,
    .channels = 2,
    .format = I2S_FMT_DATA_FORMAT_I2S,
    .options = I2S_OPT_BIT_CLK_MASTER | I2S_OPT_FRAME_CLK_MASTER,
    .frame_clk_freq = 44100,
    .mem_slab = &my_slab,
    .block_size = 4096,
    .timeout = 1000,
};

i2s_configure(i2s_dev, I2S_DIR_TX, &cfg);
```

---

## 看门狗

```c
#include <zephyr/drivers/watchdog.h>

const struct device *wdt = DEVICE_DT_GET(DT_NODELABEL(wdt0));

struct wdt_timeout_cfg cfg = {
    .window.min = 0,
    .window.max = 5000,
    .callback = wdt_callback,
};

int wdt_id = wdt_install_timeout(wdt, &cfg);
wdt_setup(wdt, WDT_OPT_PAUSE_HALTED_BY_DBG);
wdt_feed(wdt, wdt_id);
```

---

## 低功耗

### System Idle

```c
#include <zephyr/pm/pm.h>
#include <zephyr/pm/device.h>

/* Zephyr 自动管理 idle 状态 */
/* 手动挂起设备 */
pm_device_action_run(dev, PM_DEVICE_ACTION_SUSPEND);

/* 手动恢复设备 */
pm_device_action_run(dev, PM_DEVICE_ACTION_RESUME);
```

### Deep Sleep

```c
#include <zephyr/pm/pm.h>

/* 配置唤醒源 */
sys_poweroff();
```

---

## Crash 诊断

### HardFault

```
[00:00:01.000,000] <err> os: ***** BUS FAULT *****
[00:00:01.000,000] <err> os:   Precise data bus error
[00:00:01.000,000] <err> os:   BFAR Address: 0x00000000
[00:00:01.000,000] <err> os: r0/a1: 0x00000000  r1/a2: 0x20001000
[00:00:01.000,000] <err> os: r2/a3: 0x00000001  r3/a4: 0x00000000
[00:00:01.000,000] <err> os: r12/ip: 0x00000000 r14/lr: 0x08001234
[00:00:01.000,000] <err> os:  xpsr: 0x61000000
[00:00:01.000,000] <err> os: Faulting instruction address (r15/pc): 0x08001234
```

### addr2line

```bash
# Zephyr 使用 west 命令
west debug --runner=openocd

# 或手动 addr2line
arm-none-eabi-addr2line -e build/zephyr/zephyr.elf -a 0x08001234
```

---

## SDK 裁剪

### 模块裁剪

```kconfig
# 禁用未使用模块
CONFIG_BT=n
CONFIG_DISK_ACCESS=n
CONFIG_FLASH=n
CONFIG_SENSOR=n
CONFIG_USB=n
```

### DTS overlay 裁剪

```dts
/* 禁用未使用外设 */
&i2c1 {
    status = "disabled";
};

&spi1 {
    status = "disabled";
};
```

---

## FreeRTOS → Zephyr 迁移

| FreeRTOS API | Zephyr API | 注意事项 |
|-------------|------------|----------|
| `xTaskCreate` | `k_thread_create` | 栈由 `K_THREAD_STACK_DEFINE` 分配 |
| `vTaskDelete` | `k_thread_abort` | `abort` 语义不同 |
| `xSemaphoreCreateMutex` | `K_MUTEX_DEFINE` | 静态定义 |
| `xSemaphoreTake` | `k_mutex_lock` | 返回 0 成功 |
| `xSemaphoreGive` | `k_mutex_unlock` | 同上 |
| `xQueueCreate` | `K_MSGQ_DEFINE` | 静态定义 |
| `xQueueSend` | `k_msgq_put` | 返回 0 成功 |
| `xQueueReceive` | `k_msgq_get` | 同上 |
| `xTimerCreate` | `K_TIMER_DEFINE` | 静态定义 |
| `xTimerStart` | `k_timer_start` | 单位 ms |
| `pvPortMalloc` | `k_malloc` | 需要 `CONFIG_HEAP_MEM_POOL_SIZE` |
| `vPortFree` | `k_free` | 同上 |
| `portMAX_DELAY` | `K_FOREVER` | 永久等待 |
| `pdMS_TO_TICKS(ms)` | `K_MSEC(ms)` | Zephyr 原生支持 ms |

---

## 快速参考

### 构建命令

```bash
# 初始化 workspace
west init -m https://github.com/zephyrproject-rtos/zephyr
west update

# 构建
west build -b <board> <app_dir>

# 烧写
west flash

# 调试
west debug
```

### 常用命令

```bash
# 清理
west build -t pristine

# 配置
west build -t menuconfig

# DTS 编译
dtc -I dtb -O dts build/zephyr/zephyr.dts
```

### 目录结构

```
my_project/
├── CMakeLists.txt
├── prj.conf              # Kconfig
├── boards/
│   └── <board>.overlay   # DTS overlay
├── src/
│   └── main.c
└── west.yml              # manifest
```
