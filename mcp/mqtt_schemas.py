"""MQTT MCP tool schemas — JSON Schema definitions for all MQTT tools."""

MQTT_TOOL_SCHEMAS = [
    {
        "name": "mqtt_connect",
        "description": "Connect to an MQTT broker. Supports TLS and authentication.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "MQTT broker hostname or IP",
                },
                "port": {
                    "type": "integer",
                    "default": 1883,
                    "minimum": 1,
                    "maximum": 65535,
                    "description": "MQTT broker port (1883 for plain, 8883 for TLS)",
                },
                "client_id": {
                    "type": "string",
                    "description": "MQTT client ID (auto-generated if omitted)",
                },
                "username": {
                    "type": "string",
                    "description": "Authentication username",
                },
                "password": {
                    "type": "string",
                    "description": "Authentication password",
                },
                "tls": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable TLS encryption",
                },
                "keepalive": {
                    "type": "integer",
                    "default": 60,
                    "minimum": 10,
                    "maximum": 300,
                    "description": "Keepalive interval in seconds",
                },
            },
            "required": ["host"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mqtt_disconnect",
        "description": "Disconnect from the current MQTT broker.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "mqtt_publish",
        "description": "Publish a message to an MQTT topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "MQTT topic to publish to",
                },
                "payload": {
                    "type": "string",
                    "description": "Message payload (string, max 64KB)",
                },
                "qos": {
                    "type": "integer",
                    "enum": [0, 1, 2],
                    "default": 0,
                    "description": "Quality of Service level (0=at most once, 1=at least once, 2=exactly once)",
                },
                "retain": {
                    "type": "boolean",
                    "default": False,
                    "description": "Retain message on broker",
                },
            },
            "required": ["topic", "payload"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mqtt_subscribe",
        "description": "Subscribe to an MQTT topic. Supports wildcards: + (single level), # (multi level).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "MQTT topic filter (e.g., 'sensor/+/temperature', 'device/#')",
                },
                "qos": {
                    "type": "integer",
                    "enum": [0, 1, 2],
                    "default": 0,
                    "description": "Quality of Service level",
                },
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mqtt_unsubscribe",
        "description": "Unsubscribe from an MQTT topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "MQTT topic to unsubscribe from",
                },
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mqtt_list_topics",
        "description": "List all currently subscribed MQTT topics with their QoS levels.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "mqtt_get_messages",
        "description": "Read message history from the ring buffer. Supports topic filtering and pagination.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Filter by topic prefix (e.g., 'sensor/' matches all sensor topics)",
                },
                "limit": {
                    "type": "integer",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000,
                    "description": "Maximum number of messages to return",
                },
                "since_timestamp": {
                    "type": "number",
                    "description": "Unix timestamp — only return messages after this time",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "mqtt_clear_messages",
        "description": "Clear the message history ring buffer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Clear only messages matching this topic prefix (omit to clear all)",
                },
            },
            "additionalProperties": False,
        },
    },
]

# ── Resource Schemas ──

MQTT_RESOURCE_SCHEMAS = [
    {
        "uri": "mqtt://connection-status",
        "name": "MQTT Connection Status",
        "description": "Current MQTT connection state, broker address, client ID, and subscription list",
        "mimeType": "application/json",
    },
    {
        "uri": "mqtt://message-history",
        "name": "MQTT Message History",
        "description": "Recent messages from the ring buffer (last 100 messages)",
        "mimeType": "application/json",
    },
    {
        "uri": "mqtt://subscribed-topics",
        "name": "MQTT Subscribed Topics",
        "description": "Currently subscribed MQTT topics with QoS levels",
        "mimeType": "application/json",
    },
]
