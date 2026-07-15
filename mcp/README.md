# Serial MCP

串口调试 MCP 服务器。支持智能日志分析、发送并等待、USB 设备身份识别、日志滚动与脱敏、书签标记、导出复现包。

## 5 分钟上手

**1. 配置 `.mcp.json`**

```json
"serial-mcp": {
  "command": "python",
  "args": ["mcp/serial_server.py"],
  "env": {
    "SERIAL_LOG_DIR": "%TEMP%/freertos-serial-logs"
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
# 忽略大小写搜索
serial_search(keyword="error", case_sensitive=false)

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
| `serial_connect` | 连接指定串口，启动后台读取线程 |
| `serial_disconnect` | 断开连接 |
| `serial_write` | 发送原始数据 |
| **`serial_request`** | **发送命令并等待正则匹配**（支持 MCP 取消） |
| `serial_get_lines` | 从环形缓冲区读取最近日志 |
| `serial_search` | 搜索缓冲区关键字（可选忽略大小写） |
| `serial_check_device` | 检测 USB 设备是否重新插入（可能换了端口） |
| `serial_get_stats` | 缓冲区统计（收发计数、时间范围） |
| `serial_watch` | 后台症状监控，并附带自动诊断计划 |
| `serial_bookmark` | 在日志中标记关键时刻 |
| `serial_export_bundle` | 导出最小复现包（JSON） |
| `serial_summary` | 缓冲区健康摘要 |
| `serial_session_start` | 启动持续接收会话，默认在读异常后重连同一端口 |
| `serial_session_poll` | 增量读取新日志，并返回断线/重连状态 |
| `serial_session_stop` | 停止会话并释放端口 |

## 持续接收与分析

使用一个会话持续接收，不必重复连接或读取整段历史：

```text
serial_session_start(port="COM10", baudrate=1000000)
serial_session_poll(after_sequence=0, n=200)
# 下次将返回的 next_sequence 传回 after_sequence
serial_session_stop()
```

会话遇到瞬时读错误时会保留 `connection_state`、`last_disconnect_reason`、
`last_read_error` 和重连计数；它只会重连原端口，绝不按相同 VID/PID 自动
切换到另一块设备。

## `serial_request` — 发并等

最有价值的工具。替代手动 write → poll → check 循环：

```
serial_request(command="AT+RST", expect="ready", timeout=5.0)
```

匹配成功返回：
```json
{"ok": true, "matched_line": "ready", "matched_sequence": 42, "match_groups": [], "context": ["...", "ready"], "elapsed_ms": 312}
```

客户端可通过 JSON-RPC `notifications/cancelled` 及原始请求 ID 取消仍在等待的请求；取消会返回 `{"ok": false, "error": "cancelled"}`。

超时返回（含最近 RX 日志，方便诊断）：
```json
{"ok": false, "error": "timeout", "recent_rx": ["...", "..."], "elapsed_ms": 5000}
```

## `serial_watch` — 自动诊断桥接

检测到 WDT、HardFault、Guru Meditation 等告警时，每条 alert 都会附带 `diagnostic_plan`。它由 `context_router` 生成，包含推荐工作流（例如 `crash_debug`）、`workflows/debug_crash.md` 等必读文件、约束、诊断探针和 checker 目标。调用方读取 alert 后即可直接进入对应调试流程，无需再手工复制日志。

## USB 设备身份

除了 COM 口名称，也会记录设备身份：

```json
{"port": "COM3", "vid": "0x1a86", "pid": "0x7523", "serial_number": "ABC123", "manufacturer": "wch.cn"}
```

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

## MQTT release-safety probes

The MQTT MCP now separates policy validation from broker verification:

```text
mqtt_validate_qos_policy(message_class="availability", qos=1, retain=true)
mqtt_verify_retained(topic="device/42/status", expected_payload="online")
mqtt_test_will(topic="device/42/status", payload="offline", qos=1, retain=true)
```

`mqtt_verify_retained` and `mqtt_test_will` create isolated, short-lived
probe clients on the already connected broker. The Will probe deliberately
closes only its temporary client's transport; it never interrupts the main
MCP connection. Keep probe topics scoped to a disposable test device/topic.

## OTA signed A/B workflow

Only Ed25519-signed firmware can be pushed or scheduled for an A/B switch.
Create `ota_trusted_keys.json` beside the repository root (or set
`OTA_TRUSTED_KEYS_FILE`) with public keys only:

```json
{
  "keys": {
    "release-2026": {"public_key_pem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n"}
  }
}
```

Upload a detached signature with `ota_upload(signature_path=..., key_id="release-2026")`, then run
`ota_verify_signature`. The release operations reject unsigned, untrusted, or
hash-mismatched artifacts. Private signing keys must remain outside this
repository and are never accepted by the MCP server.

For A/B control-plane verification:

```text
ota_prepare_ab_switch(device_ip="...", platform="esp32", version="1.2.0")
ota_test_rollback(device_ip="...")
ota_report_boot_result(device_ip="...", partition="B", success=true)
```

The device bootloader performs the physical partition selection and reports
the boot result. The MCP tracks and validates the transition; a failed pending
slot keeps the known-good active slot and is recorded as `rolled_back`.

## Shared MCP runtime

Serial, MQTT, and OTA servers share `mcp_runtime.py`. Every `tools/call` now
uses the same JSON-schema subset validation, fragmented stdin JSON buffering,
and output redaction. Long serial requests and MQTT broker probes also honor
`notifications/cancelled` by JSON-RPC request ID.

Set `MCP_AUDIT_LOG_DIR` to enable local JSONL audit records. Arguments and
results are redacted before writing; passwords, tokens, secrets, API keys,
authorization values, and private-key fields are never persisted. Auditing is
best-effort and cannot block a device-control operation.
