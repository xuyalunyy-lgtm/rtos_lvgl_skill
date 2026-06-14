# JL 杰理芯片平台专档

Agent 确认目标平台为杰理（JL / Jieli）系列时读取本文件。

**本专档基于实测 SDK：** `fw-AC79_AIoT_SDK`（AC79NN tag `AC79NN_SDK_V1.2.13_2026-04-20`，WL82/AC791N）

| 项 | 值 |
|----|-----|
| 版本源 | `apps/common/system/version.c` → `sdk_version()` |
| cfg_tool | `AC791N-v0.01-cfg_tool-v0.10`（`cpu/wl82/tools/script.ver`） |
| 官方文档 | https://doc.zh-jieli.com/AC79/zh-cn/master/index.html |

适用芯片：AC791N/AC792N（AC79x AIoT）、AC69x 音频、AC63x BLE 等。**AC79 与 AC69 工程结构不同**，本文以 AC79 AIoT 为准。

---

## SDK 目录地图（Phase A 扫描结果）

```
fw-AC79_AIoT_SDK/
├── apps/                    # 应用工程 + apps/common/ 公共代码
│   ├── common/              # net、audio、UI、ASR、example/lvgl_v8|v9
│   ├── demo/                # 官方 Demo（wifi/ui/audio/hello/...）
│   ├── wifi_story_machine/  # 全功能产品（勿作裁剪起点）
│   ├── wifi_camera/ wifi_ipc/ scan_box/
│   └── <app>/board/wl82/    # 各 app 实际 Makefile 入口
├── cpu/wl82/                # 芯片相关：liba/、linker、tools/ 烧录输出
├── include_lib/             # 公共头文件（⚠️ 非 include/）
│   ├── system/os/os_api.h
│   ├── server/audio_server.h
│   ├── net/wifi/wifi_connect.h
│   └── utils/event/net_event.h
├── lib/                     # 预编译库（lib/net/、lib/server/）
├── tools/ sdk_tools/ doc/ ui_project/
├── init_env.sh              # Linux 工具链下载到 /opt/jieli
└── Makefile                 # 根调度：make ac791n_<app>
```

### apps/ 子工程一览

| 类型 | 工程 | 用途 |
|------|------|------|
| 最小 | `demo_hello` | 任务/OS 入门 |
| WiFi | `demo_wifi` | **IoT 联网最小基线** |
| WiFi 扩展 | `demo_wifi_ext` | WiFi 进阶示例 |
| UI | `demo_ui` | LVGL / JL UI 任务 |
| 音频 | `demo_audio` | audio_server |
| BLE | `demo_ble` | BLE 协议栈 |
| 经典蓝牙 | `demo_edr` | EDR 蓝牙 |
| 视频 | `demo_video` / `demo_uvc` | 摄像头 / UVC |
| Matter | `demo_matter` | Matter 协议 |
| 全功能板 | `demo_DevKitBoard` | 外设齐全，裁剪起点偏重 |
| 扫码盒 | `scan_box` | 扫码产品 |
| 产品级 | `wifi_camera` / `wifi_ipc` / `wifi_story_machine` | 完整产品；**禁止作首版裁剪底** |

### 模块依赖链（IoT + 屏 + 语音典型）

```
app_config.h 宏开关
  → task_info_table（tcpip/WiFi/UI/audio 任务）
  → wifi_on() / config_network_*
  → SYS_NET_EVENT / net_event.h
  → audio_server enc/dec（Model）
  → lvgl_main_task 或 ui/lcd_task_*（View）
```

---

## SDK 全景扫描（裁剪前强制）

**动刀前必须完成 Phase A**，输出模块地图。详见 [prompts/sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt)。

```
Phase A — 只读扫描
  ├── 读 apps/<target>/include/app_config.h 全部 CONFIG_/TCFG_
  ├── 读 apps/<target>/app_main.c → task_info_table[] + irq_info_table[]
  ├── 确认 Makefile 目标：make ac791n_<app>
  ├── 编译一次，记录 cpu/wl82/tools/sdk.map 大小
  └── 列出 apps/common/ 中被 Makefile 链入的模块

Phase B — 产品需求问卷 → 需求↔模块对照表
Phase C — 按需求裁剪，每步 make + 冒烟
```

