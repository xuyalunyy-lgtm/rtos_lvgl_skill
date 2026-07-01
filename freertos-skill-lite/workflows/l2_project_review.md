# Workflow: L2 工程审查（多仓 / 固件产品）

**触发：** 用户要求审查整个工程、workspace review、量产前审计、架构 review。

<thinking>
1. 识别工作区：产品仓 + SDK 仓 + skill（若有）
2. **从仓库结构识别平台**（Kconfig/sdkconfig/Makefile/`platforms/` 线索），加载对应 `platforms/xxx.md`
3. 分三层：仓库卫生(C9) → 架构文档 → 组件代码(C1–C10)
4. 产品 components 跑 run_review；config 跑 secret_scan
</thinking>

## Step 1 — 总纲与平台

- [core_rules.md](../references/core_rules.md)
- [constraint_index.md](../references/constraint_index.md)（含 **C9、C10**）
- **用户指定或检测到的** [platforms/esp32.md](../platforms/esp32.md) | [jl](../platforms/jl.md) | [bk](../platforms/bk.md) | [stm32](../platforms/stm32.md)

平台检测线索：`idf.py` / `sdkconfig` → ESP32；`make ac791n_*` / `task_info_table` → JL；`make bk7258` / `ap/`+`cp/` → BK；CubeMX/`Core/` → STM32。

## Step 2 — 仓库卫生（C9，优先）

```bash
python tools/secret_scan_checker.py --git-remotes
python tools/secret_scan_checker.py --dir <产品仓>/projects
```

对照 [secrets_kconfig.txt](../prompts/secrets_kconfig.txt)：
- 入库 `config` / `sdkconfig` 是否含非空 SECRET/TOKEN
- `.gitignore` 是否含 `*.secrets` / `config.local` / `sdkconfig.local`
- Git remote 是否内嵌 token
- 是否有提交的调试日志含语音/鉴权数据

## Step 3 — 架构与文档

| 检查项 | 期望 |
|--------|------|
| `docs/ARCHITECTURE.md` | 存在且与当前 Kconfig 主路径一致 |
| README | 产品名/云栈与 defconfig 一致 |
| `components/README.md` | 链接有效 |
| 构建脚本 | 无硬编码绝对路径；支持 `-p` / 环境变量 |

## Step 4 — 产品代码静态审查

```bash
python tools/run_review.py --dir <产品仓>/components --platform <esp32|jl|bk|stm32>
```

手工 spot-check（checker 不覆盖）：
- **大文件 / 上帝模块**：单文件 >3k 行、`*_bind.c` / `*_manager.c` 职责是否过重
- Demo TODO（深睡 hack、临时 recover）是否阻塞量产
- LVGL 桥接是否走 `lv_async_call` / 平台 UI 队列 API（BK: `lvgl_port_lock`；JL: 消息队列；ESP: `esp_lvgl_port`）
- **语音产品**：prompt/TTS 后 uplink 时序 → [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt)（C10）
- **Audio/WSS 现场链路**：TTS 打断、shared voice handle、WSS 上行、speaker idle/deinit、TLS/堆栈峰值 → [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt)（C10）+ [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt)（C24）+ [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt)（C7/C20）
- **带屏音视频产品**：camera/video preview、音画同步、掉帧/爆音、长时间漂移、DMA/cache/零拷贝坏帧 → [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt)（C25）+ [av_codec_format.txt](../prompts/av_codec_format.txt)（C26）+ [av_clock_jitter.txt](../prompts/av_clock_jitter.txt)（C27）+ [av_dma_buffer_lifecycle.txt](../prompts/av_dma_buffer_lifecycle.txt)（C28）
- **产品层死代码（C6.5）** — 见 Step 4b

## Step 4b — 产品层裁剪 spot-check（C6.5）

对照 `main/CMakeLists.txt`（或 Makefile `srcs`）与 config，**未启用或未 init 的模块不得编入镜像**：

| 信号 | 处置 |
|------|------|
| Kconfig `=n`（MQTT/VAD/Camera 等） | 对应 `.c` 用 `if (CONFIG_*)` 守卫或移出 `srcs` |
| `super.init()` / `*_tool_init()` 从未调用 | 移出编译；若功能仍要，改到正确 init 链 |
| `#if 0` 整块或注释掉的 `*_start()` | 删除死代码或恢复完整链路，勿两头悬空 |
| Demo 组件（空 test、示例 moduleA/B/C） | 删除目录或移出 `components/` |
| 条件编译 Web 子模块 | 仅编已定义宏的模块 |
| 密钥在 `.c` `#define` | 迁 Kconfig + 本地 secrets（C9.1） |

平台实测裁剪表（打印机、带屏 AI 等）→ 各 `platforms/xxx.md`，勿在通用 workflow 硬编码产品名。

```bash
rg "super\.init\(\)|_tool_init|_instance\(\)->start" <产品仓>/main --glob '*.c' | head
```

## Step 5 — 构建与 CI

- 按 `platforms/xxx.md` 编译（如 `idf.py build` / `make ac791n_*` / `make bk7258` / `build.sh`）
- 是否缺 CI：secret scan + build smoke
- 产品层是否有单元测试（C5）

## Step 6 — 输出（优先修复顺序）

<output_format>

```markdown
## 结论
通过 / 需修复

## 优先修复顺序

### 🔴 P0 — 会导致死机/卡死/硬件风险（立即修复）
- C1.x — LVGL 跨线程调用 → 死机
- C4.x — ISR 中阻塞 → 系统卡死
- C12.x — API 返回值未检查 → HardFault
- C20.x — 网络永久阻塞 → 任务卡死
- C24.x — 外设未收尾 → 硬件损坏

### 🟠 P1 — 会导致内存泄漏/任务阻塞/状态错乱（本轮必须修复）
- C2.x — Queue payload 泄漏
- C3.x — cJSON 未 Delete
- C7.x — 内存泄漏/栈溢出
- C8.x — 启动顺序错误
- C13.x — 状态机异常未处理
- C19.x — NVS 未 commit

### 🟡 P2 — 可维护性/日志/结构优化（下轮迭代）
- C6.5 — 未 init 仍编入 / Demo 组件
- C11.x — 命名/函数长度
- C14.x — 日志规范
- C15.x — 优先级文档

### 🟢 P3 — 上线前安全/配置化（发布前）
- C9.x — 凭据硬编码（测试阶段例外）
- C14.4 — 日志脱敏（测试阶段例外）
- C5.x — 测试宏关闭

## Checker 摘要
- run_review: ...
- secret_scan: ...
- blocking_wait: ...

## 建议后续（按优先级）
1. 先修 P0（死机/卡死风险）
2. 再修 P1（泄漏/阻塞）
3. 最后处理 P2/P3（优化/配置化）
```

</output_format>
