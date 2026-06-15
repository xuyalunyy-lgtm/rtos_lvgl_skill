# JL 杰理芯片平台专档

Agent 确认目标平台为杰理（JL / Jieli）系列时读取本文件。

适用芯片：AC79x（AC791N/AC792N AIoT）、AC69x（AC696N/AC695N 蓝牙音频）、AC63x（AC632N BLE）、AC70x 等。

SDK 文档：https://doc.zh-jieli.com/

## 关键差异速览

| 项目 | 杰理 SDK 惯例 | 注意 |
|------|--------------|------|
| RTOS API | **OS API**（`os_task_create`）+ **thread API**（`thread_fork`） | 非裸 `xTaskCreate`，勿与 ESP-IDF 混用 |
| 任务注册 | `task_info_table[]` 静态表 + 动态 `thread_fork` | 常驻任务放表；临时任务用 thread API |
| 任务优先级 | 数字**越大**越高，范围通常 0–31 | 与 STM32 相反，与 ESP-IDF 类似 |
| 任务延时 | `thread_delay_ms(n)` / `os_time_dly(n)` | 任务循环中**必须**让出 CPU，禁止忙等 |
| 音频 | `audio_server` 服务（enc/dec） | 不走裸 I2S 寄存器，经 server 事件回调 |
| 网络 | AC79 内置 WiFi + LwIP | WSS/URL 播放走 SDK 网络模块 |
| UI | LVGL（AC79 带屏方案） | 须在 LVGL 任务或 `lv_async_call` 中刷新 |
| 编译 | 杰理 GCC + CodeBlocks / Makefile | 烧录用 JLFlashTool |

## 推荐任务优先级（杰理风格）

```c
/* 数值越大优先级越高；以下为 AC792N 常见区间参考 */
#define AUDIO_SERVER_PRIO    (8)    /* 音频采集/播放 — 最高 */
#define NET_WSS_PRIO         (6)    /* WiFi / WSS 长连接 */
#define LVGL_TASK_PRIO       (4)    /* LVGL 刷新 */
#define APP_PRESENTER_PRIO   (3)    /* Presenter 业务状态机 */
#define USER_BG_PRIO         (2)    /* 低频后台 */
```

输出优先级表时**同时给出相对顺序和杰理数值**，并注明具体芯片 SDK 版本可能有差异。

## 任务创建：两种方式

### 方式 A — task_info_table 静态注册（常驻任务）

```c
/* app_main.c 或 app_task.c — 系统自动遍历创建 */
#define USER_STACK_SIZE   (512)   /* 单位：word，具体以 SDK 宏为准 */

const struct task_info task_info_table[] = {
    {"app_core",    1,  USER_STACK_SIZE, 0},
    {"audio_enc",   AUDIO_SERVER_PRIO, 768, 0},
    {"net_wss",     NET_WSS_PRIO, 1024, 0},
    {"lvgl_ui",     LVGL_TASK_PRIO, 1024, 0},
    {"presenter",   APP_PRESENTER_PRIO, 512, 0},
    {NULL, NULL, 0, 0},   /* ⚠️ 必须以此结尾，否则遍历越界死机 */
};
```

各任务入口函数须在 `app_config.c` 或对应模块中实现，函数内为 `while(1)` 死循环 + `thread_delay_ms()`。

### 方式 B — thread_fork 动态创建（临时/按需任务）

```c
/* 动态创建 WSS 解析任务 */
int pid;
thread_fork("wss_parse", NET_WSS_PRIO, 1024, 0, &pid, wss_task_entry, NULL);

static void wss_task_entry(void *parm)
{
    (void)parm;
    for (;;) {
        /* 网络接收 + cJSON 解析 */
        thread_delay_ms(10);   /* 必须延时，禁止忙等 */
    }
}
```

- 栈大小单位以 SDK 头文件注释为准（多数为 **word**）。
- **禁止**在中断/音频硬件回调中调用 `thread_fork`、`os_sem_pend` 等阻塞 API。

## 音频开发（Model 层）

杰理音频走 `audio_server`，不直接操作 I2S 寄存器：

```c
#include "server/audio_server.h"

/* 打开录音服务 */
void *audio_hdl = server_open("audio_server", "enc");
server_register_event_handler(audio_hdl, NULL, audio_enc_event_handler);

static void audio_enc_event_handler(void *priv, int argc, int *argv)
{
    int event = argv[0];
    switch (event) {
    case AUDIO_SERVER_EVENT_ERR:
        /* xQueue / 自定义事件送 Presenter，禁止 lv_obj_* */
        break;
    case AUDIO_SERVER_EVENT_END:
        break;
    default:
        break;
    }
}
```

- 编码格式：OPUS、MP3、PCM、WAV 等，由 server 参数指定。
- 音频事件回调在 **server 任务上下文**，等效于后台任务 — **禁止直接改 UI**。
- DMA 双缓冲由 SDK 内部管理；用户层只需处理 server 事件和 PCM 数据流。
- 播放：`server_open("audio_server", "dec")` + URL/文件路径。

## 网络 / WSS（Model 层，AC79 AIoT）

```c
/* 网络事件回调 — 禁止 lv_obj_* */
static void net_event_callback(void *priv, int event, void *data)
{
    switch (event) {
    case NET_EVENT_CONNECTED:
        net_emit_event(NET_EVT_CONNECTED, NULL, 0);
        break;
    case NET_EVENT_DATA:
        /* cJSON 解析后 Queue 送 Presenter */
        break;
    default:
        break;
    }
}
```

