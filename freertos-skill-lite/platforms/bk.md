# BK 博通集成（Beken）平台专档

Agent 确认目标平台为博通集成 BK 系列时读取本文件。

适用芯片：BK7258（主流 AIoT/带屏）、BK7251、BK7231/BK7236（WiFi 模组）等。

SDK 框架：**Armino**（`bk_avdk` / `bk_avdk_smp`），文档：https://docs.bekencorp.com/

## SDK 全景扫描（裁剪前强制）

**动刀裁剪之前，必须先整体扫描原厂 SDK**。BK 工程结构复杂（AP/CP 双核、多 repo），禁止未扫描直接删代码。

```
Phase A — 只读扫描
  ├── clone bk_avdk_smp + 目标 solution repo
  ├── 列出 projects/ 与 ap/ cp/ 目录职责
  ├── 导出 projects/<app>/config/bk7258/config 全部 CONFIG_*
  ├── make bk7258 编译基线，记录 Flash/RAM
  ├── 列出 AP 侧 xTaskCreate / 官方 init 顺序
  └── 确认 CP 侧 WiFi 组件边界（用户通常只改 ap/）

Phase B — 询问用户完整产品需求
  └── 需求驱动裁剪表（非固定模板）

Phase C — 从 projects/ 最小 Demo fork 新工程，按需求裁剪
```

**推荐**：选最接近产品的最小 Demo（如 `lvgl/widgets`），copy 为新工程后再裁，勿在 `beken_genie` 全量工程上直接删。

扫描输出模板见 [prompts/sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt)。

## 关键差异速览

| 项目 | Armino SDK 惯例 | 注意 |
|------|----------------|------|
| 内核 | FreeRTOS（SMP 多核，BK7258） | AP/CP 双核分工，WiFi 协议栈多在 CP 侧 |
| 编译 | `make bk7258 PROJECT=<path>` | Linux 为主，Windows 可用 `dbuild.ps1` |
| 配置 | Kconfig + `bk7258.defconfig` | 工程 config 可 override 芯片默认配置 |
| 任务优先级 | FreeRTOS 标准，**数字越大越高**（config 依 SDK 版本） | 以 `FreeRTOSConfig.h` 为准 |
| 网络 | 内置 WiFi + LwIP | WSS/HTTP 走 SDK 网络组件 |
| UI | LVGL + **BEKEN LVGL UI Designer** | 导出代码在 `beken_generated/` |
| 多媒体 | AVDK 音视频框架（BK7258） | 摄像头/UVC/LCD 切换场景常见 |

## SDK 仓库结构

```
bk_avdk_smp/                 # 主 SDK（RTOS、驱动、WiFi、LVGL）
├── projects/                # 官方 Demo（lvgl/86box, lvgl/widgets 等）
├── middleware/              # 中间件
└── components/              # 组件

bk_solution_ai/              # AI 方案（beken_genie, volc_rtc）
bk_solution_dashboard/       # 仪表盘方案（scooter 等）
```

AI/行业方案通过 `SDK_DIR` 指向 `bk_avdk_smp` 编译：

```bash
cd ~/armino/bk_solution_ai/projects/beken_genie
export SDK_DIR=~/armino/bk_avdk_smp
make bk7258
```

## 编译脚本（与 SDK 同级目录）

Skill 提供 **`bk_build.sh`** / **`bk_build.ps1`**，放置在与 `bk_avdk_smp` **同级**的工作区根目录：

```
~/armino/                      ← 工作区根（脚本放这里）
├── bk_avdk_smp/               ← SDK
├── bk_solution_ai/            ← 可选方案仓
├── bk_build.sh                ← Linux / WSL / Docker
├── bk_build.ps1               ← Windows
└── bk_build.env.example       ← 复制为 bk_build.env 配置默认工程
```

```bash
# Linux / WSL
chmod +x bk_build.sh
./bk_build.sh build -p bk_solution_ai/projects/beken_genie
./bk_build.sh clean  -p lvgl/widgets
./bk_build.sh rebuild
```

```powershell
# Windows（方案仓工程优先走 dbuild.ps1）
.\bk_build.ps1 build -Project bk_solution_ai\projects\beken_genie
.\bk_build.ps1 clean
.\bk_build.ps1 rebuild -Soc bk7258
```

脚本自动探测同级 `bk_avdk_smp` / `bk_avdk`；外部工程自动设置 `SDK_DIR`；SDK 内 Demo 使用 `make bk7258 PROJECT=xxx`。

