# Workflow: Hardware-Software Co-debug / IO Pin Planning

**Trigger:** Hardware co-debug, IO pin allocation, GPIO conflict investigation, pin muxing, peripheral wiring, new board bring-up, PCB layout review.

<thinking>
1. IO pins are the physical constraints of an embedded system — no matter how correct the software is, wrong IO wiring means hardware won't work
2. User **must** provide a complete IO pin usage table; Agent is **forbidden** from assuming pin assignments
3. Every IO change requires **repeated verification**: platform capability → pin mux → electrical constraints → software configuration
4. This workflow integrates with L3_new_module: run IO verification before adding new peripherals
5. New projects may only **reference** the format and structure of existing configuration files; **direct reuse or modification of original configuration files is forbidden**; must write entirely new configurations strictly per user input
</thinking>

## Step 0 — Collect IO Pin Usage Table (Mandatory, Cannot Skip)

**Iron Rules:**
1. Before user provides a complete IO table, Agent is forbidden from outputting any pin-related code or configuration
2. New projects may only **reference** the format and structure of existing project/template configuration files; **direct copy, reuse, or modification of original project configuration files is forbidden**; must write entirely new configurations strictly per user input

### 0.1 Mandatory Interaction Template

Agent outputs the following template, requiring user to fill in each item:

```markdown
## IO Pin Usage Table (Please fill in all allocated IOs)

### Basic Information
- Chip Model: ____
- Package/Pin Count: ____
- Development Board Model: ____

### GPIO Allocation

| IO Number | Function | Peripheral/Protocol | Level | Direction | Remarks |
|---------|------|-----------|------|------|------|
| GPIO_xx | e.g. LED Indicator | GPIO OUT | 3.3V | Output | Onboard green LED |
| GPIO_xx | e.g. Button Input | GPIO IN | 3.3V | Input | Internal pull-up |
| GPIO_xx | e.g. I2S_SCK | I2S0 | 3.3V | — | Microphone clock |
| ... | ... | ... | ... | ... | ... |

### Analog IO (if any)

| IO Number | Function | ADC Channel | Resolution | Sampling Range | Remarks |
|---------|------|----------|--------|----------|------|
| ... | ... | ... | ... | ... | ... |

### Communication Buses

| Bus | SCL/SCK | SDA/MOSI | MISO | CS/SS | Speed | Slave Devices |
|------|---------|----------|------|-------|------|--------|
| I2C0 | GPIO_xx | GPIO_xx | — | — | 400kHz | OLED + Sensor |
| SPI0 | GPIO_xx | GPIO_xx | GPIO_xx | GPIO_xx | 10MHz | Flash + LCD |
| UART1 | TX: GPIO_xx | RX: GPIO_xx | — | — | 115200 | Debug UART |

### Special Pins

| IO Number | Function | Constraints |
|---------|------|------|
| ... | BOOT/Download Mode | Power-on level determines boot mode |
| ... | EN/Reset | Cannot be configured as general GPIO |
| ... | JTAG/SWD | Debug interface, can be released in production |
```

### 0.2 Handling Incomplete User Input

| Missing Information | Agent Action |
|----------|-----------|
| IO table not provided at all | **Refuse to continue**, output template and explain reason |
| Some rows marked "TBD" | Allowed, but **must** complete during final verification |
| Only peripheral name written without specific IO | Request completion, cannot assume on its own |
| Only schematic screenshot provided | Agent attempts to read and extract, but **must** have user confirm |

---

## Step 1 — 平台能力核对

### 1.1 加载平台专档

读取 `platforms/xxx.md`，提取芯片引脚复用矩阵关键限制。

### 1.2 核对清单

逐项检查用户 IO 表：

| 检查项 | 方法 | 违规处理 |
|--------|------|----------|
| **引脚复用冲突** | 同一 GPIO 被分配给两个互斥外设（如同时 I2S 和 SPI） | 🔴 报错，要求用户二选一 |
| **外设通道存在性** | 芯片是否有所需的 I2S0/SPI1/UART2 等通道 | 🔴 报错，建议替代方案 |
| **输入/输出方向** | ADC 引脚被配置为数字输出 | 🔴 报错 |
| **特殊引脚误用** | Strapping pin（BOOT/EN）被用作普通 GPIO | 🟡 警告，确认用户意图 |
| **电平不匹配** | 3.3V GPIO 直连 5V 外设 | 🟡 警告，建议电平转换 |
| **中断能力** | 需要外部中断的引脚是否支持 GPIO 中断 | 🔴 报错 |
| **DMA 通道** | I2S/ADC 等需要 DMA 的外设，DMA 通道是否可用 | 🟡 警告 |
| **驱动能力** | 大电流负载（电机/继电器）直接由 GPIO 驱动 | 🟡 警告，建议外加驱动电路 |

