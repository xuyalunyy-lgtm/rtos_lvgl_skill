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
        "description": "Connect to a serial port. Starts background reading into local ring buffer.",
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
                    "description": "Search keyword (case-sensitive substring match)",
                },
                "n": {
                    "type": "integer",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 5000,
                    "description": "Max results to return (most recent)",
                },
            },
            "required": ["keyword"],
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
        "description": "Start/stop/query background log monitoring. When active, automatically detects symptoms (crash, WDT, heap exhaustion, etc.) and generates alerts. Uses the same symptom routes as log_triage.",
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