## 推荐任务优先级（BK7258 参考）

```c
/* BK7258 SMP — 以 SDK FreeRTOSConfig.h 为准；大数高优先级写法示例 */
#define AUDIO_TASK_PRIO      (configMAX_PRIORITIES - 1)
#define WSS_TASK_PRIO        (configMAX_PRIORITIES - 3)
#define LVGL_TASK_PRIO       (configMAX_PRIORITIES - 5)
#define PRESENTER_TASK_PRIO  (configMAX_PRIORITIES - 7)
```

输出优先级表时**同时给出相对顺序和 SDK 配置依据**。BK7258 AP/CP 双核场景下，WiFi 协议栈任务由 SDK 预置，用户任务跑在 AP 侧，**勿与协议栈任务抢最高优先级**。

## 任务创建模板

```c
#include "FreeRTOS.h"
#include "task.h"

/* Model — WSS 网络任务 */
void network_wss_task_start(void)
{
    BaseType_t ret = xTaskCreate(
        wss_task_entry,
        "wss",
        4096,                    /* bytes 或 words 以 SDK 宏为准，BK7258 常用 bytes */
        NULL,
        WSS_TASK_PRIO,
        NULL
    );
    configASSERT(ret == pdPASS);
}

static void wss_task_entry(void *param)
{
    (void)param;
    for (;;) {
        /* 网络接收 — 禁止 lv_obj_* */
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
```

**栈单位陷阱**：不同 Beken SDK 版本 `xTaskCreate` 栈参数可能是 bytes 或 words，必须以当前工程 `FreeRTOSConfig.h` 和官方 Demo 为准，代码注释中标注单位。

## LVGL 集成（BK7258 核心场景）

### 标准 LVGL 任务

```c
/* projects/xxx/ap/lvgl/lvgl_app_ui.c */
static void lvgl_task(void *param)
{
    (void)param;
    lv_init();
    lv_port_disp_init();
    lv_port_indev_init();

    beken_ui_init();   /* Designer 生成的初始化，仅 View 层调用 */

    for (;;) {
        lv_timer_handler();
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}
```

### BEKEN LVGL UI Designer 工作流

1. 用 Designer 拖拽设计界面 → 导出 C 代码到 `beken_generated/`
2. 将 `beken_generated/` 复制到工程 `ap/` 目录
3. 修改 `CMakeLists.txt` 加入生成源文件
4. 在 `lvgl_app_ui.c` 用 `beken_ui_init()` 替换手写页面初始化

**规则**：
- Designer 生成代码归属 **View 层**，不含业务逻辑。
- 控件事件回调**只发消息**给 Presenter（参照 `good_mvp_pattern.c`），禁止在回调中做网络请求或 `vTaskDelay`。
- 跨任务刷新：优先 `lv_async_call()`；多任务访问 LVGL 须互斥保护。

### 摄像头 / LVGL 切换（BK7258 特有）

部分工程（如 `lvgl/camera`）在 UVC 摄像头画面与 LVGL UI 间切换：

```bash
# 串口命令切换（Demo 参考）
lvcam_open    # 显示摄像头
lvcam_close   # 恢复 LVGL UI
```

切换时须确保 LVGL 任务已释放显示资源，避免 DMA 与 LVGL 帧缓冲冲突。

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
- WiFi 连接由 SDK `wifi` 组件管理，Model 层监听事件而非直接调底层寄存器。
- 解析后的数据打包 `net_evt_t` 投 Queue，Presenter 调 `view_xxx()` 刷新。

## 音频 / 多媒体（AVDK）

BK7258 AVDK 提供音视频 pipeline，不同于杰理 `audio_server` 或 STM32 裸 I2S：

- 录音/播放走 AVDK media API（`media_app`、`audio_interface` 等，以 SDK 版本为准）。
- 音频回调在 media 任务上下文 — **禁止直接改 UI**。
- DMA 缓冲由 AVDK 管理；用户层处理 PCM 帧或编码流，结果送 Presenter Queue。
- 高实时场景须确认 AP/CP 核分工，避免 media 任务与 WiFi 抢占。

## Kconfig / 关键配置

```
# 栈溢出检测
CONFIG_FREERTOS_CHECK_STACKOVERFLOW=y

# LVGL 显存与色深
CONFIG_LV_COLOR_DEPTH=16

# WiFi
CONFIG_WIFI_ENABLE=y
```

