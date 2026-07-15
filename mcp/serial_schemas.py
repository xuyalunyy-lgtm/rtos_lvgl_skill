"""Serial MCP tool schemas — JSON Schema definitions for all serial tools."""

SERIAL_TOOL_SCHEMAS = [
    {
        "name": "serial_list",
        "description": "List available serial ports on the system.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_connect",
        "description": "Connect to a serial port. Starts background reading into a local ring buffer and, when SERIAL_LOG_DIR is configured, a persistent session log.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "port": {
                    "type": "string",
                    "description": "Serial port name (e.g., COM3, /dev/ttyUSB0)",
                },
                "baudrate": {
                    "type": "integer",
                    "default": 115200,
                    "description": "Baud rate (e.g., 9600, 115200, 921600)",
                },
                "bytesize": {
                    "type": "integer",
                    "enum": [5, 6, 7, 8],
                    "default": 8,
                    "description": "Data bits",
                },
                "parity": {
                    "type": "string",
                    "enum": ["N", "E", "O", "M", "S"],
                    "default": "N",
                    "description": "Parity (None, Even, Odd, Mark, Space)",
                },
                "stopbits": {
                    "type": "number",
                    "enum": [1, 1.5, 2],
                    "default": 1,
                    "description": "Stop bits",
                },
                "auto_reconnect": {
                    "type": "boolean",
                    "default": True,
                    "description": "Keep the session alive and retry the same port after read failures",
                },
            },
            "required": ["port"],
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_disconnect",
        "description": "Disconnect from the current serial port.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_session_start",
        "description": "Start a receive-only serial session. The local reader runs continuously; transient read failures retry the same port and preserve diagnostics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "port": {
                    "type": "string",
                    "description": "Serial port to monitor (for example COM10)",
                },
                "baudrate": {
                    "type": "integer",
                    "default": 115200,
                    "description": "Baud rate",
                },
                "bytesize": {
                    "type": "integer",
                    "enum": [5, 6, 7, 8],
                    "default": 8,
                    "description": "Data bits",
                },
                "parity": {
                    "type": "string",
                    "enum": ["N", "E", "O", "M", "S"],
                    "default": "N",
                    "description": "Parity",
                },
                "stopbits": {
                    "type": "number",
                    "enum": [1, 1.5, 2],
                    "default": 1,
                    "description": "Stop bits",
                },
                "auto_reconnect": {
                    "type": "boolean",
                    "default": True,
                    "description": "Retry the original port after transient failures",
                },
            },
            "required": ["port"],
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_session_poll",
        "description": "Return only newly received serial lines since after_sequence, with live session and reconnect health. Pass next_sequence from the prior response on the next call.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "after_sequence": {
                    "type": "integer",
                    "default": 0,
                    "minimum": 0,
                    "description": "Last consumed sequence number from the prior poll",
                },
                "n": {
                    "type": "integer",
                    "default": 200,
                    "minimum": 1,
                    "maximum": 1000,
                    "description": "Maximum new entries to return",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_session_stop",
        "description": "Stop the persistent receive-only session and release the serial port.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_write",
        "description": "Send data to the connected serial port. Data is also recorded in the local buffer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Data to send (string)",
                },
                "newline": {
                    "type": "string",
                    "default": "",
                    "description": "Newline suffix (e.g., '\\r\\n', '\\n', '' for none)",
                },
            },
            "required": ["data"],
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_request",
        "description": "Send a command and wait for a matching response. Returns matched line with context, or timeout with recent RX history. Supports MCP notifications/cancelled. More reliable than manual write+poll.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to send (e.g., 'AT+RST', 'AT+GMR')",
                },
                "expect": {
                    "type": "string",
                    "description": "Regex pattern to match in RX lines (e.g., 'ready', 'OK', 'ERROR')",
                },
                "timeout": {
                    "type": "number",
                    "default": 5.0,
                    "minimum": 0.1,
                    "maximum": 30.0,
                    "description": "Max seconds to wait for match",
                },
                "newline": {
                    "type": "string",
                    "default": "\r\n",
                    "description": "Newline suffix appended to command",
                },
                "context_lines": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 0,
                    "maximum": 20,
                    "description": "Number of RX lines before/after match to include in context",
                },
            },
            "required": ["command", "expect"],
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_get_lines",
        "description": "Read lines from the local ring buffer. Data is stored locally and only returned when this tool is called — no tokens consumed until you ask.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 10000,
                    "description": "Number of recent lines to return",
                },
                "direction": {
                    "type": "string",
                    "enum": ["rx", "tx"],
                    "description": "Filter by direction: 'rx' (received) or 'tx' (sent). Omit for both.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_search",
        "description": "Search the local ring buffer for a keyword. Returns matching lines only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Search keyword",
                },
                "n": {
                    "type": "integer",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 5000,
                    "description": "Max results to return (most recent)",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "default": True,
                    "description": "Use a case-sensitive substring match (default: true)",
                },
            },
            "required": ["keyword"],
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_check_device",
        "description": "Check if the previously connected device is still present. Detects USB reconnection on a different port by comparing VID/PID/serial number.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_get_stats",
        "description": "Get ring buffer statistics: total lines, rx/tx counts, time range.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_watch",
        "description": "Start/stop/query background log monitoring. Alerts include a context_router diagnostic plan, so WDT/crash detection directly identifies debug_crash.md, constraints, probes, and checker targets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "alerts", "status"],
                    "description": "Action: start monitoring, stop monitoring, get recent alerts, or get status",
                },
                "platform": {
                    "type": "string",
                    "enum": ["esp32", "stm32", "jl", "bk", "zephyr"],
                    "default": "esp32",
                    "description": "Target platform (for symptom matching, only used with 'start')",
                },
                "n": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Number of recent alerts to return (only used with 'alerts')",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_bookmark",
        "description": "Mark a moment in the log with a labeled bookmark. Useful for marking test start, critical events, etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Human-readable bookmark label (e.g., 'wifi-connect-test', 'ota-start')",
                },
            },
            "required": ["label"],
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_export_bundle",
        "description": "Export a minimal reproduction bundle: recent log lines, serial config, device identity, watch alerts. Useful for filing bug reports.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "context_lines": {
                    "type": "integer",
                    "default": 200,
                    "minimum": 10,
                    "maximum": 5000,
                    "description": "Number of recent buffer lines to include",
                },
                "include_alerts": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include watch alerts in the bundle",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "serial_summary",
        "description": "Analyze recent log buffer and return a health summary: severity counts, detected symptoms, boot events, error samples. No tokens consumed until called.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "default": 500,
                    "minimum": 50,
                    "maximum": 5000,
                    "description": "Number of recent buffer lines to analyze",
                },
            },
            "additionalProperties": False,
        },
    },
]

# ── Resource Schemas ──

SERIAL_RESOURCE_SCHEMAS = [
    {
        "uri": "serial://connection-status",
        "name": "Serial Connection Status",
        "description": "Current serial port connection state, port name, baud rate, and buffer size",
        "mimeType": "application/json",
    },
    {
        "uri": "serial://log-buffer",
        "name": "Serial Log Buffer",
        "description": "Recent lines from the ring buffer (last 100 lines)",
        "mimeType": "application/json",
    },
    {
        "uri": "serial://available-ports",
        "name": "Available Serial Ports",
        "description": "List of serial ports detected on this system",
        "mimeType": "application/json",
    },
]