扫描模板：

```markdown
| SDK 模块 | 路径/宏 | 基线 | 用户需求 | 处置 |
|----------|---------|------|----------|------|
| WiFi | CONFIG_WIFI_ENABLE, demo_wifi task_info | 开 | 要 | 保留 tcpip/Rtmp* 任务 |
| BT | CONFIG_BT_ENABLE, TCFG_USER_BT_* | 开 | 不要 | app_config 关宏 + 删任务 |
| OPUS | CONFIG_OPUS_ENC_ENABLE | 开 | 要 | 保留，关 MP3/AAC |
| LVGL | USE_LVGL_UI_DEMO, lvgl_main.c | 关 | 要 | 从 demo_ui 合入 |
```

---

## 编译系统

### 工具链

| 环境 | 路径 | 编译器 |
|------|------|--------|
| Windows | `C:/JL/pi32/bin` | `clang.exe`、`pi32v2-lto-wrapper.exe` |
| Linux | `/opt/jieli/pi32v2/bin` | `clang`、`lto-wrapper` |

Linux 环境：`init_env.sh` 或 http://pkgman.jieliapp.com/doc/all

典型编译 flags（`apps/demo/demo_wifi/board/wl82/Makefile`）：`-target pi32v2 -mcpu=r3 -mfprev1 -Oz -flto`

### 编译 / 清理命令

```bash
# 在 SDK 根目录 — 全部 Makefile 目标
make ac791n_wifi_camera
make ac791n_scan_box
make ac791n_wifi_ipc
make ac791n_wifi_story_machine
make ac791n_demo_demo_ble
make ac791n_demo_demo_wifi_ext
make ac791n_demo_demo_edr
make ac791n_demo_demo_ui
make ac791n_demo_demo_hello
make ac791n_demo_demo_devkitboard
make ac791n_demo_demo_uvc
make ac791n_demo_demo_video
make ac791n_demo_demo_audio
make ac791n_demo_demo_wifi          # IoT 最小 Demo 推荐

make clean_ac791n_demo_demo_wifi    # 清理对应工程（前缀 clean_）

# 或进入 app 板级目录
cd apps/demo/demo_wifi/board/wl82
make && make clean
```

### 输出产物

| 阶段 | 文件 | 路径 |
|------|------|------|
| ELF | `sdk.elf` | `cpu/wl82/tools/` |
| Map | `sdk.map` | `cpu/wl82/tools/` |
| App 段 | `app.bin` | `.text+.data+.dynamic_data+.ram0_data+.cache_ram_data` 拼接 |
| 烧录固件 | `jl_isd.fw` | `cpu/wl82/tools/` |
| OTA 包 | `*.ufw` | `ufw_maker.exe` 生成 |
| 烧录脚本 | `download.bat` | 由 `download.c` 生成 |

Post-build：`isd_download.exe` + `isd_config.ini` + `uboot.boot` + `app.bin` + 可选 UI/音频资源。

烧录：`cpu/wl82/tools/download.bat`（Windows）/ `isd_download.exe`

---

## 关键差异速览