工程级配置在 `projects/<name>/config/bk7258/config` 覆盖芯片默认。

## SDK 深度裁剪（Armino / BK7258）

> **以下仅为候选项**，须在产品需求问卷确认「不需要」后再关闭；禁止未询问用户直接套用。

### 配置入口

```bash
# 工程级 Kconfig
projects/<your_app>/config/bk7258/config

# 芯片默认
middleware/soc/bk7258/bk7258.defconfig
```

### 优先关闭项

| 类别 | Kconfig / 配置 | 未用时关闭 |
|------|---------------|-----------|
| 蓝牙 | `CONFIG_BT` | 无 BLE 则关 |
| 未用 Demo 工程 | `projects/` | 不编译无关 demo，只 fork 目标工程 |
| AVDK 摄像头 | media config | 无 UVC 则关 `CONFIG_UVC` 等 |
| LVGL demo | LVGL config | 关 benchmark/widgets demo，缩 `LV_MEM_SIZE` |
| LwIP | lwip config | 缩 `MEM_SIZE`、连接数 |
| CLI/调试 | debug config | 关串口 CLI、多余 log level |
| CP 侧组件 | cp/ 目录 | 不修改 CP，但通过 Kconfig 关 AP 侧不需要的 IPC 通道 |

### 工程选择（裁剪第一步）

**不要**在完整 `bk_solution_ai` 上直接开发。正确流程：

```
1. 选最贴近产品的最小 Demo（如 lvgl/widgets 或 beken_genie 子集）
2. copy 为新工程目录
3. 删 ap/ 下未用模块源文件
4. 改 CMakeLists.txt 移除 REQUIRES 依赖
5. Kconfig 逐项关未用功能
```

### beken_generated 裁剪

- Designer 导出后删未用页面/组件 `.c/.h`
- 字库子集化，只保留 UI 实际用到的字符
- 图片转 indexed / 压缩，删原始大图

### BK 裁剪验证

```bash
make bk7258
# 查看 build 输出 size 信息；或用 map 文件分析
```

- AP 堆峰值：FreeRTOS `xPortGetMinimumEverFreeHeapSize()`
- 确认 CP 侧 WiFi 正常后再缩 AP 侧 LwIP 池（逐步减，每步测 WSS）

## 常见 Crash / 异常定位

| 现象 | Beken 特有原因 |
|------|---------------|
| 编译找不到 SDK | 未设 `SDK_DIR` 指向 `bk_avdk_smp` 根目录 |
| LVGL 不显示 | `beken_ui_init()` 未调用；Designer 文件未加入 CMakeLists |
| 摄像头与 UI 冲突 | UVC 与 LVGL 同时占用显示通路，须按 Demo 切换 |
| WiFi 连上但 WSS 失败 | SNTP 未同步；证书配置；LwIP 内存不足 |
| 系统随机重启 | 栈溢出（查 `uxTaskGetStackHighWaterMark`）；ISR 阻塞 |
| AP/CP 通信异常 | 核间消息队列满；用户任务抢占协议栈 |

## 文件归属惯例（BK7258 工程）

```
projects/<your_app>/
├── ap/                           # AP 侧应用（用户主战场）
│   ├── main.c                    # 入口，创建任务
│   ├── network_wss_task.c        # Model — WSS
│   ├── app_presenter.c           # Presenter
│   ├── lvgl/
│   │   ├── lvgl_app_ui.c         # LVGL 任务 + View 初始化
│   │   └── ui_view_manager.c     # View 刷新接口
│   ├── beken_generated/          # Designer 导出（View 层）
│   └── CMakeLists.txt
├── cp/                           # CP 侧（通常不改）
└── config/bk7258/                # 工程配置
```

## 与其他平台的差异提醒

| 对比项 | BK 博通集成 | 杰理 JL | ESP32 |
|--------|------------|---------|-------|
| SDK 名 | Armino (bk_avdk_smp) | AC79 AIoT SDK | ESP-IDF |
| UI 工具 | BEKEN LVGL UI Designer | 第三方/UI 手写 | Squareline / 手写 |
| 多核 | AP/CP SMP（BK7258） | 部分双核 DSP | 双核 Xtensa |
| 编译 | `make bk7258` | Makefile/CodeBlocks | `idf.py build` |
| 音频 | AVDK media pipeline | audio_server | I2S driver |
