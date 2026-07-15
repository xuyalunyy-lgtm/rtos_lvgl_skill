# 新手上手：从零到第一次固件审查

本路径假设你已有一个包含 C/C++ 固件源文件的目录，但尚未确定 SDK、芯片或 checker 该怎样选择。

## 1. 确认 Python 与目录

```powershell
python --version
cd path\to\freertos-embedded-architect-skill
```

Windows 推荐设置 UTF-8，避免旧控制台显示乱码：

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
```

## 2. 先做只读项目初检

```powershell
python tools/project_doctor.py path\to\your-project
```

它只扫描本地标记，不会构建、写 manifest 或连接设备。确认输出的平台、SDK 和配置文件后，再运行：

```powershell
python tools/project_doctor.py path\to\your-project --run-review
```

Doctor 会把平台、构建系统和 `sdkconfig` / `prj.conf` 传给审查器；不要手工把每个新芯片加入全局 manifest。

## 3. 第一次审查

```powershell
python tools/run_review.py --dir path\to\your-project --platform esp32 --markdown artifacts\first-review.md --html artifacts\first-review.html
```

将 `esp32` 换成 `stm32`、`jl`、`bk`、`zephyr` 或 `freertos`。`exit 1` 表示发现待审查问题，不表示命令损坏；先读报告中的 P0/P1，再逐项确认。

## 4. 处理一条告警

```powershell
python tools/constraint_lookup.py C15 --platform zephyr
```

该命令给出规则、自动 checker、good/bad fixture 和平台差异。修复后用同一命令重跑；JSON 历史默认保存在 `artifacts/review_history/`，可观察问题数是否 improved 或 regressed。

## 5. 开发时实时反馈

```powershell
python tools/run_review.py --dir path\to\your-project --platform esp32 --watch
```

首次保存前会完整审查一次。以后保存 C/C++ 文件时，只会对变动文件重跑相关 checker。它是快速反馈，不替代提交前的全量审查。

## 常见坑

| 现象 | 原因与处理 |
|---|---|
| `exit=1` | 代表 checker 发现问题；查看 Markdown/HTML 报告，不要把它当作 Python 崩溃。 |
| 平台选错 | `--platform` 会改变 SDK API 语义。先跑 `project_doctor.py`，不确定时不要猜。 |
| Zephyr 误报已禁用代码 | 传入 `--config prj.conf`；Doctor 的 `--run-review` 会自动传递。 |
| watch 没有触发 | watch 只监控 `--dir` 内的 C/C++ 文件；确认保存到该目录并保持终端运行。 |
| 报告没出现 | 确认目标父目录可写；使用 `--markdown artifacts/report.md` 或 `--html artifacts/report.html`。 |
| 某条约束不理解 | 用 `python tools/constraint_lookup.py Cxx`，再阅读它指向的分片和 fixture。 |

## 提交前

```powershell
python scripts/quick_gate.py --strict
```

它覆盖 fixture、路由、文档链接、MCP 自测和单元测试。不要把串口允许列表、Wi-Fi 密码、broker 凭据或 `artifacts/` 中的本地日志提交进仓库。