### 1.3 输出格式

```markdown
## IO 核对结果

### ✅ 通过项
- GPIO_xx: I2S_SCK — 引脚复用正确，平台支持

### 🔴 冲突/错误
- GPIO_15: 同时分配给 SPI0_MOSI 和 I2S_SD — **引脚复用冲突**
  - 建议：I2S_SD 改用 GPIO_xx（平台专档 I2S 引脚表）

### 🟡 警告
- GPIO_0: BOOT strapping pin — 上电时需为高电平
  - 确认：外部电路是否保证上电时为高？

### 待确认
- GPIO_xx: 标注「待定」— 请补充功能分配
```

---

## Step 2 — 软件配置生成（通过核对后）

### 2.1 生成引脚定义头文件

```c
/**
 * @file board_io.h
 * @brief 板级 IO 口定义（自动生成，请勿手动修改引脚编号）
 * @warning 修改引脚前必须走 hw_sw_cocodebug workflow 重新核对
 */

#ifndef BOARD_IO_H
#define BOARD_IO_H

/* ── LED ─────────────────────────────── */
#define BOARD_LED_STATUS_PIN        GPIO_NUM_2
#define BOARD_LED_STATUS_ACTIVE     1       /* 高电平点亮 */

/* ── 按键 ─────────────────────────────── */
#define BOARD_BTN_WAKE_PIN          GPIO_NUM_0
#define BOARD_BTN_WAKE_ACTIVE       0       /* 低电平触发 */

/* ── I2S 音频 ─────────────────────────── */
#define BOARD_I2S_SCK_PIN           GPIO_NUM_12
#define BOARD_I2S_WS_PIN            GPIO_NUM_13
#define BOARD_I2S_SD_PIN            GPIO_NUM_14
#define BOARD_I2S_MCLK_PIN          GPIO_NUM_16  /* 若需要 MCLK */

/* ── I2C 传感器 ───────────────────────── */
#define BOARD_I2C_SCL_PIN           GPIO_NUM_22
#define BOARD_I2C_SDA_PIN           GPIO_NUM_21

/* ── SPI LCD ──────────────────────────── */
#define BOARD_SPI_MOSI_PIN          GPIO_NUM_23
#define BOARD_SPI_SCK_PIN           GPIO_NUM_18
#define BOARD_SPI_CS_PIN            GPIO_NUM_5
#define BOARD_LCD_DC_PIN            GPIO_NUM_17
#define BOARD_LCD_RST_PIN           GPIO_NUM_25
#define BOARD_LCD_BL_PIN            GPIO_NUM_26

#endif /* BOARD_IO_H */
```

### 2.2 生成 Kconfig 引脚配置（可选）

```kconfig
# Board IO Configuration — generated by hw_sw_cocodebug workflow
# DO NOT modify pin numbers without re-running IO verification

config BOARD_LED_STATUS_PIN
    int "Status LED GPIO"
    default 2

config BOARD_BTN_WAKE_PIN
    int "Wake button GPIO"
    default 0

config BOARD_I2S_SCK_PIN
    int "I2S Serial Clock GPIO"
    default 12
```

---

## Step 3 — 外设初始化代码模板

根据用户 IO 表和平台，生成外设初始化骨架代码。代码中**所有引脚编号必须引用 `board_io.h` 宏**，禁止硬编码 magic number。

### 3.1 初始化顺序核对（C8 联动）

```
时钟/PLL → GPIO 方向配置 → 外设驱动 init → DMA 配置 → 中断注册 → 任务创建
```

- 外设 init 须在使用该外设的 Task 创建**之前**完成
- I2S/SPI 等带 DMA 的外设，DMA 缓冲须在 ISR 注册**之前**就绪

---

## Step 4 — 反复核对（贯穿全流程）

**铁律：每次涉及以下场景，必须重新走 IO 核对：**

| 触发场景 | 核对范围 |
|----------|----------|
| 新增外设（传感器/屏幕/音频） | 新外设的 IO + 与现有 IO 的冲突 |
| PCB 改版 / 换芯片型号 | **全量重新核对** |
| 发现 GPIO 冲突 / 功能异常 | 冲突引脚 + 相邻引脚 |
| 引脚复用表变更（SDK 升级） | 受影响引脚 |
| 量产前最终审查 | 全量核对 + 电气约束 |

### 反复核对 Checklist

每次核对时 Agent 必须输出：