| 项目 | AC79 SDK 实测 | 注意 |
|------|--------------|------|
| 头文件 | `include_lib/` | 非 `include/` |
| RTOS API | `os_api.h`：`thread_fork` / `os_task_create` | 非裸 `xTaskCreate` |
| 任务注册 | `task_info_table[]` in `app_main.c` | 须注册到任务列表 |
| 优先级 | **数字越大越高**（如 `sys_event`=29） | 与 STM32 相反 |
| 栈 / 队列 | `struct task_info.stack_size` 单位 **word（4B）** | 见 `include_lib/system/task.h` |
| 表结尾 | `{0,0}` 或 `{0,0,0,0,0}` | ⚠️ 非 `{NULL,NULL,0,0}` |
| 静态栈 | 第 5 字段 `tcb_stk_q` | `sizeof(StaticTask_t) + STK_SIZE*4 + ...` |
| 日志 | `printf` + `CONFIG_DEBUG_ENABLE` | 非仅 `log_i` |
| 音频 | `server_open("audio_server","enc/dec")` | 禁止裸 I2S 寄存器 |
| 网络 | `wifi_on()` + `SYS_NET_EVENT` | LwIP 2.2 + mbedTLS 3.4 |
| LVGL | `lvgl_main.c` → `thread_fork(..., prio 1, ...)` | 官方要求低优先级 |
| 延时 | `thread_delay_ms` / `os_time_dly` / `msleep` | 任务循环必须让出 CPU |

---

## task_info_table（实测规范）

定义见 `include_lib/system/task.h`：

```c
struct task_info {
    const char *name;   /* 任务名，须唯一 */
    u8 prio;            /* 越大越高 */
    u32 stack_size;     /* word 为单位 */
    u16 qsize;          /* 消息队列 word 数，0=无 */
    u8 *tcb_stk_q;      /* 静态栈/队列，NULL=动态分配 */
};
```

**表结尾：** 各 app 不一致，常见 `{0, 0}`、`{0, 0, 0, 0, 0}` 或 `{0, 0};`，**不是**统一的 `{NULL, NULL, 0, 0}`。

### 全部 `task_info_table[]` 位置（16 处）

| App | 路径 |
|-----|------|
| demo_audio | `apps/demo/demo_audio/app_main.c` |
| demo_ble | `apps/demo/demo_ble/app_main.c` |
| demo_DevKitBoard | `apps/demo/demo_DevKitBoard/app_main.c` |
| demo_edr | `apps/demo/demo_edr/app_main.c` |
| demo_hello | `apps/demo/demo_hello/app_main.c` |
| demo_matter | `apps/demo/demo_matter/app_main.c` |
| demo_ui | `apps/demo/demo_ui/app_main.c` |
| demo_uvc | `apps/demo/demo_uvc/app_main.c` |
| demo_video | `apps/demo/demo_video/app_main.c` |
| demo_wifi | `apps/demo/demo_wifi/app_main.c` |
| demo_wifi_ext | `apps/demo/demo_wifi_ext/app_main.c` |
| scan_box | `apps/scan_box/app_main.c` |
| wifi_camera | `apps/wifi_camera/app_main.c` |
| wifi_ipc | `apps/wifi_ipc/app_main.c` |
| wifi_story_machine | `apps/wifi_story_machine/app_main.c`（50+ 行） |
| 文档示例 | `apps/common/example/system/os/os_api/static_task_test.c` |

### demo_hello 最小集

```c
{"app_core",  15, 2048, 1024},
{"sys_event", 29,  512,    0},
{"systimer",  14,  256,    0},
{"sys_timer",  9,  512,  128},
{0, 0, 0, 0, 0},
```

### demo_wifi 实测（WiFi 最小集）

```c
/* apps/demo/demo_wifi/app_main.c */
const struct task_info task_info_table[] = {
    {"app_core",         15, 2048, 1024},
    {"sys_event",        29,  512,    0},
    {"systimer",         14,  256,    0},
    {"sys_timer",         9,  512,  128},
    {"tcpip_thread",     16,  800,    0},
    {"tasklet",          10, 1400,    0},
    {"RtmpMlmeTask",     17,  700,    0},
    {"RtmpCmdQTask",     17,  300,    0},
    {"wl_rx_irq_thread",  5,  256,    0},
    {0, 0, 0, 0, 0},
};
```

### demo_ui 常见 UI 任务（`CONFIG_UI_ENABLE`）

```c
{"ui",          21,  768, 256},
{"lcd_task_0",   8, 1024,  32},
{"lcd_task_1",   8, 1024,  32},
{"te_task",      9, 1024,  32},
```

