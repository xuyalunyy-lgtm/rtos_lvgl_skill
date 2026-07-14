"""OTA MCP tool schemas — JSON Schema definitions for all OTA tools."""

OTA_TOOL_SCHEMAS = [
    {
        "name": "ota_start",
        "description": "Start the local OTA firmware server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "default": "localhost",
                    "description": "Server bind address (must be in OTA_ALLOWED_HOSTS)",
                },
                "port": {
                    "type": "integer",
                    "default": 8080,
                    "minimum": 1024,
                    "maximum": 65535,
                    "description": "Server port",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_stop",
        "description": "Stop the OTA firmware server.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_server_status",
        "description": "Get OTA server status including running state and connected devices.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_upload",
        "description": "Upload a firmware binary to the local repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Target platform (e.g., esp32, stm32, jl, bk)",
                },
                "version": {
                    "type": "string",
                    "description": "Semantic version (e.g., 1.0.0)",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to firmware binary file",
                },
                "description": {
                    "type": "string",
                    "default": "",
                    "description": "Optional firmware description",
                },
            },
            "required": ["platform", "version", "file_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_list",
        "description": "List all firmware in the repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Filter by platform (omit for all)",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_delete",
        "description": "Delete a firmware version from the repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Target platform",
                },
                "version": {
                    "type": "string",
                    "description": "Version to delete",
                },
            },
            "required": ["platform", "version"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_info",
        "description": "Get detailed information about a specific firmware version.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Target platform",
                },
                "version": {
                    "type": "string",
                    "description": "Firmware version",
                },
            },
            "required": ["platform", "version"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_push",
        "description": "Push upgrade notification to a specific device.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_ip": {
                    "type": "string",
                    "description": "Target device IP address",
                },
                "platform": {
                    "type": "string",
                    "description": "Firmware platform",
                },
                "version": {
                    "type": "string",
                    "description": "Target firmware version",
                },
            },
            "required": ["device_ip", "platform", "version"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_push_all",
        "description": "Push upgrade notification to all online devices of a platform.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Target platform",
                },
                "version": {
                    "type": "string",
                    "description": "Target firmware version",
                },
            },
            "required": ["platform", "version"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_device_status",
        "description": "Get status of a registered device.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_ip": {
                    "type": "string",
                    "description": "Device IP address",
                },
            },
            "required": ["device_ip"],
            "additionalProperties": False,
        },
    },
]

# ── Resource Schemas ──

OTA_RESOURCE_SCHEMAS = [
    {
        "uri": "ota://server-status",
        "name": "OTA Server Status",
        "description": "OTA server running state, address, and connected device count",
        "mimeType": "application/json",
    },
    {
        "uri": "ota://firmware-list",
        "name": "OTA Firmware List",
        "description": "All firmware in the repository with versions and metadata",
        "mimeType": "application/json",
    },
    {
        "uri": "ota://device-registry",
        "name": "OTA Device Registry",
        "description": "Registered devices with their status and current versions",
        "mimeType": "application/json",
    },
]
