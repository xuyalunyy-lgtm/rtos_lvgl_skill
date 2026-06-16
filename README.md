# FreeRTOS Embedded Architect Skill

Cursor Agent Skill：FreeRTOS 物联网固件架构（MVP 分层、LVGL 线程安全、I2S DMA、cJSON 防泄漏、WSS/mbedTLS、JL/BK SDK 需求驱动裁剪）。

## 快速开始

1. 安装：见 [INSTALL.md](INSTALL.md)
2. 控制平面：[SKILL.md](SKILL.md)
3. 结构说明：[references/skill_structure.md](references/skill_structure.md)
4. Agent 对话示例：「BK7258 WSS + LVGL MVP 架构 review」

## 四层结构

```
L0  SKILL.md                 意图路由（<100 行）
L1  workflows/               编排（见 workflows/README.md）
L2  references/              总纲 · 约束矩阵 · 结构
L3  prompts/ + platforms/   场景 + 平台（按需 1–3 + 1）
L4  examples/ + tools/       完整版专有
```

| 路径 | 职责 |
|------|------|
| [workflows/](workflows/) | L2/L3/Debug/自我迭代 Step 编排 |
| [references/](references/) | core_rules、constraint_detail、skill_structure、iteration_log |
| [prompts/](prompts/) | 场景专链（按 C 域索引见 skill_structure） |
| [platforms/](platforms/) | ESP32 / STM32 / JL / BK 专档 |
| [examples/](examples/) | good/bad 范例 + `app_mvp.h` |
| [tools/](tools/) | checker、codegen、fixtures |
| [scripts/](scripts/) | sync、iterate、install（含 `.cmd` 包装） |
| [freertos-skill-lite/](freertos-skill-lite/) | Lite 分发（sync 生成，勿手改） |

## 关键范例

| 类型 | 文件 |
|------|------|
| 正例 WSS Model | [examples/good_wss_json_parse.c](examples/good_wss_json_parse.c) |
| 正例 Presenter | [examples/good_presenter_consumer.c](examples/good_presenter_consumer.c) |
| 反例 WSS 栈/重连 | [examples/bad_wss_blocking.c](examples/bad_wss_blocking.c) |
| 共享类型 | [examples/app_mvp.h](examples/app_mvp.h) |
