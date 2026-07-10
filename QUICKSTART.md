# Quick Start — 5 分钟跑出第一次 Review

## 1. 环境准备

需要 Python 3.10+，无需安装任何依赖。

```bash
# Windows (PowerShell)
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'

# macOS / Linux
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
```

## 2. 一键 Review 单个文件

```bash
# Review 反例（bad_*.c 默认排除，需加 --include-bad）
python tools/run_review.py examples/bad_unchecked_return.c --platform esp32 --include-bad
```

预期输出（约 30 秒）：

```
[return_check_checker] ... 发现 4 个 C12 告警
[isr_safety_checker] ... 发现问题
Summary: 存在告警/失败 (exit=1)，请人工核对
```

**exit=1 表示发现问题**，exit=0 表示全部通过。

> 注意：`bad_*.c` 文件默认被排除（它们是反例，不是你的代码）。用 `--include-bad` 可纳入审查。
> Checker 是启发式的，good_*.c 也可能触发少量警告——这是正常的，需人工判断。

## 3. Review 整个目录

```bash
python tools/run_review.py --dir ./src --platform esp32
```

- 默认排除 `bad_*.c` 反例（加 `--include-bad` 可纳入）
- `--platform` 可选：`esp32` / `stm32` / `jl` / `bk` / `freertos` / `zephyr`

## 4. 查看有哪些 Checker

```bash
python tools/run_review.py --list-checkers
```

## 5. 跑 Quick Gate（全量自测）

```bash
python scripts/quick_gate.py
```

这会依次运行：self-test、example 验证、log triage、text encoding、runtime distribution、link check、LVGL regression 等 15 项检查。LVGL regression 是 non-blocking，失败会显示 WARN；其余阻断项全部 PASS 才算通过。

## 6. JSON 输出（CI 集成）

```bash
python tools/run_review.py --dir ./src --platform esp32 --json
```

输出结构化 JSON，包含每个 checker 的 issue 数和 exit code。

## 7. 上下文路由（选工作流）

不确定用哪个 workflow？先跑路由：

```bash
python tools/context_router.py --workflow code_review --platform esp32 --json
```

或用症状文本自动推断：

```bash
python tools/context_router.py --symptom-text "HardFault in audio task" --json
```

## 8. 入口边界

| 场景 | 入口 | 说明 |
|------|------|------|
| CLI / CI | `python tools/run_review.py` | 一键静态审查 |
| Claude Code / IDE | MCP tools | 通过 `.mcp.json` 自动加载 |
| LVGL 页面生成 | MCP 优先 | MCP 不可用时 fallback 到 `workflows/l3_lvgl_page.md` |
| Quick Gate | `python scripts/quick_gate.py` | 发布前全量自测 |

## 常见问题

**Q: Windows 下输出乱码？**
设置 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。

**Q: 想看某个 checker 的详细规则？**
查看 `references/constraint_quick_index.md` 找到对应约束 ID，再查对应分片文件。

**Q: 如何给自己的代码写 fixture？**
参考 `tools/fixtures/` 目录下的 `good_*.c` 和 `bad_*.c` 文件。
