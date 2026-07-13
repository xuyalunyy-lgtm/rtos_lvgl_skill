"""MQTT client bridge — paho-mqtt wrapper with thread-safe ring buffer.

Provides a clean async-safe interface for MQTT publish/subscribe/message-history.
Used by mqtt_server.py as the MCP tool backend.

Usage:
    from mqtt_client import MqttBridge
    bridge = MqttBridge()
    bridge.connect("localhost", 1883)
    bridge.subscribe("sensor/#")
    messages = bridge.get_messages(topic="sensor/temperature", limit=10)
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# ── Configuration ──

DEFAULT_MAX_MESSAGES = 1000
DEFAULT_KEEPALIVE = 60
DEFAULT_TIMEOUT = 30
MAX_PAYLOAD_BYTES = 64 * 1024  # 64KB

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("MQTT_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]


class MqttBridge:
    """Thread-safe MQTT client with ring buffer message history."""

    def __init__(self, max_messages: int = DEFAULT_MAX_MESSAGES):
        self._client: mqtt.Client | None = None
        self._messages: list[dict[str, Any]] = []
        self._max_messages = max_messages
        self._subscriptions: dict[str, int] = {}
        self._lock = threading.Lock()
        self._connected = False
        self._broker_host: str = ""
        self._broker_port: int = 0
        self._client_id: str = ""
        self._connect_time: float = 0
        self._reconnect_delay: float = 1.0
        self._max_reconnect_delay: float = 60.0

    # ── Connection ──

    def connect(
        self,
        host: str,
        port: int = 1883,
        client_id: str | None = None,
        username: str | None = None,
        password: str | None = None,
        tls: bool = False,
        keepalive: int = DEFAULT_KEEPALIVE,
    ) -> dict[str, Any]:
        """Connect to MQTT broker.

        Returns:
            {"ok": bool, "client_id": str, "broker": str, "error": str|None}
        """
        # Validate host against allowlist
        if not self._is_host_allowed(host):
            return {"ok": False, "error": f"Host '{host}' not in allowed hosts: {ALLOWED_HOSTS}"}

        # Disconnect existing connection if any
        if self._connected:
            self.disconnect()

        try:
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id or "",
                protocol=mqtt.MQTTv311,
            )

            if username:
                self._client.username_pw_set(username, password)

            if tls:
                self._client.tls_set()

            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            self._client.connect(host, port, keepalive)
            self._client.loop_start()

            # Wait for connection with timeout
            deadline = time.time() + DEFAULT_TIMEOUT
            while time.time() < deadline and not self._connected:
                time.sleep(0.1)

            if not self._connected:
                self._client.loop_stop()
                return {"ok": False, "error": f"Connection timeout after {DEFAULT_TIMEOUT}s"}

            self._broker_host = host
            self._broker_port = port
            self._client_id = self._client._client_id.decode() if self._client._client_id else ""
            self._connect_time = time.time()
            self._reconnect_delay = 1.0

            return {
                "ok": True,
                "client_id": self._client_id,
                "broker": f"{host}:{port}",
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def disconnect(self) -> dict[str, Any]:
        """Disconnect from MQTT broker."""
        if not self._client or not self._connected:
            return {"ok": True, "message": "Not connected"}

        try:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            return {"ok": True, "message": "Disconnected"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Publish / Subscribe ──

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> dict[str, Any]:
        """Publish a message to a topic.

        Returns:
            {"ok": bool, "topic": str, "payload_size": int, "error": str|None}
        """
        if not self._connected:
            return {"ok": False, "error": "Not connected"}

        # Truncate oversized payloads
        truncated = False
        if len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            payload = payload.encode("utf-8")[:MAX_PAYLOAD_BYTES].decode("utf-8", errors="ignore")
            truncated = True

        try:
            result = self._client.publish(topic, payload, qos=qos, retain=retain)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                return {"ok": False, "error": f"Publish failed: rc={result.rc}"}

            return {
                "ok": True,
                "topic": topic,
                "payload_size": len(payload),
                "truncated": truncated,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def subscribe(self, topic: str, qos: int = 0) -> dict[str, Any]:
        """Subscribe to a topic (supports wildcards +/#).

        Returns:
            {"ok": bool, "topic": str, "qos": int, "error": str|None}
        """
        if not self._connected:
            return {"ok": False, "error": "Not connected"}

        try:
            result = self._client.subscribe(topic, qos=qos)
            if result[0] != mqtt.MQTT_ERR_SUCCESS:
                return {"ok": False, "error": f"Subscribe failed: rc={result[0]}"}

            with self._lock:
                self._subscriptions[topic] = qos

            return {"ok": True, "topic": topic, "qos": qos}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def unsubscribe(self, topic: str) -> dict[str, Any]:
        """Unsubscribe from a topic.

        Returns:
            {"ok": bool, "topic": str, "error": str|None}
        """
        if not self._connected:
            return {"ok": False, "error": "Not connected"}

        try:
            result = self._client.unsubscribe(topic)
            if result[0] != mqtt.MQTT_ERR_SUCCESS:
                return {"ok": False, "error": f"Unsubscribe failed: rc={result[0]}"}

            with self._lock:
                self._subscriptions.pop(topic, None)

            return {"ok": True, "topic": topic}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Message History ──

    def get_messages(
        self,
        topic: str | None = None,
        limit: int = 100,
        since: float | None = None,
    ) -> list[dict[str, Any]]:
        """Read message history from ring buffer.

        Args:
            topic: Filter by topic (optional, supports prefix match)
            limit: Max messages to return
            since: Unix timestamp filter (only messages after this time)

        Returns:
            List of {topic, payload, timestamp, qos, retain}
        """
        with self._lock:
            messages = list(self._messages)

        # Filter by topic prefix
        if topic:
            messages = [m for m in messages if m["topic"].startswith(topic.rstrip("#"))]

        # Filter by timestamp
        if since:
            messages = [m for m in messages if m["timestamp"] >= since]

        # Apply limit (most recent first)
        return messages[-limit:]

    def clear_messages(self, topic: str | None = None) -> dict[str, Any]:
        """Clear message history.

        Args:
            topic: Clear only messages matching this topic prefix (None = all)

        Returns:
            {"ok": bool, "cleared": int}
        """
        with self._lock:
            if topic is None:
                cleared = len(self._messages)
                self._messages.clear()
            else:
                before = len(self._messages)
                prefix = topic.rstrip("#")
                self._messages = [m for m in self._messages if not m["topic"].startswith(prefix)]
                cleared = before - len(self._messages)

        return {"ok": True, "cleared": cleared}

    # ── Status ──

    @property
    def status(self) -> dict[str, Any]:
        """Connection status."""
        with self._lock:
            subs = dict(self._subscriptions)
        return {
            "connected": self._connected,
            "broker": f"{self._broker_host}:{self._broker_port}" if self._connected else None,
            "client_id": self._client_id,
            "subscriptions": subs,
            "message_count": len(self._messages),
            "uptime_seconds": round(time.time() - self._connect_time, 1) if self._connected else 0,
        }

    @property
    def subscribed_topics(self) -> list[dict[str, Any]]:
        """List subscribed topics."""
        with self._lock:
            return [{"topic": t, "qos": q} for t, q in self._subscriptions.items()]

    # ── Internal ──

    def _is_host_allowed(self, host: str) -> bool:
        """Check if host is in allowlist."""
        # Always allow localhost variants
        if host in ("localhost", "127.0.0.1", "::1"):
            return True
        return host in ALLOWED_HOSTS

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when connected."""
        if rc == 0:
            self._connected = True
            logger.info("MQTT connected to %s:%d", self._broker_host, self._broker_port)
        else:
            logger.error("MQTT connect failed: rc=%d", rc)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Callback when disconnected."""
        self._connected = False
        if rc != 0:
            logger.warning("MQTT unexpected disconnect: rc=%d, will reconnect", rc)

    def _on_message(self, client, userdata, msg):
        """Callback when message received."""
        try:
            payload = msg.payload.decode("utf-8", errors="replace")
        except Exception:
            payload = repr(msg.payload)

        entry = {
            "topic": msg.topic,
            "payload": payload,
            "timestamp": time.time(),
            "qos": msg.qos,
            "retain": msg.retain,
        }

        with self._lock:
            self._messages.append(entry)
            # Ring buffer: drop oldest when full
            while len(self._messages) > self._max_messages:
                self._messages.pop(0)

    def shutdown(self):
        """Clean shutdown."""
        self.disconnect()


# ── Module-level singleton for MCP server ──

_bridge: MqttBridge | None = None


def get_bridge(max_messages: int = DEFAULT_MAX_MESSAGES) -> MqttBridge:
    """Get or create the module-level MqttBridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = MqttBridge(max_messages)
    return _bridge
