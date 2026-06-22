# FreeRTOS Embedded Architect Skill

Cursor Agent Skill：FreeRTOS 物联网固件架构（MVP 分层、LVGL 线程安全、I2S DMA、音视频管线/A-V sync、编解码格式一致性、时钟漂移/jitter buffer、DMA cache/零拷贝 buffer 生命周期、cJSON 防泄漏、WSS/mbedTLS、SDK 裁剪、错误处理、状态机、日志规范、任务优先级、定时器管理、多核 IPC、低功耗、显示驱动、软硬联调 IO 口规划）。约束体系 C1–C28（当前 27 个约束域，C22 预留）。

## 快速开始

1. 安装：见 [INSTALL.md](INSTALL.md)
2. 控制平面：[SKILL.md](SKILL.md)
3. 结构说明：[references/skill_structure.md](references/skill_structure.md)
4. Agent 对话示例：「BK7258 WSS + LVGL MVP 架构 review」

## 四层结构

```
L0  SKILL.md                 意图路由（<100 行）
L0  agents/openai.yaml       Codex/OpenAI UI 元数据
L1  workflows/               编排（见 workflows/README.md）
L2  references/              总纲 · 约束矩阵 · 结构
L3  prompts/ + platforms/   场景 + 平台（按需 1–3 + 1）
L4  examples/ + tools/       完整版专有
```

| 路径 | 职责 |
|------|------|
| [workflows/](workflows/) | L2/L3/Debug/自我迭代 Step 编排 |
| [agents/](agents/) | Codex/OpenAI UI 元数据 |
| [references/](references/) | core_rules、constraint_detail、skill_structure、iteration_log |
| [prompts/](prompts/) | 场景专链（按 C 域索引见 skill_structure） |
| [platforms/](platforms/) | ESP32 / STM32 / JL / BK 专档 |
| [examples/](examples/) | good/bad 范例 + `app_mvp.h` |
| [tools/](tools/) | checker、codegen、fixtures、checker registry |
| [scripts/](scripts/) | sync、iterate、install（含 `.cmd` 包装） |
| [freertos-skill-lite/](freertos-skill-lite/) | Lite 分发（sync 生成，勿手改） |

安装包边界：Cursor / Claude Code / Codex 安装脚本会排除仓库根目录 `README.md`、`INSTALL.md`、`CHANGELOG.md`、`.github/`、`.vscode/`、`freertos-skill-lite/`、缓存与本地 SDK；源码仓保留这些维护资产，运行时索引如 `workflows/README.md` 保留。

## 常用验证

```bash
python tools/run_review.py --list-checkers
python tools/run_review.py --self-test
python tools/run_review.py --validate-examples
python scripts/check_runtime_distribution.py
python scripts/check_skill_metadata.py
python scripts/check_skill_metadata.py --self-test
python scripts/skill_iterate.py --check
```

## 关键范例

| 类型 | 文件 |
|------|------|
| 正例 WSS Model | [examples/good_wss_json_parse.c](examples/good_wss_json_parse.c) |
| 正例 Presenter | [examples/good_presenter_consumer.c](examples/good_presenter_consumer.c) |
| 正例 语音 Uplink | [examples/good_voice_prompt_uplink.c](examples/good_voice_prompt_uplink.c) |
| 正例 音视频同步 | [examples/good_av_pipeline_sync.c](examples/good_av_pipeline_sync.c) |
| 正例 媒体格式 | [examples/good_media_format_contract.c](examples/good_media_format_contract.c) |
| 正例 时钟/Jitter | [examples/good_av_clock_jitter.c](examples/good_av_clock_jitter.c) |
| 正例 DMA/cache buffer | [examples/good_av_dma_buffer_lifecycle.c](examples/good_av_dma_buffer_lifecycle.c) |
| 反例 WSS 栈/重连 | [examples/bad_wss_blocking.c](examples/bad_wss_blocking.c) |
| 反例 音视频阻塞 | [examples/bad_av_pipeline_blocking.c](examples/bad_av_pipeline_blocking.c) |
| 反例 媒体格式 | [examples/bad_media_format_mismatch.c](examples/bad_media_format_mismatch.c) |
| 反例 时钟/Jitter | [examples/bad_av_clock_jitter.c](examples/bad_av_clock_jitter.c) |
| 反例 DMA/cache buffer | [examples/bad_av_dma_buffer_lifecycle.c](examples/bad_av_dma_buffer_lifecycle.c) |
| 反例 C12 返回值 | [examples/bad_unchecked_return.c](examples/bad_unchecked_return.c) |
| 反例 C14 日志 | [examples/bad_isr_printf.c](examples/bad_isr_printf.c) |
| 共享类型 | [examples/app_mvp.h](examples/app_mvp.h) |