```markdown
## IO 反复核对 — 第 N 轮

### 核对原因
- [ ] 新增外设：____
- [ ] PCB 改版
- [ ] GPIO 冲突排查
- [ ] 量产前审查
- [ ] SDK 升级引脚复用变更

### 核对结果
- [ ] 无新增冲突
- [ ] 发现冲突：____（见 Step 1 输出格式）

### 用户确认
> 请确认以上 IO 分配无误后，我将继续下一步。
```

---

## Step 5 — 联调诊断（已有硬件时）

当用户报告硬件联调异常时：

### 5.1 IO 诊断 Checklist

| 现象 | 排查方向 |
|------|----------|
| 外设无响应 | IO 编号是否正确？引脚复用是否生效？GPIO 方向是否正确？ |
| 数据错乱 | MOSI/MISO 是否接反？时钟极性/相位（SPI mode）？I2C 地址？ |
| 间歇性故障 | 上拉/下拉电阻？电平匹配？信号完整性（线太长/干扰）？ |
| 仅特定板有问题 | 焊接质量？芯片批次差异？Strapping pin 电平？ |
| 中断不触发 | GPIO 中断类型（上升/下降/双边）？中断号是否正确？ISR 是否注册？ |
| ADC 读数不准 | ADC 衰减配置？参考电压？采样时间？GPIO 是否配置为模拟模式？ |

### 5.2 Audio/WSS 联合排查路径

当异常涉及 MIC、SPK、TTS 打断、WSS 上行、TLS 重连或长 TTS 背压时，不能只停在 IO 层。按同一时间线收集四类证据：

| 证据 | 看什么 | 对应约束 |
|------|--------|----------|
| 日志 | `CLIENT_INTERRUPT`、TTS generation、speaker idle/deinit、capture state、uplink frame index、TLS reconnect/backoff | C10、C20、C24 |
| 示波器/逻辑分析仪 | I2S BCLK/LRCK/SD 是否持续、speaker amp 使能、MIC bias/电源是否被误关 | C4、C18、C24 |
| 状态机 | `IDLE/CAPTURE/SPEAKER` 是否互斥；旧 TTS chunk 是否在 capture pending/running 时被丢弃 | C10、C13 |
| 堆/栈 | WSS/TLS 握手最低水位、PSRAM/SRAM matched free、speaker ring backpressure、task delete/IDLE cleanup 前后日志 | C7、C20 |

推荐时间线：

```text
AI key / wake
  -> interrupt sent or local cancel
  -> TTS generation++
  -> speaker stop only if SPEAKER mode, otherwise no-op
  -> capture pending/running
  -> stale TTS chunk dropped
  -> uplink frame index increments
  -> CLIENT_AUDIO_FINISH / ASR result
```

判断规则：
- 有 I2S/MIC 波形但 ASR 空：优先看 C10 时序、AEC settle、codec/sample-rate，而不是改 IO。
- speaker stop 后 MIC 波形消失：优先看 C24.4，shared backend 是否被错误 deinit/free。
- uplink frame 不增长但 WSS connected：看 capture 状态机和 WSS send task 是否被 TTS/JSON 处理阻塞。
- heap 下降或延迟 HardFault：按 [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) 查跨堆 matched free 与 TLS 重连峰值。

### 5.3 联调日志模板

建议用户在关键点添加日志：

```c
LOG_I(TAG, "IO init: LED=%d, BTN=%d, I2S_SCK=%d",
      BOARD_LED_STATUS_PIN, BOARD_BTN_WAKE_PIN, BOARD_I2S_SCK_PIN);

LOG_I(TAG, "GPIO config: pin=%d dir=%d pull=%d",
      pin, gpio_get_direction(pin), gpio_get_pull_mode(pin));
```

---

## Step 6 — 输出

```markdown
## IO 核对摘要
- 芯片/平台：
- IO 总数：已用 __ / 可用 __
- 冲突：无 / 已解决（见核对结果）
- 待确认：__ 项

## IO 口用途表
（最终确认版，含所有修改）

## 引脚定义文件
board_io.h

## 核对记录
- 第 1 轮：初始 IO 表收集
- 第 2 轮：新增 ____ 后核对
- ...
```

---

## 与其他 Workflow 的关系

| 场景 | 联动 |
|------|------|
| **l3_new_module** 新增外设 | 先走 hw_sw_cocodebug IO 核对，再写代码 |
| **debug_crash** GPIO 相关 HardFault | 核对 IO 配置是否正确 |
| **l2_code_review** 审查引脚配置 | 检查 `board_io.h` 是否与 IO 表一致 |
| **l3_sdk_trim** 裁剪外设驱动 | 更新 IO 表，释放不再使用的引脚 |
