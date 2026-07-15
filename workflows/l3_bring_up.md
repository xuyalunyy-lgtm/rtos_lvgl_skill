# 工作流：L3 板级启动（从上电到全功能跑通）

**触发：** 新板 bring-up / 最小系统验证 / 外设逐个点亮 / 首次全链路联调 / 量产前闭环验证 / board bring-up

```yaml
# 工作流输入结构
inputs:
  required:
    - name: board_name
      type: string
      description: 板级名称（如 "BK7258_EVB"、"ESP32-S3-DevKit"）
    - name: platform
      type: enum[esp32, stm32, jl, bk]
      description: 目标平台
  optional:
    - name: peripherals
      type: string[]
      description: 需要验证的外设列表（如 ["i2c_sensor", "lcd_display", "wifi"]）
    - name: sdk_path
      type: string
      description: SDK 路径

# 工作流输出结构
outputs:
  format: markdown
  sections:
    - IO 规划表（GPIO 分配 + 冲突检查）
    - 最小系统配置（boot sequence + WDT）
    - 外设逐个验证结果（每外设：pass/fail + 日志）
    - 全链路联调结果
  verification: 编译通过 + 每外设独立验证命令
```

<thinking>
1. Bring-up 是嵌入式开发的「从 0 到 1」，每个阶段都有明确交付物
2. 必须先走 hw_sw_cocodebug 收集 IO 表，再编译最小系统
3. 外设逐个验证，禁止「全量编译一次跑」——出问题无法定位
4. 每个阶段的验证结果是下一阶段的输入，不可跳步
</thinking>

## 前置条件

| 条件 | 说明 |
|------|------|
| **IO 口用途表** | 已完成 [hw_sw_cocodebug.md](hw_sw_cocodebug.md) Step 0–1（IO 收集 + 平台核对） |
| **SDK/工具链** | 开发环境已搭建，编译命令可用（见 `platforms/xxx.md`） |
| **硬件** | 板子到手，串口可连，供电正常 |

若 IO 表未完成 → 先走 `hw_sw_cocodebug.md`，**不可跳过**。

---

## 阶段 1 — 最小系统编译（无外设）

**目标：** 芯片能上电、串口有 log、看门狗不复位。

### 1.1 最小工程骨架

```markdown
## 最小系统 checklist

- [ ] 工程能编译通过（0 error）
- [ ] 串口有启动 log（`LOG_I(TAG, "boot OK")`）
- [ ] Task WDT 不触发（main 任务有 yield/timeout）
- [ ] 堆水位可读（`heap_caps_get_free_size` / `xPortGetFreeHeapSize`）
- [ ] 无 HardFault / Guru Meditation
```

### 1.2 启动顺序验证（C8 联动）

```
时钟/PLL 初始化
  → GPIO 方向配置
  → 串口初始化（最早的 log 输出点）
  → 堆/内存池初始化
  → NVS/Flash 初始化
  → WiFi/BLE 协议栈初始化（不连接）
  → Task WDT 注册
  → 启动 log：打印芯片型号、SDK 版本、堆水位
```

### 1.3 输出

```markdown
## 最小系统验证

- 芯片型号：
- SDK 版本：
- 编译结果：0 error / __ warning
- 串口 log：正常 / 无输出（排查 TX/RX 引脚）
- 堆水位：__ bytes free
- WDT：未触发 / __ ms 后复位（排查阻塞点）
```

---

## 阶段 2 — 外设逐个验证

**铁律：一次只验证一个外设，确认通过后再验证下一个。**

### 2.1 验证顺序（推荐）

```
GPIO (LED/按键) → UART → I2C → SPI → I2S/音频 → LVGL/显示 → 网络/WiFi → WSS/TLS
```

### 2.2 每个外设的验证模板

```markdown
## 外设验证：[外设名]

### 配置
- IO 引脚：GPIO_xx（与 board_io.h 一致 ✅/❌）
- 时钟/速率：____
- DMA：需要 / 不需要

### 测试方法
- [ ] init 成功（返回值检查，C12）
- [ ] 基本读写/收发正常
- [ ] 中断正常（若适用）
- [ ] 日志输出正常（C14：分级 + TAG + profile，热路径限频）
- [ ] 销毁/释放正常（无泄漏）

### 结果
- 通过 / 失败
- 失败原因：____
- 排查方向：____
```