### MVP 裁剪后目标形态（示例）

```c
/* 仅保留业务必需；优先级保持相对顺序 */
{"app_core",    15, 2048, 1024},
{"sys_event",   29,  512,    0},
{"tcpip_thread",16,  800,    0},
/* WiFi 相关按 demo_wifi 保留或缩减 */
{"net_wss",     12, 1536,    0},   /* thread_fork 创建的 WSS 可不入表 */
{"lvgl_main_task", 1, 8192, 0},   /* LVGL 官方用低优先级 1，栈 8K words */
{0, 0, 0, 0, 0},
```

**裁剪规则：** 每删一行确认无代码再创建该任务；`wifi_story_machine` 有 50+ 行，须逐项对照需求删。

---

## 推荐任务优先级（相对顺序）

实测参考（**数值越大越高**）：

| 任务 | demo 中 prio | 相对角色 |
|------|-------------|----------|
| `sys_event` | 29 | 系统事件分发 |
| `ui` | 21 | JL 原生 UI（非 LVGL） |
| `RtmpMlmeTask` / `RtmpCmdQTask` | 17 | WiFi 协议 |
| `tcpip_thread` | 16 | LwIP |
| `app_core` | 15 | 应用主任务 |
| `tasklet` | 10 | WiFi 软中断任务 |
| `wl_rx_irq_thread` | 5 | WiFi RX |
| `lvgl_main_task` | **1** | LVGL（故意最低，避免卡顿） |

输出优先级表时写**相对顺序 + 实测 prio**，并注明 `stack_size` 为 **words**。

---

## OS API

**头文件：** `include_lib/system/os/os_api.h`

```c
int os_task_create(void (*func)(void *), void *parm,
                   u8 prio, u32 stk_size, int q_size, const char *name);

int os_task_create_static(..., u8 *tcb_stk_q);

int thread_fork(const char *thread_name, int prio, int stk_size, u32 q_size,
                int *pid, void (*func)(void *), void *parm);

void thread_delay_ms(u32 ms);
void os_time_dly(u32 ticks);
```

| 杰理 API | 用途 |
|----------|------|
| `thread_fork` | WSS/Presenter/LVGL 等动态任务（最常用） |
| `os_task_create` | demo_hello 等简单任务 |
| `os_task_create_static` | 配合 `tcb_stk_q` 静态分配 |
| `thread_kill` | 终止 `thread_fork` 创建的任务 |
| `os_sem_*` / `os_mutex_*` / `os_q_*` | 同步与队列 |

**禁止**在 ISR/音频硬件回调中使用 `os_sem_pend`、`thread_delay_ms` 等阻塞 API。

---

## 音频（Model 层）— audio_server

**头文件：** `include_lib/server/audio_server.h`、`include_lib/system/server/server_core.h`

```c
void *enc = server_open("audio_server", "enc");
void *dec = server_open("audio_server", "dec");
server_register_event_handler(hdl, priv, audio_event_handler);
```

其他 server：`server_open("ai_server", NULL)`、`server_open("video_server", ...)`

事件类型（`audio_server.h`）：

```c
AUDIO_SERVER_EVENT_CURR_TIME   /* 0x20 */
AUDIO_SERVER_EVENT_END
AUDIO_SERVER_EVENT_ERR
AUDIO_SERVER_EVENT_SPEAK_START /* VAD 开始 */
AUDIO_SERVER_EVENT_SPEAK_STOP  /* VAD 结束 */
```

- 回调在 **server 任务上下文** — 禁止 `lv_obj_*`，须发消息给 Presenter
- 编解码格式由 `app_config.h` 控制：`CONFIG_OPUS_ENC_ENABLE`、`CONFIG_PCM_ENC_ENABLE` 等
- IOCTL：`AUDIO_REQ_ENC` / `AUDIO_REQ_DEC` / `AUDIO_REQ_IOCTL` + `AUDIO_ENC_OPEN` / `AUDIO_DEC_OPEN` 等

---

## 网络 / WiFi（Model 层）

