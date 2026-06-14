# Workflow: L2 工程审查（多仓 / 固件产品）

**触发：** 用户要求审查整个工程、workspace review、量产前审计、架构 review。

<thinking>
1. 识别工作区：产品仓 + SDK 仓 + skill（若有）
2. 平台默认 BK7258 时读 platforms/bk.md
3. 分三层：仓库卫生(C9) → 架构文档 → 组件代码(C1–C8)
4. 产品 components 跑 run_review；config 跑 secret_scan
</thinking>

## Step 1 — 总纲与平台

- [core_rules.md](../references/core_rules.md)
- [constraint_index.md](../references/constraint_index.md)（含 **C9**）
- [platforms/bk.md](../platforms/bk.md) 或用户指定平台

## Step 2 — 仓库卫生（C9，优先）

```bash
python tools/secret_scan_checker.py --git-remotes
python tools/secret_scan_checker.py --dir <产品仓>/projects
```

对照 [secrets_kconfig.txt](../prompts/secrets_kconfig.txt)：
- 入库 `config` 是否含非空 SECRET/TOKEN
- `.gitignore` 是否含 `config.secrets` / `config.local`
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
python tools/run_review.py --dir <产品仓>/components --platform bk
```

手工 spot-check（checker 不覆盖）：
- `naozhong_duer_bind` / 大文件职责是否过重（如 `system_manager.c` >3k 行、`webparse.c` >3k 行）
- Demo TODO（深睡 hack、LED recover）是否阻塞量产
- LVGL 桥接是否走 `lvgl_port_lock` / `lv_async_call` / `lvMsgSendToLvgl`
- **产品层死代码（C6.5）** — 见 Step 4b

## Step 4b — 产品层裁剪 spot-check（C6.5）

对照 `main/CMakeLists.txt` 与 `config/*/config`，**未启用或未 init 的模块不得编入镜像**：

| 信号 | 处置 |
|------|------|
| Kconfig `=n`（如 `PAHO_MQTT`、`PROTOCOL_USE_MQTT`、`VAD`、`DVP_CAMERA`） | 对应 `.c` 用 `if (CONFIG_*)` 守卫或移出 `srcs` |
| `super.init()` / `*_tool_init()` 从未调用 | 移出编译；若功能仍要，改到正确 init 链（如 MCP → `iot_devices_init`） |
| `#if 0` 整块或注释掉的 `*_instance()->start()` | 删除死代码或恢复完整链路，勿两头悬空 |
| Demo 组件（`moduleA/B/C`、空 `list_test.c`） | 删除目录或移出 `components/` |
| Webnet/AP：仅 `WEBNET_USING_CGI` 开启 | 勿编 asp/dav/ssi/upload 等未定义宏的模块 |
| 密钥在 `.c` `#define` | 迁 Kconfig + `config.secrets`（C9.1） |

BK 打印机类：`CONFIG_IOT_DEV_CAMERA` 默认 `n`（无 DVP）；JPEG 打印走 `print_job` + `img_rgb565`，与 MCP camera 无关。

```bash
# 辅助：找未编入但残留的大文件 / 孤儿源
rg -l "list_test|moduleA" projects/<app>/main || true
rg "super\.init\(\)|_tool_init" projects/<app>/main --glob '*.c' | head
```

## Step 5 — 构建与 CI

- 能否 `make bk7258` 或 `build.sh` 零配置路径编译
- 是否缺 CI：secret scan + build smoke
- 产品层是否有单元测试（C5）

## Step 6 — 输出

<output_format>

```markdown
## 结论
通过 / 需修复

## P0（安全/崩溃）
- C9.x / C1.x — 位置 — 问题 — 修复

## P1（稳定性/文档）
...

## P2（裁剪 / 技术债）
- C6.5 — 未 init 仍编入 / Demo 组件 / Webnet 冗余模块

## Checker 摘要
- run_review: ...
- secret_scan: ...

## 建议后续
1. ...
```

</output_format>