### 2.3 GPIO / LED / 按键验证

```c
/* 最简 LED 验证 */
#include "board_io.h"

void led_test(void)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << BOARD_LED_STATUS_PIN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t ret = gpio_config(&io_conf);  /* C12: 检查返回值 */
    if (ret != ESP_OK) {
        LOG_E(TAG, "LED GPIO config failed: %s", esp_err_to_name(ret));
        return;
    }
    gpio_set_level(BOARD_LED_STATUS_PIN, BOARD_LED_STATUS_ACTIVE);
    LOG_I(TAG, "LED ON (pin=%d)", BOARD_LED_STATUS_PIN);
}
```

### 2.4 I2C / 传感器验证

```c
/* I2C 总线扫描 — 确认从设备地址 */
void i2c_scan(void)
{
    LOG_I(TAG, "I2C scan: SCL=%d SDA=%d", BOARD_I2C_SCL_PIN, BOARD_I2C_SDA_PIN);
    for (uint8_t addr = 0x08; addr < 0x78; addr++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (addr << 1) | I2C_MASTER_WRITE, true);
        i2c_master_stop(cmd);
        esp_err_t ret = i2c_master_cmd_begin(I2C_NUM_0, cmd, pdMS_TO_TICKS(100));
        i2c_cmd_link_delete(cmd);
        if (ret == ESP_OK) {
            LOG_I(TAG, "  Found device at 0x%02X", addr);
        }
    }
}
```

### 2.5 显示 / LVGL 验证

```c
/* 最简 LVGL 验证 — 画一个 Label */
#include "lvgl.h"

static void lvgl_minimal_test(lv_disp_t *disp)
{
    lv_obj_t *scr = lv_disp_get_scr_act(disp);
    lv_obj_t *label = lv_label_create(scr);
    lv_label_set_text(label, "Bring-up OK");
    lv_obj_center(label);
    LOG_I(TAG, "LVGL label created on display");
}
```

---

## 阶段 3 — MVP 任务链路验证

**目标：** Model → Queue → Presenter → View 全链路跑通。

### 3.1 任务创建顺序（C8.1 联动）

```
Presenter Looper（等待 Queue）
  → View / LVGL Task
  → Model / 网络任务（最后启动，因为它产生事件）
```

### 3.2 全链路验证 checklist

```markdown
## MVP 全链路验证

### 任务状态
- [ ] Presenter Looper 已创建（Task 名：____，优先级：____）
- [ ] LVGL Task 已创建（Task 名：____，优先级：____）
- [ ] Model 任务已创建（Task 名：____，优先级：____）
- [ ] 优先级差 ≥2（C15.1）

### Queue 验证
- [ ] Queue 已创建（深度：____，元素大小：____）
- [ ] Model → Presenter xQueueSend 成功
- [ ] Presenter → View lv_async_call 成功
- [ ] Queue 满时 Model 释放 payload（C2.4）

### 内存验证
- [ ] 堆最低水位 > __ bytes（基线记录，C7.1）
- [ ] 无 cJSON* 进 Queue（C2.1）
- [ ] 无栈指针进 Queue（C2.2）
- [ ] payload 由 Presenter vPortFree（C2.3）

### LVGL 验证
- [ ] UI 仅在 LVGL Task 中修改（C1.1/C1.2）
- [ ] 无跨线程 lv_obj_* 调用
- [ ] lv_timer_handler 正常运行
```

---

## 阶段 4 — 网络 / WSS / TLS 验证

### 4.1 WiFi 连接验证

```markdown
## WiFi 验证

- [ ] WiFi STA 模式初始化
- [ ] 扫描到 AP
- [ ] 连接成功（获取 IP）
- [ ] SNTP 时间同步（C8.2：TLS 握手前必须完成）
- [ ] DNS 解析正常
```

### 4.2 WSS 连接验证

```markdown
## WSS 验证

- [ ] TLS 握手成功（栈 ≥4096 bytes，建议 6144，C7.5）
- [ ] WebSocket 握手成功
- [ ] 收发消息正常
- [ ] 断线重连正常（指数退避，C7.9）
- [ ] 堆水位：握手峰值 __ bytes free（C7.1 基线）
- [ ] cJSON 解析正常（goto cleanup 模板，C3）
```

---