**关键路径：**

| 组件 | 路径 |
|------|------|
| WiFi API | `include_lib/net/wifi/wifi_connect.h` |
| LwIP | `include_lib/net/lwip_2_2_0/` |
| mbedTLS | `include_lib/net/mbedtls_3_4_0/` |
| 配网 | `apps/common/net/config_network.c`、`config_network.h` |
| 网络事件 | `include_lib/utils/event/net_event.h` |
| WiFi 静态库 | `cpu/wl82/liba/wl_wifi_sfc.a`、`lwip_2_2_0_sfc.a`、`wpasupplicant.a` |

### 初始化流程（典型 demo_wifi）

1. **静态任务**（`task_info_table`）：`tcpip_thread`、`tasklet`、`RtmpMlmeTask`、`RtmpCmdQTask`、`wl_rx_irq_thread`
2. **App 任务**（如 `wifi_demo_task.c`）：
   ```c
   wifi_set_store_ssid_cnt(NETWORK_SSID_INFO_CNT);
   wifi_set_event_callback(wifi_event_callback);
   wifi_on();   /* 之后可启动网络应用 */
   ```
3. **配网**（可选）：`config_network_start()` → SMP/Airkiss/BLE/QR → `config_network_stop()` → `config_network_connect()` → `wifi_sta_connect(ssid, pwd, save)`
4. **应用事件**（`event_handler` 中 `SYS_NET_EVENT`）：
   ```c
   switch (net_event->event) {
   case NET_EVENT_CONNECTED:
   case NET_EVENT_DISCONNECTED:
   case NET_EVENT_SMP_CFG_FINISH:
   case NET_CONNECT_TIMEOUT_NOT_FOUND_SSID:
   case NET_CONNECT_ASSOCIAT_FAIL:
   case NET_NTP_GET_TIME_SUCC:   /* TLS 前须 NTP */
       break;
   }
   ```

- WSS/TLS 栈在 LwIP + mbedTLS 3.4 上；`thread_fork` 创建的网络任务栈建议 **≥ 1536 words（6144B）**
- cJSON 解析在 Model 任务，结果经 `os_q_*` 或自定义队列送 Presenter
- **禁止**在 `SYS_NET_EVENT` 回调里直接刷新 LVGL

---

## LVGL 集成（View 层）

**源码：** `apps/common/example/third_party/lvgl_v8/lvgl_main.c`（v9 在 `lvgl_v9/`，DevKitBoard Makefile 可引用 v9）

启用宏：`USE_LVGL_UI_DEMO`（`demo_ui` / `demo_DevKitBoard` 的 `app_config.h` 或 `demo_config.h`）

```c
static void lvgl_main_task(void *priv)
{
    lv_init();
    lv_port_disp_init();
    lv_port_indev_init();
    lv_port_fs_init();
    while (1) {
        u32 t = lv_timer_handler();
        if (t >= 1000 / OS_TICKS_PER_SEC) msleep(t);
    }
}

/* 官方注释：LVGL 须最低优先级，高优先级任务不能长时间占 CPU */
thread_fork("lvgl_main_task", 1, 8 * 1024, 0, 0, lvgl_main_task, NULL);
late_initcall(lvgl_main_task_init);
```

- 跨任务刷新：优先 `lv_async_call()`；或 `os_mutex` 保护
- JL 原生 UI（非 LVGL）：`ui` / `lcd_task_*` / `te_task` 任务 + `CONFIG_UI_ENABLE`
- UI 资源：`ui_project/`、`CONFIG_UI_PATH_FLASH`、`CONFIG_UI_PACKRES_LEN`

---

## 最小工程 fork 建议（IoT + LVGL + WiFi）

| 方案 | 优点 | 缺点 |
|------|------|------|
| **1. `demo_wifi` + 合入 LVGL** | WiFi 栈最小；联网流程清晰 | 须手动加 UI 任务 / lvgl 源与 Makefile |
| **2. `demo_ui` + WiFi 宏** | LVGL 现成 | 默认无 WiFi 任务与事件 |
| **3. 裁剪 `demo_DevKitBoard`** | WiFi + LVGL + 外设示例齐全 | 偏重（BT/视频/USB）；须剪 `demo_config.h` |