- AC79 网络栈集成在 SDK 中，WSS 握手栈开销大，任务栈建议 ≥ 4096 bytes。
- cJSON 解析后**立即** `cJSON_Delete`，payload 用 `malloc` 或 SDK 内存池，Presenter 负责释放。
- WiFi 配网、重连逻辑放在独立 Model 任务，不耦合 View。

## LVGL 集成（AC79 带屏方案）

- LVGL 在专用 `lvgl_ui` 任务中调用 `lv_timer_handler()` + `thread_delay_ms(5)`。
- 跨任务刷新：优先 `lv_async_call()`；或使用 `os_mutex` 保护（见 prompts/lvgl_thread_safety.txt）。
- **禁止**在 `audio_enc_event_handler`、`net_event_callback` 中调用 `lv_label_set_text`。
- UI 代码放 `ui_view_manager.c`；Designer 导出的页面在 View 层初始化。

## OS API 速查（与 FreeRTOS 对照）

| 杰理 OS API | FreeRTOS 等价 | 备注 |
|-------------|--------------|------|
| `os_task_create(...)` | `xTaskCreate(...)` | 动态任务 |
| `os_task_create_static(...)` | `xTaskCreateStatic(...)` | 减碎片，常驻任务推荐 |
| `os_sem_create / os_sem_pend` | `xSemaphoreCreate / xSemaphoreTake` | ISR 中禁用 pend |
| `os_mutex_create / os_mutex_pend` | 互斥锁 | LVGL 保护可用 |
| `os_q_create / os_q_pend` | `xQueueCreate / xQueueReceive` | Presenter 事件队列 |
| `thread_fork(...)` | 封装版任务创建 | 最常用 |
| `thread_delay_ms(n)` | `vTaskDelay(ms)` | 任务循环必用 |

## 内存与调试

- 常驻任务优先 `os_task_create_static` / 静态栈，减少碎片。
- 网络循环中避免高频 `cJSON_Parse` + `free`；考虑复用解析缓冲或 jsmn 流式。
- 调试输出：`printf` / `log_i`（AC79 SDK 日志宏），注意不要在音频中断中打印。
- 栈水位：查阅 SDK 是否提供 `stack_check` 或 task info 调试命令。

## 常见 Crash / 异常定位

| 现象 | 杰理特有原因 |
|------|-------------|
| 开机即死机 | `task_info_table` 末尾未加 `{NULL, NULL, 0, 0}` |
| 音频卡顿 / 爆音 | 音频回调中阻塞或调用 `thread_delay_ms` |
| UI 花屏 / 死机 | 网络/音频回调中直接 `lv_obj_*` |
| WiFi 连上但 WSS 失败 | 系统时间未同步；证书/域名配置错误 |
| 内存越来越紧 | 动态 `thread_fork` 频繁创建销毁；cJSON 未 Delete |

## SDK 深度裁剪（杰理 SDK）

### 配置入口

- `app_config.h` / `board_config.h` — 功能宏开关
- `Makefile` / CodeBlocks 工程 — 源文件列表
- `task_info_table[]` — 常驻任务表

### 优先关闭项

| 类别 | 位置 | 未用时操作 |
|------|------|-----------|
| 蓝牙 | `app_config.h` | `TCFG_USER_BT_CLASSIC_ENABLE=0` 等 |
| 未用 codec | audio 配置宏 | 只留 OPUS/PCM，关 MP3/AAC/WMA/... |
| 文件系统 | 配置宏 | 无 SD/U盘则关 `TCFG_SD_*` / FAT |
| 网络 | AC79 网络宏 | 无 WiFi 则关；有则缩缓冲 |
| Demo 应用 | `apps/` 目录 | 删未用 demo 子目录，只留目标 app |
| 在线 DB / 提示音 | 资源目录 | 删未用 `.mp3`/`.bin` 资源包 |
| 调试 CLI | `task_info_table` | 删 `systimer`/`usb_msd` 等 Demo 任务 |

### task_info_table 裁剪（关键）

```c
/* 裁剪前：SDK Demo 可能有 10+ 条目
 * 裁剪后：只留 app_core + audio + net + lvgl + presenter */
const struct task_info task_info_table[] = {
    {"app_core",  1, 512, 0},
    {"audio_enc", 8, 768, 0},
    {"net_wss",   6, 1024, 0},
    {"lvgl_ui",   4, 1024, 0},
    {NULL, NULL, 0, 0},   /* 必须保留 */
};
```

每删一条 → 确认对应 `xxx_task()` 入口不再被 `#include` 或链接。

### 杰理裁剪验证

- 编译看 `.map` / SDK 自带 size 脚本（若有）
- 用 SDK 日志或 `mem_stats()` 类 API 看堆剩余
- 开机后列任务：确认无多余 Demo 任务运行

## 文件归属惯例（AC79 AIoT 工程）

```
apps/                       # 或 cpu/wl82/tools/ 下应用目录
├── app_main.c              # 入口，task_info_table
├── app_config.c            # 任务入口函数注册
├── network_wss_task.c      # Model — WSS / WiFi
├── app_presenter.c         # Presenter
├── ui_view_manager.c       # View — LVGL
└── audio_model.c           # Model — audio_server 封装
include/
└── app_mvp.h               # 跨层事件结构体
```

## 与其他平台的差异提醒

| 对比项 | 杰理 JL | ESP32 | STM32 |
|--------|---------|-------|-------|
| 任务 API | `thread_fork` / `os_task_create` | `xTaskCreate` | `xTaskCreate` / `osThreadNew` |
| 音频 | `audio_server` | 裸 I2S driver | HAL I2S + DMA |
| 优先级方向 | 大数高 | 大数高（IDF） | 小数高 |
| 静态任务表 | `task_info_table` 必须 | 无 | 无 |
