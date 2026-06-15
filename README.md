# FreeRTOS Embedded Architect Skill

Cursor Agent Skill：FreeRTOS 物联网固件架构（MVP 分层、LVGL 线程安全、I2S DMA、cJSON 防泄漏、WSS/mbedTLS、JL/BK SDK 需求驱动裁剪）。

## 快速开始

1. 安装：见 [INSTALL.md](INSTALL.md)
2. 核心入口：[SKILL.md](SKILL.md)
3. 在 Agent 对话中描述平台与任务，例如：「BK7258 WSS + LVGL MVP 架构 review」

## 目录结构

```
SKILL.md              # 控制平面：意图路由 → workflows/
workflows/            # L2/L3/Debug/自我迭代 编排
references/           # core_rules、iteration_log、Lite 清单
CHANGELOG.md          # 版本历史
scripts/sync_lite.py  # 生成 Lite SKILL.md + 同步子目录
platforms/            # 平台专档
prompts/              # 场景专链
examples/             # Few-Shot + app_mvp.h
tools/                # checker、codegen、fixtures/
freertos-skill-lite/  # Lite 分发包
```

## 关键范例

| 类型 | 文件 |
|------|------|
| 正例 WSS Model | [examples/good_wss_json_parse.c](examples/good_wss_json_parse.c) |
| 正例 Presenter | [examples/good_presenter_consumer.c](examples/good_presenter_consumer.c) |
| 反例 WSS 栈/重连 | [examples/bad_wss_blocking.c](examples/bad_wss_blocking.c) |
| 共享类型 | [examples/app_mvp.h](examples/app_mvp.h) |