**推荐起点：** 方案 1 — `demo_wifi`（`make ac791n_demo_demo_wifi`）

```
1. 复制 apps/demo/demo_wifi → apps/<your_product>/
2. 从 demo_ui 合入 USE_LVGL_UI_DEMO + lvgl_v8 源文件与 Makefile 片段
3. 按需求裁剪 app_config.h 宏与 task_info_table
4. 新增 network_wss_task.c / app_presenter.c / ui_view_manager.c（MVP）
```

**勿从 `wifi_story_machine` 删功能起步**（任务表 50+ 行，BT/视频/USB 全捆绑）。

---

## app_config.h 关键宏（裁剪候选项）

> 须需求确认后再关闭。路径：`apps/<app>/include/app_config.h`  
> 板级：`apps/<app>/board/wl82/board_config.h` → `CONFIG_BOARD_*` + `board_7916AA_cfg.h`

| 类别 | 宏（实测名） |
|------|-------------|
| Flash/SDRAM | `__FLASH_SIZE__`（常见 8MB）、`__SDRAM_SIZE__`（8MB 或 0）、`CONFIG_NO_SDRAM_ENABLE` |
| 网络 | `CONFIG_NET_ENABLE`、`CONFIG_WIFI_ENABLE`、`CONFIG_RF_TRIM_CODE_AT_RAM` / `CONFIG_RF_TRIM_CODE_MOVABLE` |
| 配网 | `CONFIG_AIRKISS_NET_CFG`、`CONFIG_QR_CODE_NET_CFG`、`CONFIG_ASSIGN_MACADDR_ENABLE` |
| 蓝牙 | `CONFIG_BT_ENABLE`、`TCFG_USER_BT_CLASSIC_ENABLE`、`TCFG_USER_BLE_ENABLE`、`TCFG_USER_TWS_ENABLE`、`CONFIG_BT_RX_BUFF_SIZE` |
| 音频 | `CONFIG_AUDIO_ENABLE`、`CONFIG_AUDIO_MIX_ENABLE`、`CONFIG_OPUS_ENC/DEC_ENABLE`、`CONFIG_MP3_ENC/DEC_ENABLE`、`CONFIG_PCM_ENC/DEC_ENABLE`、`CONFIG_AEC_ENC_ENABLE`、`TCFG_EQ_ENABLE`、`TCFG_DRC_ENABLE` |
| 采样/播放 | `CONFIG_AUDIO_ENC_SAMPLE_SOURCE`、`CONFIG_AUDIO_DEC_PLAY_SOURCE`（如 `"dac"`） |
| 存储 | `TCFG_SD0/SD1_ENABLE`、`TCFG_SD_PORTS`、`TCFG_SD_DAT_WIDTH`（1/4 线）、`CONFIG_STORAGE_PATH`、`CONFIG_ROOT_PATH` |
| UI | `CONFIG_UI_ENABLE`、`USE_LVGL_UI_DEMO`、`CONFIG_UI_FILE_SAVE_IN_RESERVED_EXPAND_ZONE`、`CONFIG_UI_PACKRES_LEN`、`TCFG_LCD_ILI9341/ILI9488_ENABLE`、`TCFG_TOUCH_GT911/FT6236_ENABLE` |

---

## 内存与 Flash（AC791N 典型）

来自 `cpu/wl82/sdk_ld_sfc.c` / `sdk_ld_sdram.c`：

| 区域 | 典型配置 |
|------|----------|
| Flash (`rom`) | `ORIGIN = 0x2000120`，`LENGTH = __FLASH_SIZE__` |
| SDRAM | `ORIGIN = 0x4000120`，`LENGTH = __SDRAM_SIZE__` |
| 片上 SRAM (`ram0`) | `0x1c00000` + TLB，~578KB（README：双核 DSP，578K SRAM） |
| Cache RAM | `0x1f20000`，大小由 `FREE_DACHE_WAY` / `FREE_IACHE_WAY` 决定 |

