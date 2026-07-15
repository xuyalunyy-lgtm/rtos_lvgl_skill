# Serial MCP

串口调试 MCP 服务器。支持智能日志分析、发送并等待、USB 设备身份识别、日志滚动与脱敏、书签标记、导出复现包。

## 5 分钟上手

**1. 配置 `.mcp.json`**

```json
"serial-mcp": {
  "command": "python",
  "args": ["mcp/serial_server.py"],
  "env": {
    "SERIAL_ALLOWED_PORTS": "COM3",
    "SERIAL_LOG_DIR": "artifacts/serial-logs"
  }
}
```

把 `COM3` 换成你实际的串口号。重启 MCP 服务器生效。

**2. 常用操作**

```
# 查看可用串口（含 USB VID/PID/序列号）
serial_list

# 连接
serial_connect(port="COM3", baudrate=115200)

# 发送命令并等待响应（最常用的调试方式）
serial_request(command="AT+RST", expect="ready", timeout=5.0)

# 查看最近日志
serial_get_lines(n=50)

# 搜索关键字
serial_search(keyword="ERROR")

# 标记关键时刻
serial_bookmark(label="wifi-test-start")

# 导出复现包
serial_export_bundle()
```

**3. 验证安装**

```bash
python mcp/serial_server.py --self-test
python mcp/test_serial_e2e.py
```

## 工具一览（13 个）

| 工具 | 说明 |
|------|------|
| `serial_list` | 列出串口，含 USB VID/PID/序列号/厂商信息 |
| `serial_connect` | 连接白名单串口，启动后台读取线程 |
| `serial_disconnect` | 断开连接 |
| `serial_write` | 发送原始数据 |
| **`serial_request`** | **发送命令并等待正则匹配**（替代手动 write+poll） |
| `serial_get_lines` | 从环形缓冲区读取最近日志 |
| `serial_search` | 搜索缓冲区关键字 |
| `serial_check_device` | 检测 USB 设备是否重新插入（可能换了端口） |
| `serial_get_stats` | 缓冲区统计（收发计数、时间范围） |
| `serial_watch` | 后台症状监控（崩溃、WDT、堆耗尽等） |
| `serial_bookmark` | 在日志中标记关键时刻 |
| `serial_export_bundle` | 导出最小复现包（JSON） |
| `serial_summary` | 缓冲区健康摘要 |

## `serial_request` — 发并等

最有价值的工具。替代手动 write → poll → check 循环：

```
serial_request(command="AT+RST", expect="ready", timeout=5.0)
```

匹配成功返回：
```json
{"ok": true, "matched_line": "ready", "match_groups": [], "context": ["...", "ready"], "elapsed_ms": 312}
```

超时返回（含最近 RX 日志，方便诊断）：
```json
{"ok": false, "error": "timeout", "recent_rx": ["...", "..."], "elapsed_ms": 5000}
```

## USB 设备身份

不再只靠 COM 口名称识别设备：

```json
{"port": "COM3", "vid": "0x1a86", "pid": "0x7523", "serial_number": "ABC123", "manufacturer": "wch.cn"}
```

白名单支持三种格式：
- `COM3` — 端口名（原有）
- `vid:1a86 pid:7523` — USB VID:PID
- `serial:ABC123` — 序列号

`serial_check_device` 可检测同一块板是否换了端口重新插入。

## 日志工程

### 滚动
- 按大小滚动（默认每个文件 5MB，保留最近 10 个）
- 通过 `SERIAL_LOG_MAX_SIZE` 和 `SERIAL_LOG_MAX_FILES` 配置

### 元数据
每个日志文件开头写入会话元数据：
```
# session_start: 2026-07-15T12:00:00Z
# port: COM3
# baudrate: 115200
# device_vid: 0x1a86
```

### 脱敏
敏感数据写入磁盘前自动掩码。默认规则：
- `password=...`、`token=...`、`secret=...`、`api_key=...`
- `AT+CWJAP="ssid","password"`（Wi-Fi 凭据）

自定义规则：`SERIAL_REDACT_PATTERNS` 环境变量（逗号分隔的正则表达式）。

### 书签
`serial_bookmark("wifi-test-start")` 在日志和缓冲区中写入带时间戳的标记。

### 导出
`serial_export_bundle()` 创建 JSON 文件，包含：
- 最近日志行（已脱敏）
- 串口配置和设备身份
- Watch 告警
- 缓冲区摘要

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SERIAL_ALLOWED_PORTS` | （空 = 拒绝所有） | 逗号分隔的串口白名单 |
| `SERIAL_LOG_DIR` | （无） | 日志输出目录 |
| `SERIAL_LOG_MAX_SIZE` | `5242880`（5MB） | 单个日志文件最大字节数 |
| `SERIAL_LOG_MAX_FILES` | `10` | 每个端口最多保留的日志文件数 |
| `SERIAL_REDACT_PATTERNS` | （内置） | 逗号分隔的脱敏正则表达式 |

## 测试

```bash
# 单元自测（不需要硬件）
python mcp/serial_server.py --self-test

# E2E 测试（使用 loopback mock，不需要硬件）
python mcp/test_serial_e2e.py
```
