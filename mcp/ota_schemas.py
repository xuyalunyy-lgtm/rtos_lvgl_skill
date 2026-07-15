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
                "signature_path": {
                    "type": "string",
                    "description": "Detached Ed25519 signature file. Required with key_id for distributable firmware.",
                },
                "key_id": {
                    "type": "string",
                    "description": "Trusted public-key ID from ota_trusted_keys.json. Required with signature_path.",
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
        "name": "ota_verify_signature",
        "description": "Verify stored firmware SHA-256 and its detached Ed25519 signature against a trusted public key.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string"},
                "version": {"type": "string"},
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
        "name": "ota_prepare_ab_switch",
        "description": "Validate signed firmware and schedule the device's inactive A/B slot for the next boot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_ip": {"type": "string"},
                "platform": {"type": "string"},
                "version": {"type": "string"},
                "target_partition": {"type": "string", "enum": ["A", "B"]},
            },
            "required": ["device_ip", "platform", "version"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_report_boot_result",
        "description": "Record device boot outcome; a failed pending-slot boot becomes a rollback while the known-good slot remains active.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_ip": {"type": "string"},
                "partition": {"type": "string", "enum": ["A", "B"]},
                "success": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["device_ip", "partition", "success"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_validate_ab_state",
        "description": "Validate A/B control-plane invariants for a registered device.",
        "inputSchema": {
            "type": "object",
            "properties": {"device_ip": {"type": "string"}},
            "required": ["device_ip"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ota_test_rollback",
        "description": "Dry-run a pending partition boot failure and prove the active partition is preserved; registry state is restored afterwards.",
        "inputSchema": {
            "type": "object",
            "properties": {"device_ip": {"type": "string"}},
            "required": ["device_ip"],
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