Linker 选择：

- `CONFIG_NO_SDRAM_ENABLE` → `sdk_ld_sfc.c`
- 有 SDRAM → `sdk_ld_sdram.c`
- `CONFIG_SFC_ENABLE` → 代码在 Flash ROM 段

裁剪验证：`cpu/wl82/tools/sdk.map`

---

## 常见 Crash / 异常

| 现象 | AC79 原因 |
|------|-----------|
| 开机即死机 | `task_info_table` 缺结束行 `{0,0,...}`；或表项与任务不匹配 |
| LVGL 卡顿 | 高优先级任务长时间占用 CPU；违反 lvgl prio=1 设计 |
| UI 花屏 | 网络/音频回调直接 `lv_obj_*` |
| WSS/TLS 失败 | 未收 `NET_NTP_GET_TIME_SUCC`；证书或域名错误 |
| 栈溢出 | `stack_size` 单位误当 bytes（实为 words） |

---

## MVP 文件归属（AC79 实测路径）

```
apps/<your_product>/
├── app_main.c                 # task_info_table、irq_info_table
├── include/app_config.h       # 功能宏
├── board/wl82/
│   ├── Makefile               # 编译入口
│   └── board_config.h
├── network_wss_task.c         # Model — WiFi/WSS
├── app_presenter.c            # Presenter — Looper
├── ui_view_manager.c          # View — LVGL / lv_async_call
└── audio_model.c              # Model — audio_server 封装

apps/common/                     # 按需链入，勿整包复制
├── net/config_network.c
└── example/third_party/lvgl_v8/
```

---

## 快速参考路径

```
OS API:         include_lib/system/os/os_api.h
task_info:      include_lib/system/task.h
server_open:    include_lib/system/server/server_core.h
audio_server:   include_lib/server/audio_server.h
wifi_connect:   include_lib/net/wifi/wifi_connect.h
net_event:      include_lib/utils/event/net_event.h
config_network: apps/common/net/config_network.c
LVGL entry:     apps/common/example/third_party/lvgl_v8/lvgl_main.c
Build output:   cpu/wl82/tools/sdk.elf, app.bin, jl_isd.fw, *.ufw
Version:        apps/common/system/version.c
```

---

## 共享引擎：prompt + 云端 uplink（C10）

JL 播放/采集经 `audio_server`，与 BK 多 port 模型不同，但 **C10 时序铁律相同**：

| 项 | JL 做法 |
|----|---------|
| 播放结束 | 收 `AUDIO_SERVER_EVENT_END` / `SPEAK_STOP` 后再开麦 |
| dec 关闭 | prompt/TTS 用 `AUDIO_REQ_DEC` close，勿与 enc 并发占 ref |
| 回调 | `audio_event_handler` 在 server 任务 — 禁止直接 `lv_obj_*`；prompt 完成 → 发消息给 Presenter/会话任务 |
| settle | END 后 delay 80–150ms + 确认 enc 已 OPEN 且 VAD/AEC ready（`CONFIG_AEC_ENC_ENABLE`） |
| 诊断 | 对比两轮 peak；有 uplink 但 ASR 空 → 查 AEC/播放未关 |

深细节 → [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt)

---

## 与其他平台差异

| 对比项 | JL AC79 | ESP32 | STM32 |
|--------|---------|-------|-------|
| 任务 API | `thread_fork` / `os_task_create` | `xTaskCreate` | `xTaskCreate` / `osThreadNew` |
| 任务表 | `task_info_table` 必须 | 无 | 无 |
| 音频 | `audio_server` | I2S driver | HAL I2S |
| 优先级 | 大数高 | 大数高（IDF） | 小数高 |
| 栈参数 | words | words（IDF） | words 或 bytes |
| 编译 | `make ac791n_*` | `idf.py build` | CubeMX make |
