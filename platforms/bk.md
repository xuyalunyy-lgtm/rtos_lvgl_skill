# BK 博通集成（Beken）平台专档

Agent 确认目标平台为博通集成 BK 系列时读取本文件。

**本专档基线 SDK：** `bk_idk-release-v2.2.1`（Armino IDK，Tag 格式 `v2.2.1.x`）

| 项 | 值 |
|----|-----|
| 基线 repo | `bk_idk`（Armino 生态基础 SDK） |
| 版本源 | SDK 根目录 `README.md` / `git tag` / 编译日志 `APP_VERSION` |
| 官方文档 | https://docs.bekencorp.com/（芯片文档在 `docs/bk7239/`、`docs/bk7236n/`） |
| 烧录工具 | https://dl.bekencorp.com/tools/flash/（BKFIL） |
| 维护要求 | Phase A 扫描后在本表填写实测 tag，禁止照搬未验证版本号 |

适用芯片：**BK7258**（三核 AIoT/带屏主流）、BK7236/BK7236N、BK7239、BK7234 等 2022 年后芯片。BK7231/BK7251 等旧芯片**不在** Armino 支持范围。

---

## 目录

- [Armino 生态分层](#armino-生态分层)
- [SDK 目录地图](#sdk-目录地图phase-a-扫描--bk_idk-v221)
- [SDK 全景扫描](#sdk-全景扫描裁剪前强制)
- [环境部署与编译](#环境部署与编译)
- [配置体系](#配置体系)
- [关键差异速览](#关键差异速览)
- [应用入口与任务模板](#应用入口与任务模板bk_idk)
- [BK7258 三核架构](#bk7258-三核架构)
- [AVDK 扩展层](#avdk-扩展层bk_avdk_smp--方案仓)
- [网络 / WSS](#网络--wssmodel-层)
- [SDK 深度裁剪](#sdk-深度裁剪)
- [常见 Crash / 异常定位](#常见-crash--异常定位)
- [带屏 AI 语音产品实测模式](#带屏-ai-语音产品实测模式bk-avdk-ap-类)
- [带屏打印机产品实测](#带屏打印机产品实测bk_printer--bk7258)
- [与其他平台的差异](#与其他平台的差异)

---

## Armino 生态分层

```
bk_idk                    ← 基础 IDK（RTOS、WiFi、BT、驱动、LwIP、mbedTLS）
  └── bk_avdk / bk_avdk_smp   ← 多媒体扩展（LVGL、AVDK、摄像头、AP/CP 工程结构）
        └── bk_solution_ai / bk_solution_dashboard   ← 行业方案（beken_genie、scooter 等）
```

| 场景 | 使用哪个 SDK | 典型工程 |
|------|-------------|---------|
| WiFi IoT / 模组 / 安全启动 | **bk_idk** | `projects/app`、`projects/security/*` |
| 带屏 / 摄像头 / 语音 AI | **bk_avdk_smp** + 方案仓 | `lvgl/widgets`、`bk_solution_ai/projects/beken_genie` |
| SDK 裁剪起点 | 按产品选**最小**工程 fork | bk_idk 用 `app`；带屏用 `lvgl/widgets` |

**Agent 判断规则：** 用户工程含 `ap/`、`cp/` 目录或 LVGL/AVDK → 读本文「AVDK 扩展层」章节；纯 WiFi/模组 → 以 bk_idk 结构为准。

---

## SDK 目录地图（Phase A 扫描 · bk_idk v2.2.1）

```
bk_idk/
├── Makefile                     # 入口 → tools/build_tools/build_files/build_main.mk
├── dbuild.sh / dbuild.ps1       # Docker 编译（Windows 推荐）
├── components/                  # 可裁剪组件（见下表）
├── middleware/
│   ├── soc/                     # 芯片 defconfig + 链接脚本
│   │   ├── bk7258/              # CPU0 主核
│   │   ├── bk7258_cp1/          # CPU1 固件
│   │   └── bk7258_cp2/          # CPU2 固件
│   ├── driver/                  # HAL / 外设驱动
│   ├── arch/                    # CM33 架构
│   └── boards/                  # 板级校准等
├── projects/
│   ├── app/                     # 默认工程（main/app_main.c）
│   ├── security/                # 安全启动 Demo（xip / secureboot / overwrite）
│   └── properties_libs/         # 预编译属性库
├── docs/                        # 在线文档源（bk7239/、bk7236n/）
├── include/                     # 公共头（components/、os/、driver/）
├── properties/                  # 内部预编译库 / bootloader
└── tools/
    ├── build_tools/             # armino 构建系统、menuconfig
    └── env_tools/               # 环境脚本、BKFIL、分区工具、bk_py_libs
```

### middleware/soc 支持的构建目标

| defconfig | 说明 |
|-----------|------|
| `bk7234` | 单核 WiFi 6 |
| `bk7236` | 单核，默认 fallback SoC |
| `bk7236n` | BK7236 衍生 |
| `bk7239` | WiFi 6 + BLE 5.4 + TrustEngine |
| `bk7258` | 三核 SMP 主核（CPU0） |
| `bk7258_cp1` | BK7258 CPU1 固件 |
| `bk7258_cp2` | BK7258 CPU2 固件 |

BK7258 编译 `make bk7258` 时，`projects/app/pj_config.mk` 会自动预构建 `bk7258_cp1`、`bk7258_cp2`（`SUPPORT_TRIPLE_CORE=true`）。

### components/ 模块地图（裁剪参考）

| 类别 | 组件 | 未用时 |
|------|------|--------|
| RTOS | `bk_rtos`、`os_source` | 不可关 |
| 启动 | `bk_init`、`bk_startup`、`bk_system` | 不可关 |
| 网络 | `bk_wifi`、`bk_netif`、`lwip_intf_v2_1` | 无 WiFi 可评估关 WiFi 相关 |
| 协议 | `bk_httpc`、`bk_https`、`bk_websocket`、`webclient`、`http` | 按协议需求 |
| TLS | `mbedtls`、`psa_mbedtls`、`wolfssl` | 保留一个栈 |
| 蓝牙 | `bk_bluetooth` | 无 BLE 关 `CONFIG_BLE` |
| CLI | `bk_cli`、`at`、`at_server` | 量产关 `CONFIG_CLI` |
| OTA | `bk_ota`、`ota`、`https_ota` | 无 OTA 可关 |
| 存储 | `easy_flash`、`fatfs`、`littlefs`、`flashdb` | 按需求 |
| USB | `bk_usb` | 无 USB 关 |
| 安全 | `bk_trustengine`、`security`、`tfm`、`mcuboot` | 按安全方案 |
| 调试 | `coredump`、`cm_backtrace`（via Kconfig） | 量产可关 |
| Demo | `demos` | 不编入工程 |

---

## SDK 全景扫描（裁剪前强制）

**动刀裁剪之前，必须先整体扫描原厂 SDK**。BK 工程可能跨多个 repo（bk_idk + avdk + solution），禁止未扫描直接删代码。

```
Phase A — 只读扫描
  ├── 确认 SDK 层级（bk_idk / bk_avdk_smp / solution）
  ├── git tag / README 记录版本
  ├── 列出 projects/ 与（若有）ap/ cp/ 目录职责
  ├── 导出 projects/<app>/config/<soc>/config 全部 CONFIG_*
  ├── make bk7258 编译基线，记录 Flash/RAM / all-app.bin 大小
  ├── 列出 xTaskCreate / rtos_create_thread 与官方 init 顺序（bk_init 链）
  └── BK7258：确认 CPU0/1/2 分工与 mailbox IPC 边界

Phase B — 询问用户完整产品需求
  └── 需求驱动裁剪表（非固定模板）

Phase C — 从 projects/ 最小 Demo fork 新工程，按需求裁剪
```

扫描输出模板见 [prompts/sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt)。

---

## 环境部署与编译

### Linux（推荐本地编译）

```bash
# 环境脚本（Ubuntu ≥20.04 / Debian ≥11）
tools/env_tools/setup/armino_env_setup.sh

# SDK 根目录
make bk7258                              # 默认 projects/app
make bk7258 PROJECT=security/xip         # 指定工程
make menuconfig                          # Kconfig 交互配置
make cleanbk7258                         # 清理单 SoC
make build                               # 快速重编上次 SoC
```

也可在工程目录执行（`projects/app/Makefile` 自动定位 SDK）：

```bash
cd projects/app && make bk7258
```

### Windows

- **推荐：** Docker + 根目录 `dbuild.ps1`（镜像 `bekencorp/armino-idk`）
- **Git clone 注意：** 须 `core.symlinks=true`、`core.autocrlf=false`，管理员权限 clone（见官方 get-started）
- 本地裸编译仅官方支持 Linux；Windows 裸 make 易缺工具链

```powershell
.\dbuild.ps1 make bk7258
.\dbuild.ps1 make bk7258 PROJECT=app
```

### 编译产物

```
build/app/bk7258/all-app.bin     # 常规烧录文件
# 安全工程首次烧录：先 bootloader.bin，再 all-app.bin
```

### Skill 编译脚本（跨 repo 工作区）

Skill 提供 **`bk_build.sh`** / **`bk_build.ps1`**，放置在与 SDK **同级**的工作区根目录：

```
~/armino/
├── bk_idk/ 或 bk_avdk_smp/    ← SDK
├── bk_solution_ai/            ← 可选方案仓
├── bk_build.sh / bk_build.ps1
└── bk_build.env.example       ← 复制为 bk_build.env 配置默认工程
```

脚本自动探测 `bk_avdk_smp` / `bk_avdk` / 可设 `BK_SDK_DIR`；外部方案仓自动设置 `SDK_DIR`。

---

## 配置体系

**优先级（高 → 低）：**

```
projects/<app>/config/<soc>/config     # 工程级 override
  > middleware/soc/<soc>/<soc>.defconfig   # 芯片默认
  > components/*/Kconfig               # 组件 Kconfig 默认值
```

BK7258 三核各有独立 defconfig：`bk7258`、`bk7258_cp1`、`bk7258_cp2`。

### 常用 Kconfig（bk_idk）

```
CONFIG_FREERTOS_CHECK_STACKOVERFLOW=y
CONFIG_CLI=y / n                    # 量产关 CLI
CONFIG_BLE=y / n
CONFIG_LWIP_V2_1=y
CONFIG_MEM_DEBUG=y                  # 调试期开，量产关
CONFIG_APP_MAIN_TASK_PRIO=4
CONFIG_APP_MAIN_TASK_STACK_SIZE=4096
```

### 密钥覆盖（C9 · 产品工程）

```
ap/config/bk7258_ap/config              # 入库，SECRET=""
ap/config/bk7258_ap/config.secrets      # 本地，gitignore
ap/config/bk7258_ap/config.local        # merge 输出 → CONFIG_SUBSTITUTE_FILE
```

合并：`scripts/merge_config_secrets.sh ap/config/bk7258_ap` → 详见 [secrets_kconfig.txt](../prompts/secrets_kconfig.txt)

---

## 关键差异速览

| 项目 | Armino / bk_idk 惯例 | 注意 |
|------|---------------------|------|
| 内核 | FreeRTOS v10（BK7258 可选 SMP） | `components/bk_rtos/freertos/FreeRTOSConfig.h` |
| 线程 API | **`rtos_create_thread()`** 栈单位 **bytes** | 见 `include/os/os.h` 注释；优先于裸 `xTaskCreate` |
| 优先级 | `configMAX_PRIORITIES=10`，**数字越大越高** | 0–9；Timer 任务占 9 |
| 入口 | `main()` → `bk_init()` → `user_app_main()` | 在 `rtos_set_user_app_entry()` 注册 |
| 编译 | `make bk7258` | 默认工程 `projects/app` |
| 多核 | BK7258 三核 + mailbox | cp1/cp2 预编译；用户主逻辑在 CPU0 |
| 网络 | `bk_wifi` + `bk_netif` + LwIP 2.1 | 事件：`components/event.h` |
| 日志/CLI | `bk_cli` / shell | 串口 DL_UART0 |

---

## 应用入口与任务模板（bk_idk）

```c
/* projects/app/main/app_main.c — 官方入口模式 */
#include "bk_private/bk_init.h"
#include <components/system.h>
#include <os/os.h>

void user_app_main(void)
{
    /* 在此创建业务任务 */
}

int main(void)
{
#if (CONFIG_SYS_CPU0)
    rtos_set_user_app_entry((beken_thread_function_t)user_app_main);
#endif
    bk_init();   /* WiFi/BT/CLI/驱动初始化链 */
    return 0;
}
```

### Model 层任务（WSS / 网络）

```c
#include <os/os.h>

#define WSS_TASK_PRIO    7    /* configMAX_PRIORITIES=10，数字越大越高 */

void network_wss_task_start(void)
{
    beken_thread_t th = NULL;
    bk_err_t ret = rtos_create_thread(
        &th,
        WSS_TASK_PRIO,
        "wss",
        wss_task_entry,
        4096,                 /* bytes — os.h 明确标注 */
        NULL
    );
    BK_ASSERT(kNoErr == ret);
}

static void wss_task_entry(beken_thread_arg_t param)
{
    (void)param;
    for (;;) {
        /* 网络接收 — 禁止 lv_obj_* */
        rtos_delay_milliseconds(10);
    }
}
```

**栈单位：** `rtos_create_thread` / `rtos_create_sram_thread` 的 `stack_size` 为 **bytes**（`include/os/os.h`）。若使用底层 `xTaskCreate`，须核对当前 SDK 是否封装为 words。

### 推荐任务优先级（BK7258 参考）

```c
/* configMAX_PRIORITIES=10；Timer=9 已被占用 */
#define AUDIO_TASK_PRIO      8
#define WSS_TASK_PRIO        7
#define LVGL_TASK_PRIO       5
#define PRESENTER_TASK_PRIO  4
```

输出优先级表时**同时给出相对顺序和 SDK 配置依据**。WiFi 协议栈任务由 SDK 预置，用户任务勿占 priority 9。

---

## BK7258 三核架构

```
CPU0 (bk7258)      — 主应用、WiFi 控制面、用户任务
CPU1 (bk7258_cp1)  — 协处理器固件（media/WiFi 数据面等，依 Kconfig）
CPU2 (bk7258_cp2)  — 协处理器固件
IPC                — CONFIG_MAILBOX=y / MAILBOX_V2_0
```

- 用户业务代码通常在 **CPU0**（`CONFIG_SYS_CPU0`）的 `user_app_main` 中启动。
- CP 固件由 SDK 预构建，**勿随意改 cp 侧**除非明确分工需求。
- PSRAM 堆：各核 `CONFIG_PSRAM_HEAP_BASE/SIZE` 须协调（见官方 memory_perf 文档）。

---

## AVDK 扩展层（bk_avdk_smp + 方案仓）

带屏 / 摄像头 / 语音 AI 产品使用 **`bk_avdk_smp`**，工程结构变为 AP/CP 分离：

```
bk_avdk_smp/
├── projects/                # lvgl/widgets, lvgl/camera, lvgl/86box 等
├── middleware/
└── components/              # LVGL、media、display

bk_solution_ai/              # beken_genie, volc_rtc
bk_solution_dashboard/       # scooter 等
```

```bash
cd ~/armino/bk_solution_ai/projects/beken_genie
export SDK_DIR=~/armino/bk_avdk_smp
make bk7258
```

### 工程目录（AVDK 典型）

```
projects/<your_app>/
├── ap/                           # AP 侧应用（用户主战场）
│   ├── main.c
│   ├── network_wss_task.c        # Model
│   ├── app_presenter.c           # Presenter
│   ├── lvgl/lvgl_app_ui.c        # LVGL 任务
│   ├── beken_generated/        # Designer 导出（View）
│   └── CMakeLists.txt
├── cp/                           # CP 侧（通常不改）
└── config/bk7258/
```

### LVGL 集成（BK7258 带屏）

```c
static void lvgl_task(void *param)
{
    (void)param;
    lv_init();
    lv_port_disp_init();
    lv_port_indev_init();
    beken_ui_init();   /* BEKEN LVGL UI Designer 生成，仅 View 层 */

    for (;;) {
        lv_timer_handler();
        rtos_delay_milliseconds(5);
    }
}
```

**BEKEN LVGL UI Designer 工作流：**
1. Designer 拖拽 → 导出 C 到 `beken_generated/`
2. 复制到工程 `ap/`，改 `CMakeLists.txt`
3. `lvgl_app_ui.c` 中 `beken_ui_init()` 替换手写页面

**规则：** Designer 代码仅 View；事件回调只发消息给 Presenter；跨任务刷新用 `lv_async_call()`。

### 摄像头 / LVGL 切换

```bash
lvcam_open    # UVC 摄像头
lvcam_close   # 恢复 LVGL UI
```

切换时须释放显示资源，避免 DMA 与 LVGL 帧缓冲冲突。

### 音频 / 多媒体（AVDK）

- 录音/播放走 AVDK media API（`media_app`、`audio_interface` 等，以 SDK 版本为准）
- 音频回调在 media 任务上下文 — **禁止直接改 UI**
- 高实时场景须确认 AP/CP/CPU1 核分工

---

## 网络 / WSS（Model 层）

```c
/* 网络事件回调在 SDK 网络任务上下文 — 禁止 lv_obj_* */
static void wss_event_handler(int event, void *data)
{
    switch (event) {
    case WSS_EVENT_CONNECTED:
        net_emit_event(NET_EVT_CONNECTED, NULL, 0);
        break;
    case WSS_EVENT_DATA:
        /* cJSON_Parse → Queue → Presenter */
        break;
    case WSS_EVENT_DISCONNECTED:
        net_emit_event(NET_EVT_ERROR, NULL, 0);
        break;
    default:
        break;
    }
}
```

- TLS/WSS 握手栈开销大，任务栈建议 ≥ 4096 bytes。
- WiFi 连接走 `bk_wifi` + `event` 组件，Model 层监听 `EVENT_WIFI_*` 而非直接调寄存器。
- 解析后打包 `net_evt_t` 投 Queue，Presenter 调 `view_xxx()` 刷新。

---

## SDK 深度裁剪

> **以下仅为候选项**，须在产品需求问卷确认「不需要」后再关闭；禁止未询问用户直接套用。

### 配置入口

```bash
projects/<your_app>/config/bk7258/config          # 工程级
middleware/soc/bk7258/bk7258.defconfig            # 芯片默认
```

### 优先关闭项

| 类别 | Kconfig | 未用时 |
|------|---------|--------|
| 蓝牙 | `CONFIG_BLE` / `CONFIG_BT` | 无 BLE |
| CLI/调试 | `CONFIG_CLI`、`CONFIG_MEM_DEBUG` | 量产 |
| AT 指令 | `CONFIG_AT` | 非模组 |
| Demo/测试 | `CONFIG_DEMO_TEST`、各 `*_TEST` | 始终 |
| 未用协议 | `CONFIG_OTA_HTTP` 等 | 按需求 |
| LwIP 池 | lwip Kconfig | 缩 `MEM_SIZE`、连接数 |
| AVDK 摄像头 | `CONFIG_UVC` 等 | 无摄像头 |
| LVGL demo | `LV_MEM_SIZE` | 缩显存 |

### 工程选择（裁剪第一步）

**不要**在完整 `bk_solution_ai/beken_genie` 上直接删。正确流程：

```
1. 选最贴近产品的最小 Demo（bk_idk 用 app；带屏用 lvgl/widgets）
2. copy 为新工程目录
3. 删未用源文件 + 改 CMakeLists REQUIRES
4. Kconfig 逐项关未用功能
5. beken_generated 删未用页面/字库子集化
```

### 裁剪验证

```bash
make bk7258
# build/app/bk7258/ 查看 map / size
# 运行时：xPortGetMinimumEverFreeHeapSize()
# BK7258：每步缩 LwIP 后测 WiFi + WSS
```

---

## 常见 Crash / 异常定位

| 现象 | 原因 |
|------|------|
| 编译找不到 SDK | 方案仓未设 `SDK_DIR`；或不在 SDK 根 / projects 子目录执行 make |
| Windows clone 失败 | 软链接 / CRLF — 见 get-started  git config |
| 线程栈溢出 | `rtos_create_thread` 栈不足；查 `uxTaskGetStackHighWaterMark` |
| WiFi 连上 WSS 失败 | SNTP 未同步；证书；LwIP `MEM_SIZE` 不足 |
| LVGL 不显示（AVDK） | `beken_ui_init()` 未调；Designer 文件未入 CMakeLists |
| 摄像头与 UI 冲突 | UVC 与 LVGL 争显示通路 |
| 系统随机重启 | 栈溢出；ISR 阻塞；看 `cm_backtrace` dump |
| 多核异常 | mailbox 队列满；PSRAM 堆配置冲突 |

调试工具：https://dl.bekencorp.com/tools/Debug_tool/BK7258-debug.zip

---

## 带屏 AI 语音产品实测模式（BK AVDK AP 类）

以下模式来自 BK7258 带屏 AI 语音量产工程 review，可作为 AVDK AP 侧重构参考。

### RTOS 队列超时

```c
#define BEKEN_NO_WAIT       (0)           /* 非阻塞 */
#define BEKEN_WAIT_FOREVER  (0xFFFFFFFF)  /* 永久等待 */
```

`rtos_push_to_queue(..., 0)` **等于** `BEKEN_NO_WAIT`，不是永久阻塞。

### LVGL 跨线程：app_event → UI

推荐 **Presenter 桥接 + 递归锁**，而非在 network/audio 任务里直接 `lv_obj_*`：

```c
/* ui_app_evt_bridge.c — app_event 线程 */
lvgl_port_lock();
ui_dispatch_from_app_evt(msg->event, msg->param);
lvgl_port_unlock();

/* lvgl_port.c — GUI 线程重入安全 + 外部线程 lv_async_call */
lvgl_port_run_on_gui(fn, arg);
```

`lvgl_port_lock` 须识别 GUI 线程已在 `lv_timer_handler` 内持锁，避免非递归 mutex 自死锁。

### 应用事件总线

- `app_event_send_msg()`：`BEKEN_NO_WAIT` 投队列，**禁止**在 ISR/timer 回调里做 `bk_reboot_ex` 等重型操作
- 关键事件（Agent/网络/OTA/深睡）队列满时可短重试；深度建议 ≥32
- Timer 到期 → 仅 `app_event_send_msg(APP_EVT_xxx)` → 业务线程执行 reboot/停倒计时

### 栈参考（BK7258 + TLS/RTC）

| 任务 | 建议栈 (bytes) | 说明 |
|------|----------------|------|
| LVGL（PSRAM 线程） | 12288 | 含 SD 资源探测、路由 |
| Volc/Agora RTC | ≥10240 / ≥12248 | TLS + JSON + 信令；须 `uxTaskGetStackHighWaterMark` 实测 |
| vsm_worker / Duer | 6144+ | 语音状态机路径深 |

### 启动顺序（带 LVGL）

```
app_event_init → SD 挂载 → lcd bringup(LVGL task) → audio_engine → Duer → ntwk_trans
```

配网 `bk_sconf_init` **勿**在 LVGL 小栈同步调用；独立 `wifi_sconf` 任务（栈 ≥4096）。

### 共享引擎：prompt tone + 云端 uplink（C10）

AVDK `onboard_speaker_stream` 支持多 **port** attach；唤醒「叮」、本地 TTS 与 Mic uplink 共用 engine + AEC 时：

| 项 | 做法 |
|----|------|
| detach | `stop` **与** playback **FINISHED** 均 `detach` 对应 `port_id` |
| port_id | 来自 `prompt_tone` 配置，勿 hardcode `1` |
| 时序 | ding **FINISHED+detach** → **80–150ms** settle → `wait_mic_capture_ready` → `voice_start` / uplink tap |
| 诊断 | 对比第一轮 vs 第二轮 `mic peak` / `tap first frame peak`；有 uplink 字节但 `ASR empty` ≠ 硬件无麦 |
| 会话 | session generation 丢弃 prompt 完成后的 stale 回调 |

深细节 → [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) · 正例 → [good_voice_prompt_uplink.c](../examples/good_voice_prompt_uplink.c)

---

## 带屏打印机产品实测（bk_printer / BK7258）

来源：2026-06 AI 打印机工程 L2 审查 + 裁剪闭环。

### 密钥（C9）

- 非 AVDK `ap/` 工程：`projects/<app>/config/bk7258/config` + `config.secrets` + `scripts/merge_config_secrets.sh`
- 云 API 密钥用 `CONFIG_APP_CLOUD_*`（Kconfig.projbuild），禁止 `system_manager.c` 硬编码 `#define`

### 产品层裁剪（C6.5）

| 可裁 | 条件 |
|------|------|
| `http_client.c`、`save_opus_data.c`、`upload_image.c` | init 未调用、opus 保存仅在 `#if 0` |
| `iot_camera.c` | `CONFIG_DVP_CAMERA=n` → `CONFIG_IOT_DEV_CAMERA=n` |
| Webnet `wn_module_{asp,dav,ssi,upload,...}.c` | `webnet.h` 仅 `WEBNET_USING_CGI` |
| `components/moduleA/B/C` | Skill checker demo，非产品代码 |
| `protocol_mqtt.c` | `CONFIG_PROTOCOL_USE_MQTT=n`（CMake 已守卫） |

**勿裁：** `wn_module_cgi.c`（SoftAP 配网）、`iot_volume.c`（须在 `iot_devices_init` 注册 MCP 工具，勿依赖已移除的 `http_client` init）。

### 打印 / 图像并发

- `system_manager_process_received_image` 须 **mutex** 串行化（BLE / 本地二维码 / 云端图共用 `img_rgb565`）
- 本地二维码任务栈建议 **≥24KB**（JPEG 软解 + 打印流水线）
- CPU1 读 JPG 文件：**禁止** `lv_img_read_file_to_mem`；用 `open/read` + `psram_malloc`，与 LVGL 解耦

### 栈参考（打印机 + WSS）

| 任务 | 建议栈 (bytes) |
|------|----------------|
| `local_qr_print` | 24576 |
| `vc_start`（voicechat 异步建链） | ≥5120 |
| WSS / dialog / system_manager | ≥4096，须 HighWaterMark 实测 |
| LVGL init（cpu1 `ui_main`） | ≥3072，含资源加载时上调 |

### WSS 异步建链（vc_start）— HardFault 高发

**症状：** WebSocket 401/断线后 ~8s，`Fault on thread vc_start`，`r3=0xcdcdcdcd`，同一 `pc` 反复出现。

**根因：** `vc_start` 线程在 `voicechat_session_connect()` 内阻塞时，事件回调或 `SYSTEM_EVENT_SERV_NULL` 路径**并发** `stop/deinit` websocket → use-after-free。

**修复清单（MVP）：**

| 项 | 做法 |
|----|------|
| 生命周期互斥 | `voicechat_client` 的 `start/stop/configure` 同一把 mutex |
| 首次建链失败 | 事件回调**勿**发 `SERV_NULL`（`started` 仍为 false）；由 `vc_start` 失败路径统一上报 |
| SERV_NULL | 处理前 **wait `vc_start` 结束** 再 `stop()` |
| connect 唤醒 | `DISCONNECTED/CLOSED` 时若仍在 CONNECTING，须 `post connect_sem`，避免 connect 长挂扩大竞态 |
| 建链失败清理 | `connect` 失败须 `disconnect+deinit`，不留半初始化 session |
| 线程退出 | 任务末尾 `rtos_delete_thread(NULL)`，**勿**在任务内 `delete_thread(&self_handle)` |

### Assert `prvNotifyQueueSetContainer`

BK SDK 全局 `configUSE_QUEUE_SETS=1`（`FreeRTOSConfig.h`）。Assert @ `queue.c` 多为：

1. QueueSet 通知队列满（成员 queue 事件未被 select 消费），或
2. **堆损坏**（常与 WSS 并发 deinit 同源，先修 vc_start 再复测）

产品层未直接用 QueueSet 时，优先怀疑内存踩踏而非业务 QueueSet 配置。

### littlefs 表情资源（LVGL decode fail:0）

UI 读 `/emoji/{name}.png`（如 `neutral.png`）。`lv_png_img_load` 返回失败时 LVGL8 常打 `decode fail:0`（`LV_RES_INV`）。

**常见原因：** `USR_CONFIG` littlefs 分区未打包 `emoji/` 目录（仓库常不含 png，须 `mklittlefs -c bk/` 烧录）。

缺文件仅无表情图，不影响 WSS/打印主流程。

### SARADC / `gpio:1 was busy`（电池采样）

CPU1 电池每轮 `bk_adc_init` 从 RF 温度检测「夺回」SARADC ISR，HAL 会打 cosmetic `gpio busy`。读数 `ok=4/4` 时可忽略；**勿**为此去掉 re-init（会导致 `-10504` 或脏读数）。

---

## 与其他平台的差异

| 对比项 | BK 博通集成 | 杰理 JL | ESP32 |
|--------|------------|---------|-------|
| 基础 SDK | bk_idk (Armino) | AC79 AIoT SDK | ESP-IDF |
| 多媒体 SDK | bk_avdk_smp | — | — |
| UI 工具 | BEKEN LVGL UI Designer | 第三方/UI 手写 | Squareline |
| 多核 | BK7258 三核 + mailbox | 部分 DSP 核 | 双核 Xtensa |
| 线程 API | `rtos_create_thread`（bytes） | `thread_fork` | `xTaskCreate` |
| 编译 | `make bk7258` | `make ac791n_xxx` | `idf.py build` |
| 音频 | AVDK media pipeline | audio_server | I2S driver |