## 阶段 5 — 语音 / 音频 / 音视频验证（若有）

### 5.1 I2S / DMA 验证

```markdown
## I2S 音频验证

- [ ] I2S RX 初始化（Mic 采集）
- [ ] I2S TX 初始化（Speaker 播放）
- [ ] DMA 缓冲 Ping-Pong 正常（C4.4）
- [ ] DMA 缓存在 SRAM（非 PSRAM，C7.8）
- [ ] ISR 仅用 *FromISR API（C4.1）
- [ ] 采集 PCM 有数据（peak > 0）
```

### 5.2 语音全链路验证

```markdown
## 语音全链路验证

- [ ] 唤醒词触发
- [ ] Prompt tone 播放（叮）
- [ ] Prompt 结束后 detach 播放路径（C10.1）
- [ ] AEC settle 完成（80–150ms，C10.2）
- [ ] Uplink 开启，云端 ASR 返回非空
- [ ] 第二轮语音：peak 与第一轮同量级（C10.1/C10.2 不退化）
- [ ] TTS 播放正常
```

### 5.3 音视频同步验证（若有 camera / video preview）

```markdown
## 音视频同步验证

- [ ] audio clock / I2S DMA timestamp 作为 master clock（C25.1）
- [ ] audio/video frame 带 pts、seq、duration/sample_count、owner（C25.2）
- [ ] A/V sync 有唯一 master clock，PTS 单调，不用系统 tick 冒充媒体时钟（C27.1）
- [ ] I2S/AEC/ASR/encoder/uplink 的 sample rate/channels/bit depth 一致或显式转换（C26.1）
- [ ] frame_samples 由 sample_rate * frame_ms * channels 推导（C26.2）
- [ ] video frame 有 pixel_format/stride，RGB565 stride ≥ width*2（C26.3）
- [ ] Camera/I2S/LCD/codec DMA buffer 位于 DMA-capable 内存并对齐（C28.1）
- [ ] DMA RX 后 CPU 读前 invalidate，LCD/I2S TX 前 clean（C28.2）
- [ ] 零拷贝 frame pool 有 owner/state/generation/release，Queue 传 index/handle（C28.3/C28.4）
- [ ] cache clean/invalidate 范围按 cache line 对齐并覆盖完整 frame/stride（C28.5）
- [ ] video queue 有界，满时 drop-oldest，不阻塞 audio hot path（C25.3）
- [ ] jitter buffer 有 capacity、low/high watermark、target delay，满水位策略明确（C27.2）
- [ ] drift correction 有 ppm 上限，小漂移 bounded correction，大漂移 resync（C27.3）
- [ ] render/playback/sync 热路径不按 drift/PTS `vTaskDelay` 或 `portMAX_DELAY` 硬等（C27.4）
- [ ] camera/display/encode/decode per-frame 路径无 malloc/free/printf/重日志（C25.4/C26.4）
- [ ] camera/LCD/DMA callback 只 notify/enqueue，不直接跑 UI/codec/network/json（C25.5）
- [ ] codec handle 不在每帧 create/init/open（C26.5）
- [ ] underrun/overrun 只做静音/重复/丢帧/resync，路径内无 malloc/free/printf/重日志（C27.5）
- [ ] 记录 av_drift_ms、drift_ppm、jitter_depth、dropped_frames、late_frames、underrun/overrun、format_mismatch、codec_error、cache/stale/reuse 计数（C25.6/C26.6/C27.6/C28.6）
```

---

## 阶段 6 — 闭环冒烟 + 量产 checklist

### 6.1 冒烟测试（全流程跑通）

```markdown
## 冒烟测试（连续运行 ≥30 分钟）

- [ ] 上电 → 连 WiFi → WSS 连接 → 等待唤醒
- [ ] 唤醒 → 语音交互 → ASR 返回 → TTS 播放
- [ ] audio sample rate / frame_ms / channels 与 ASR/encoder 配置一致
- [ ] camera/video preview 音画同步，无持续 drift / jitter_depth 异常 / dropped_frames 激增（若有）
- [ ] 连续 10 轮语音交互无异常
- [ ] 堆水位无持续下降（无泄漏）
- [ ] 无 WDT 复位
- [ ] 无 HardFault
- [ ] LVGL 界面正常刷新
- [ ] 断网重连正常
```

