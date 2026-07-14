"""Serial client bridge — pyserial wrapper with thread-safe ring buffer.

Provides a clean interface for serial port read/write with local log storage.
Used by serial_server.py as the MCP tool backend.

Design principle: store everything locally, AI pulls on demand (no token waste).

Usage:
    from serial_client import SerialBridge
    bridge = SerialBridge()
    bridge.connect("COM3", 115200)
    bridge.write("AT\r\n")
    lines = bridge.get_lines(n=50)
    results = bridge.search("ERROR", n=20)
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ──

DEFAULT_MAX_LINES = 50000
DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 1.0  # serial read timeout in seconds

ALLOWED_PORTS = [
    p.strip()
    for p in os.environ.get("SERIAL_ALLOWED_PORTS", "*").split(",")
    if p.strip()
]


class SerialBridge:
    """Thread-safe serial port client with ring buffer log storage."""

    def __init__(self, max_lines: int = DEFAULT_MAX_LINES):
        self._serial = None
        self._port: str = ""
        self._baudrate: int = 0
        self._connected = False
        self._buffer: deque[dict[str, Any]] = deque(maxlen=max_lines)
        self._max_lines = max_lines
        self._lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connect_time: float = 0
        self._rx_count: int = 0
        self._tx_count: int = 0

    # ── Port Discovery ──

    @staticmethod
    def list_ports() -> list[dict[str, Any]]:
        """List available serial ports.

        Returns:
            List of {port, description, hwid}
        """
        try:
            from serial.tools import list_ports as lp
            ports = []
            for p in lp.comports():
                ports.append({
                    "port": p.device,
                    "description": p.description,
                    "hwid": p.hwid,
                })
            return ports
        except ImportError:
            return []

    # ── Connection ──

    def connect(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: float = 1,
    ) -> dict[str, Any]:
        """Connect to a serial port.

        Args:
            port: Serial port name (e.g., COM3, /dev/ttyUSB0)
            baudrate: Baud rate (default 115200)
            bytesize: Data bits (5, 6, 7, 8)
            parity: Parity (N, E, O, M, S)
            stopbits: Stop bits (1, 1.5, 2)

        Returns:
            {"ok": bool, "port": str, "baudrate": int, "error": str|None}
        """
        if not self._is_port_allowed(port):
            return {"ok": False, "error": f"Port '{port}' not in allowed list: {ALLOWED_PORTS}"}

        # Disconnect if already connected
        if self._connected:
            self.disconnect()

        try:
            import serial as ser

            parity_map = {"N": ser.PARITY_NONE, "E": ser.PARITY_EVEN, "O": ser.PARITY_ODD,
                          "M": ser.PARITY_MARK, "S": ser.PARITY_SPACE}
            stopbits_map = {1: ser.STOPBITS_ONE, 1.5: ser.STOPBITS_ONE_POINT_FIVE, 2: ser.STOPBITS_TWO}

            self._serial = ser.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity_map.get(parity.upper(), ser.PARITY_NONE),
                stopbits=stopbits_map.get(stopbits, ser.STOPBITS_ONE),
                timeout=DEFAULT_TIMEOUT,
            )

            self._port = port
            self._baudrate = baudrate
            self._connected = True
            self._connect_time = time.time()
            self._rx_count = 0
            self._tx_count = 0

            # Start background reader thread
            self._stop_event.clear()
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

            return {
                "ok": True,
                "port": port,
                "baudrate": baudrate,
                "bytesize": bytesize,
                "parity": parity,
                "stopbits": stopbits,
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def disconnect(self) -> dict[str, Any]:
        """Disconnect from serial port."""
        if not self._connected:
            return {"ok": True, "message": "Not connected"}

        try:
            self._stop_event.set()
            if self._reader_thread and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=2)
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._connected = False
            self._serial = None
            return {"ok": True, "message": f"Disconnected from {self._port}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Read / Write ──

    def write(self, data: str, newline: str = "") -> dict[str, Any]:
        """Send data to serial port.

        Args:
            data: Data to send
            newline: Newline suffix (e.g., "\\r\\n", "\\n", "" for none)

        Returns:
            {"ok": bool, "bytes_sent": int, "error": str|None}
        """
        if not self._connected or not self._serial:
            return {"ok": False, "error": "Not connected"}

        try:
            payload = data + newline
            payload_bytes = payload.encode("utf-8")
            self._serial.write(payload_bytes)
            self._serial.flush()
            self._tx_count += 1

            # Record TX in buffer
            with self._lock:
                self._buffer.append({
                    "ts": time.time(),
                    "raw": payload,
                    "direction": "tx",
                })

            return {"ok": True, "bytes_sent": len(payload_bytes)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_lines(self, n: int = 100, direction: str | None = None) -> list[dict[str, Any]]:
        """Read lines from local ring buffer.

        Args:
            n: Number of lines to return (most recent)
            direction: Filter by 'rx', 'tx', or None for both

        Returns:
            List of {ts, raw, direction}
        """
        with self._lock:
            lines = list(self._buffer)

        if direction:
            lines = [l for l in lines if l["direction"] == direction]

        return lines[-n:]

    def search(self, keyword: str, n: int = 50) -> list[dict[str, Any]]:
        """Search ring buffer for keyword.

        Args:
            keyword: Search string (case-sensitive substring match)
            n: Max results (most recent)

        Returns:
            List of matching {ts, raw, direction}
        """
        with self._lock:
            lines = list(self._buffer)

        matched = [l for l in lines if keyword in l["raw"]]
        return matched[-n:]

    # ── Status ──

    @property
    def status(self) -> dict[str, Any]:
        """Connection status."""
        with self._lock:
            buf_size = len(self._buffer)
        return {
            "connected": self._connected,
            "port": self._port if self._connected else None,
            "baudrate": self._baudrate if self._connected else None,
            "buffer_size": buf_size,
            "max_lines": self._max_lines,
            "rx_count": self._rx_count,
            "tx_count": self._tx_count,
            "uptime_seconds": round(time.time() - self._connect_time, 1) if self._connected else 0,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get buffer statistics."""
        with self._lock:
            lines = list(self._buffer)

        if not lines:
            return {
                "total_lines": 0,
                "rx_lines": 0,
                "tx_lines": 0,
                "first_ts": None,
                "last_ts": None,
                "duration_sec": 0,
            }

        rx = sum(1 for l in lines if l["direction"] == "rx")
        tx = sum(1 for l in lines if l["direction"] == "tx")

        return {
            "total_lines": len(lines),
            "rx_lines": rx,
            "tx_lines": tx,
            "first_ts": lines[0]["ts"],
            "last_ts": lines[-1]["ts"],
            "duration_sec": round(lines[-1]["ts"] - lines[0]["ts"], 1),
            "buffer_max": self._max_lines,
        }

    # ── Internal ──

    def _is_port_allowed(self, port: str) -> bool:
        """Check if port is in allowlist."""
        if "*" in ALLOWED_PORTS:
            return True
        return port in ALLOWED_PORTS

    def _read_loop(self):
        """Background thread: continuously read serial data into buffer."""
        while not self._stop_event.is_set():
            try:
                if not self._serial or not self._serial.is_open:
                    break
                data = self._serial.readline()
                if data:
                    line = data.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        with self._lock:
                            self._buffer.append({
                                "ts": time.time(),
                                "raw": line,
                                "direction": "rx",
                            })
                        self._rx_count += 1
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.warning("Serial read error: %s", e)
                break

    def shutdown(self):
        """Clean shutdown."""
        self.disconnect()


# ── Module-level singleton for MCP server ──

_bridge: SerialBridge | None = None


def get_bridge(max_lines: int = DEFAULT_MAX_LINES) -> SerialBridge:
    """Get or create the module-level SerialBridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = SerialBridge(max_lines)
    return _bridge