### 6.2 量产 checklist

```markdown
## 量产 checklist

- [ ] C9 密钥/凭证：config.secrets 不入库（secret_scan_checker 通过）
- [ ] C9.2 Git remote 无内嵌凭证
- [ ] C6 SDK 裁剪：未用模块已关闭（先问卷后裁剪）
- [ ] C5 测试宏：APP_TEST_MODE_* 全部关闭（或 #if 0）
- [ ] C11 编码规范：函数 ≤80 行、命名规范、文件头注释
- [ ] C14 日志：无裸 printf、ISR 无日志、密码已脱敏、量产 profile 不刷屏
- [ ] C13 状态机：非法状态有 log + reset
- [ ] C29 模块契约：context/blocking/ownership/lifecycle/error 已声明
- [ ] C30 任务/队列拓扑表：priority/stack/depth/backpressure/exit 已记录
- [ ] C31 超时预算：无裸 portMAX_DELAY/WAIT_FOREVER，例外已注释
- [ ] C32 可观测性：state/error/counter/watermark/max time 可采集
- [ ] C33 生命周期：init/start/stop/deinit 与 alloc/free 对称
- [ ] C34 热路径：ISR/DMA/flush/frame/control loop 无阻塞、分配、重日志
- [ ] C35 关键路径预算：boot/net/audio/video/UI/OTA/sleep-wake 有 stage budget
- [ ] C36 数据拷贝预算：copy count、owner/release、DMA cache 策略已声明
- [ ] C37 背压降级：满队列/满池/网络差时有 drop/coalesce/backpressure/degrade
- [ ] C38 故障恢复：故障域、retry/backoff、supervisor、降级/安全停机已定义
- [ ] C39 配置矩阵：feature/board/SDK 差异、依赖、资源、test mode 已记录
- [ ] C40 一键复现：build/flash/monitor/log/decode/test 命令可复制
- [ ] C41 回归样本：新增约束或 bugfix 有 good/bad 样本或最小复现
- [ ] C42 板级资源：GPIO/DMA/clock/IRQ/cache/heap/PSRAM owner 和冲突检查明确
- [ ] C43 锁预算：等锁 timeout、持锁预算、lock_order 与优先级继承明确
- [ ] C44 临界区/关中断：critical section 短小、对称、有预算，且无阻塞/分配/日志/大拷贝
- [ ] C45 传感器集成：probe/WHO_AM_I、总线 timeout、data-ready、sample metadata、calibration lifecycle 明确
- [ ] Stack watermark 全任务 > 20% 剩余
- [ ] 堆最低水位 > 20% 总量
- [ ] Flash/RAM 占比记录
```

---

## 阶段 7 — 输出

```markdown
## Bring-up 报告

### 基础信息
- 芯片/平台：
- SDK 版本：
- 编译结果：

### IO 口用途表
（来自 hw_sw_cocodebug，最终确认版）

### 外设验证结果
| 外设 | 状态 | 备注 |
|------|------|------|
| GPIO/LED | ✅ | |
| I2C 传感器 | ✅ | 地址 0x3C |
| SPI LCD | ✅ | |
| I2S 音频 | ✅ | |
| WiFi | ✅ | |
| WSS | ✅ | |
| LVGL | ✅ | |
| 语音 | ✅ | |

### 内存基线
- 堆最低水位：__ bytes
- 任务栈 watermark（最紧）：__ bytes（任务名：____）
- Flash 占用：__ / __ bytes

### 冒烟测试
- 运行时长：__ 分钟
- 异常次数：0
- WDT 复位：0

### 已知问题
- [ ] ____
- [ ] ____
```

---

## 与其他 Workflow 的关系

| 前置 | 后续 | 联动 |
|------|------|------|
| **hw_sw_cocodebug** | 本 workflow | IO 表 + board_io.h 是 bring-up 的输入 |
| 本 workflow | **l2_code_review** | bring-up 通过后做正式 code review |
| 本 workflow | **l3_new_module** | 新增外设时回到阶段 2 验证 |
| 本 workflow | **l2_memory_analysis** | 深度内存分析（堆/栈/池） |
| 本 workflow | **debug_crash** | 冒烟中出问题 → crash 诊断 |

---
验收标准：[acceptance_criteria.md](../references/acceptance_criteria.md#bring-upl3_bring_up)
