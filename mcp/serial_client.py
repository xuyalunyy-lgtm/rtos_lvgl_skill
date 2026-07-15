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

import json
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Log configuration ──

DEFAULT_LOG_MAX_SIZE = int(os.environ.get("SERIAL_LOG_MAX_SIZE", 5 * 1024 * 1024))  # 5 MB
DEFAULT_LOG_MAX_FILES = int(os.environ.get("SERIAL_LOG_MAX_FILES", 10))


def _configured_redact_patterns() -> list[re.Pattern]:
    """Load redaction patterns from SERIAL_REDACT_PATTERNS env var."""
    raw = os.environ.get("SERIAL_REDACT_PATTERNS", "").strip()
    if not raw:
        # Default redaction: Wi-Fi passwords, common token formats
        defaults = [
            r"(?i)(?:password|passwd|pwd)\s*[=:]\s*\S+",
            r"(?i)(?:token|secret|api[_-]?key)\s*[=:]\s*\S+",
            r"(?i)(?:ssid)\s*[=:]\s*\S+",
            r"(?i)CWJAP\s*=\s*\"[^\"]*\",\"[^\"]*\"",  # AT+CWJAP="ssid","password"
        ]
        patterns = []
        for d in defaults:
            try:
                patterns.append(re.compile(d))
            except re.error:
                pass
        return patterns
    patterns = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                patterns.append(re.compile(part))
            except re.error:
                logger.warning("Invalid redact pattern ignored: %s", part)
    return patterns


REDACT_PATTERNS = _configured_redact_patterns()


def _apply_redaction(text: str) -> str:
    """Apply redaction patterns to text, replacing matches with [REDACTED]."""
    for pattern in REDACT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class RotatingLogWriter:
    """Size-based rotating log writer with metadata headers and bookmarks."""

    def __init__(
        self,
        directory: Path,
        port: str,
        *,
        max_size: int = DEFAULT_LOG_MAX_SIZE,
        max_files: int = DEFAULT_LOG_MAX_FILES,
    ):
        self._dir = directory
        self._port = port
        self._max_size = max_size
        self._max_files = max_files
        self._current_file: Path | None = None
        self._stream = None
        self._bytes_written = 0
        self._file_index = 0
        self._session_start = datetime.now(timezone.utc)
        self._metadata: dict[str, Any] = {}
        self._lock = threading.Lock()

    def open(self, metadata: dict[str, Any] | None = None) -> Path:
        """Open the first log file and write session metadata header."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self._metadata = metadata or {}
        self._file_index = 0
        return self._rotate()

    def write(self, direction: str, raw: str) -> None:
        """Write a log line with redaction and rotation."""
        with self._lock:
            if self._stream is None:
                return
            redacted = _apply_redaction(raw)
            timestamp = datetime.now(timezone.utc).isoformat()
            line = f"{timestamp} [{direction.upper()}] {redacted}\n"
            encoded = line.encode("utf-8")

            # Rotate if this write would exceed the limit
            if self._bytes_written + len(encoded) > self._max_size:
                self._rotate()
                # Re-encode after rotation
                encoded = line.encode("utf-8")

            self._stream.write(encoded)
            self._stream.flush()
            self._bytes_written += len(encoded)

    def bookmark(self, label: str) -> None:
        """Write a bookmark marker to the log."""
        with self._lock:
            if self._stream is None:
                return
            ts = datetime.now(timezone.utc).isoformat()
            line = f"\n--- BOOKMARK [{ts}]: {label} ---\n\n"
            encoded = line.encode("utf-8")
            self._stream.write(encoded)
            self._stream.flush()
            self._bytes_written += len(encoded)

    def close(self) -> None:
        """Close the current log stream."""
        with self._lock:
            if self._stream is not None:
                self._stream.close()
                self._stream = None

    @property
    def current_path(self) -> Path | None:
        return self._current_file

    def _rotate(self) -> Path:
        """Rotate to a new log file. Must be called with lock held."""
        if self._stream is not None:
            self._stream.close()

        safe_port = re.sub(r"[^A-Za-z0-9_.-]+", "_", self._port).strip("._") or "serial"
        ts = self._session_start.strftime("%Y%m%dT%H%M%S")

        if self._file_index == 0:
            filename = f"{safe_port}_{ts}.log"
        else:
            filename = f"{safe_port}_{ts}.{self._file_index}.log"

        self._current_file = self._dir / filename
        self._stream = self._current_file.open("wb")
        self._bytes_written = 0
        self._file_index += 1

        # Write metadata header
        self._write_header()

        # Enforce max_files: clean up old logs if needed
        self._cleanup_old_files()

        return self._current_file

    def _write_header(self) -> None:
        """Write session metadata header to the current log stream."""
        if self._stream is None:
            return
        header_lines = [
            f"# session_start: {self._session_start.isoformat()}",
            f"# port: {self._port}",
        ]
        for key, value in self._metadata.items():
            header_lines.append(f"# {key}: {value}")
        header_lines.append("")
        header = "\n".join(header_lines) + "\n"
        encoded = header.encode("utf-8")
        self._stream.write(encoded)
        self._bytes_written += len(encoded)

    def _cleanup_old_files(self) -> None:
        """Remove oldest log files if exceeding max_files."""
        safe_port = re.sub(r"[^A-Za-z0-9_.-]+", "_", self._port).strip("._") or "serial"
        pattern = f"{safe_port}_*.log"
        existing = sorted(self._dir.glob(pattern), key=lambda f: f.stat().st_mtime)
        while len(existing) > self._max_files:
            oldest = existing.pop(0)
            try:
                oldest.unlink()
            except OSError:
                pass

# ── Symptom routes for intelligent watch ──

ROOT = Path(__file__).resolve().parent.parent
ROUTES_FILE = ROOT / "references" / "log_symptom_routes.json"


def _load_symptom_routes() -> list[dict]:
    """Load symptom routes for log analysis."""
    if ROUTES_FILE.exists():
        try:
            return json.loads(ROUTES_FILE.read_text(encoding="utf-8")).get("symptoms", [])
        except (json.JSONDecodeError, OSError):
            return []
    return []


# Pre-compiled patterns for fast matching (loaded once at import)
_SYMPTOM_ROUTES = _load_symptom_routes()
_COMPILED_ROUTES: list[dict] = []
for _s in _SYMPTOM_ROUTES:
    compiled_patterns = []
    for p in _s.get("patterns", []):
        try:
            compiled_patterns.append(re.compile(p, re.IGNORECASE))
        except re.error:
            pass
    natural_patterns = [np.lower() for np in _s.get("natural_patterns", [])]
    weak_patterns = [wp.lower() for wp in _s.get("weak_patterns", [])]
    _COMPILED_ROUTES.append({
        "id": _s["id"],
        "name": _s.get("name", ""),
        "compiled_patterns": compiled_patterns,
        "natural_patterns": natural_patterns,
        "weak_patterns": weak_patterns,
        "constraints": _s.get("constraints", []),
        "root_cause_hints": _s.get("root_cause_hints", [])[:2],
        "severity": _s.get("severity", "medium"),
    })

# Fast keyword index for O(1) pre-filter
_KEYWORD_INDEX: dict[str, list[int]] = {}
for _idx, _route in enumerate(_COMPILED_ROUTES):
    for kw in _route["natural_patterns"] + _route["weak_patterns"]:
        for token in kw.split():
            token = token.lower()
            if token not in _KEYWORD_INDEX:
                _KEYWORD_INDEX[token] = []
            if _idx not in _KEYWORD_INDEX[token]:
                _KEYWORD_INDEX[token].append(_idx)


def match_symptoms_fast(line: str) -> list[dict]:
    """Fast symptom matching for a single log line. Uses keyword index for O(1) pre-filter."""
    line_lower = line.lower()
    candidate_indices: set[int] = set()

    # Keyword pre-filter: check if any keyword token appears in the line
    for token in line_lower.split():
        if token in _KEYWORD_INDEX:
            candidate_indices.update(_KEYWORD_INDEX[token])

    # Also check full line for pattern matches
    matches = []
    for idx in candidate_indices:
        route = _COMPILED_ROUTES[idx]
        score = 0
        matched = []

        for pattern in route["compiled_patterns"]:
            if pattern.search(line):
                score += 2
                matched.append(pattern.pattern)

        for np in route["natural_patterns"]:
            if np in line_lower:
                score += 3
                matched.append(np)

        for wp in route["weak_patterns"]:
            if wp in line_lower:
                score += 1
                matched.append(wp)

        if score > 0:
            matches.append({
                "id": route["id"],
                "name": route["name"],
                "score": score,
                "severity": route["severity"],
                "constraints": route["constraints"],
                "root_cause_hints": route["root_cause_hints"],
                "matched": matched[:3],
            })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:3]


# Log level / error pattern detection
_ERROR_PATTERNS = [
    (re.compile(r"\b(?:panic|abort|fatal|assert\s*fail)", re.IGNORECASE), "critical"),
    (re.compile(r"\b(?:Guru Meditation|HardFault|WDT|watchdog|stack overflow)", re.IGNORECASE), "critical"),
    (re.compile(r"\b(?:ERROR|ERR|FAIL|FAILED)\b"), "error"),
    (re.compile(r"\b(?:WARN|WARNING)\b"), "warning"),
    (re.compile(r"rst:0x|boot:0x|EXC_RETURN|pc=0x"), "boot"),
    (re.compile(r"heap_caps.*(?:leak|fragment|exhaust)", re.IGNORECASE), "memory"),
]

# Boot sequence markers
_BOOT_MARKERS = [
    re.compile(r"rst:0x", re.IGNORECASE),
    re.compile(r"boot:", re.IGNORECASE),
    re.compile(r"ets_\w+", re.IGNORECASE),
    re.compile(r"entry 0x", re.IGNORECASE),
]


def classify_line(line: str) -> dict:
    """Classify a single log line: level, category, severity."""
    result = {"level": "", "category": "", "severity": "info"}

    # ESP-IDF log level prefix: D/I/W/E/F (timestamp)
    lv_m = re.match(r"^([DIWEF])\s*\(", line)
    if lv_m:
        result["level"] = lv_m.group(1)

    for pattern, category in _ERROR_PATTERNS:
        if pattern.search(line):
            result["category"] = category
            if category == "critical":
                result["severity"] = "critical"
            elif category == "error" and result["severity"] != "critical":
                result["severity"] = "error"
            elif category == "warning" and result["severity"] in ("info", ""):
                result["severity"] = "warning"
            break

    return result

# ── Configuration ──

DEFAULT_MAX_LINES = 50000
DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 1.0  # serial read timeout in seconds

def _configured_ports() -> tuple[str, ...]:
    """Return the explicit serial-port allowlist, defaulting to deny all."""
    ports = tuple(
        p.strip()
        for p in os.environ.get("SERIAL_ALLOWED_PORTS", "").split(",")
        if p.strip()
    )
    if "*" in ports:
        logger.warning("SERIAL_ALLOWED_PORTS='*' is ignored; configure explicit ports instead")
        return ()
    return ports


def _configured_log_dir() -> Path | None:
    """Resolve the optional log directory relative to the skill root."""
    value = os.environ.get("SERIAL_LOG_DIR", "").strip()
    if not value:
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve()


ALLOWED_PORTS = _configured_ports()
DEFAULT_LOG_DIR = _configured_log_dir()


class SerialBridge:
    """Thread-safe serial port client with ring buffer log storage."""

    def __init__(
        self,
        max_lines: int = DEFAULT_MAX_LINES,
        *,
        allowed_ports: tuple[str, ...] | None = None,
        log_dir: Path | None = None,
    ):
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
        self._allowed_ports = ALLOWED_PORTS if allowed_ports is None else tuple(allowed_ports)
        self._log_dir = DEFAULT_LOG_DIR if log_dir is None else Path(log_dir).resolve()
        self._log_path: Path | None = None
        self._log_writer: RotatingLogWriter | None = None

        # Watch state
        self._watch_active = False
        self._watch_thread: threading.Thread | None = None
        self._watch_alerts: deque[dict[str, Any]] = deque(maxlen=200)
        self._watch_lock = threading.Lock()
        self._watch_max_alerts: int = 50
        self._watch_start_ts: float = 0
        self._watch_lines_scanned: int = 0

        # Device identity (populated on connect)
        self._device_identity: dict[str, Any] = {}

    # ── Port Discovery ──

    @staticmethod
    def list_ports() -> list[dict[str, Any]]:
        """List available serial ports with USB identity.

        Returns:
            List of {port, description, hwid, vid, pid, serial_number, manufacturer, product}
        """
        try:
            from serial.tools import list_ports as lp
            ports = []
            for p in lp.comports():
                info: dict[str, Any] = {
                    "port": p.device,
                    "description": p.description,
                    "hwid": p.hwid,
                }
                # Extract USB identity if available (platform-dependent)
                if hasattr(p, "vid") and p.vid is not None:
                    info["vid"] = f"0x{p.vid:04x}"
                if hasattr(p, "pid") and p.pid is not None:
                    info["pid"] = f"0x{p.pid:04x}"
                if hasattr(p, "serial_number") and p.serial_number:
                    info["serial_number"] = p.serial_number
                if hasattr(p, "manufacturer") and p.manufacturer:
                    info["manufacturer"] = p.manufacturer
                if hasattr(p, "product") and p.product:
                    info["product"] = p.product
                ports.append(info)
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
            allowed = ", ".join(self._allowed_ports) or "(none)"
            return {
                "ok": False,
                "error": (
                    f"Port '{port}' is not explicitly allowed. "
                    f"Set SERIAL_ALLOWED_PORTS to the intended port; configured: {allowed}"
                ),
            }

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
            self._device_identity = self._probe_device_identity(port)
            self._open_log_file(port)

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
                "log_path": str(self._log_path) if self._log_path else None,
            }

        except Exception as e:
            self._close_log_file()
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._serial = None
            self._connected = False
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
            self._close_log_file()
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

            self._record_line(payload, "tx")

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
        result: dict[str, Any] = {
            "connected": self._connected,
            "port": self._port if self._connected else None,
            "baudrate": self._baudrate if self._connected else None,
            "buffer_size": buf_size,
            "max_lines": self._max_lines,
            "rx_count": self._rx_count,
            "tx_count": self._tx_count,
            "uptime_seconds": round(time.time() - self._connect_time, 1) if self._connected else 0,
            "log_enabled": self._log_dir is not None,
            "log_path": str(self._log_path) if self._log_path else None,
            "log_rotating": self._log_writer is not None,
        }
        if self._connected and self._device_identity:
            result["device"] = self._device_identity
        return result

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
        """Check if port is in allowlist. Supports port name, vid:pid, or serial:XXXX."""
        if not self._allowed_ports:
            return False
        for entry in self._allowed_ports:
            if entry == port:
                return True
            # Identity-based matching: probe the port and compare
            if entry.startswith("vid:") or entry.startswith("serial:"):
                identity = self._probe_device_identity(port)
                if self._allowlist_entry_matches(entry, identity):
                    return True
        return False

    @staticmethod
    def _normalize_hex(value: str) -> str:
        """Normalize hex value: strip 0x prefix, lowercase."""
        v = value.strip().lower()
        if v.startswith("0x"):
            v = v[2:]
        return v

    @classmethod
    def _allowlist_entry_matches(cls, entry: str, identity: dict[str, Any]) -> bool:
        """Check if an allowlist entry matches a device identity.

        Supports formats:
            vid:XXXX pid:YYYY  — match USB VID and PID
            serial:XXXX        — match serial number
        """
        if entry.startswith("serial:"):
            target_serial = entry.split(":", 1)[1].strip()
            return identity.get("serial_number") == target_serial
        if entry.startswith("vid:"):
            parts = entry.split()
            target_vid = parts[0].split(":", 1)[1].strip()
            target_pid = ""
            if len(parts) > 1 and parts[1].startswith("pid:"):
                target_pid = parts[1].split(":", 1)[1].strip()
            if cls._normalize_hex(target_vid) != cls._normalize_hex(identity.get("vid", "")):
                return False
            if target_pid and cls._normalize_hex(target_pid) != cls._normalize_hex(identity.get("pid", "")):
                return False
            return bool(target_vid)
        return False

    @staticmethod
    def _probe_device_identity(port: str) -> dict[str, Any]:
        """Probe USB device identity for a port."""
        identity: dict[str, Any] = {}
        try:
            from serial.tools import list_ports as lp
            for p in lp.comports():
                if p.device == port:
                    if p.vid is not None:
                        identity["vid"] = f"0x{p.vid:04x}"
                    if p.pid is not None:
                        identity["pid"] = f"0x{p.pid:04x}"
                    if p.serial_number:
                        identity["serial_number"] = p.serial_number
                    if p.manufacturer:
                        identity["manufacturer"] = p.manufacturer
                    if p.product:
                        identity["product"] = p.product
                    break
        except (ImportError, Exception):
            pass
        return identity

    def check_device_present(self) -> dict[str, Any]:
        """Check if the previously connected device is still present.

        Compares stored device identity (VID/PID/serial) against current port list.
        If the same device appears on a different port, reports reconnection.

        Returns:
            {"present": bool, "reconnected": bool, "new_port": str|None, "identity": dict}
        """
        if not self._device_identity:
            return {"present": False, "reconnected": False, "new_port": None, "identity": {}}

        target_vid = self._device_identity.get("vid")
        target_pid = self._device_identity.get("pid")
        target_serial = self._device_identity.get("serial_number")

        current_ports = self.list_ports()

        # Look for exact match on same port
        for p in current_ports:
            if p["port"] == self._port:
                if self._identity_matches(p):
                    return {
                        "present": True,
                        "reconnected": False,
                        "new_port": None,
                        "identity": self._device_identity,
                    }

        # Device not on original port — check if it reappeared elsewhere
        for p in current_ports:
            if self._identity_matches(p):
                return {
                    "present": True,
                    "reconnected": True,
                    "new_port": p["port"],
                    "identity": self._device_identity,
                }

        return {
            "present": False,
            "reconnected": False,
            "new_port": None,
            "identity": self._device_identity,
        }

    def _identity_matches(self, port_info: dict[str, Any]) -> bool:
        """Check if a port's USB identity matches the stored device identity."""
        target = self._device_identity
        # Match by serial number (most reliable) if available
        if target.get("serial_number") and port_info.get("serial_number"):
            return target["serial_number"] == port_info["serial_number"]
        # Fall back to VID:PID match
        if target.get("vid") and target.get("pid"):
            return target["vid"] == port_info.get("vid") and target["pid"] == port_info.get("pid")
        return False

    def _open_log_file(self, port: str) -> None:
        """Create a rotating session log with metadata header."""
        if self._log_dir is None:
            return
        metadata: dict[str, Any] = {}
        if self._baudrate:
            metadata["baudrate"] = self._baudrate
        if self._device_identity:
            for k, v in self._device_identity.items():
                metadata[f"device_{k}"] = v
        writer = RotatingLogWriter(self._log_dir, port)
        self._log_path = writer.open(metadata=metadata)
        self._log_writer = writer

    def _close_log_file(self) -> None:
        if self._log_writer is not None:
            self._log_writer.close()
        self._log_writer = None

    def _record_line(self, raw: str, direction: str) -> None:
        entry = {"ts": time.time(), "raw": raw, "direction": direction}
        with self._lock:
            self._buffer.append(entry)
        if self._log_writer is not None:
            self._log_writer.write(direction, raw)

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
                        self._record_line(line, "rx")
                        self._rx_count += 1
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.warning("Serial read error: %s", e)
                break

    # ── Intelligent Watch ──

    def start_watch(self, *, platform: str = "esp32", max_alerts: int = 50) -> dict[str, Any]:
        """Start background symptom watch. Monitors new lines and generates alerts."""
        if not self._connected:
            return {"ok": False, "error": "Not connected"}

        if self._watch_active:
            return {"ok": True, "message": "Watch already active", "alerts_count": len(self._watch_alerts)}

        self._watch_active = True
        self._watch_alerts.clear()
        self._watch_max_alerts = max_alerts
        self._watch_start_ts = time.time()
        self._watch_lines_scanned = 0

        self._watch_thread = threading.Thread(
            target=self._watch_loop, daemon=True,
            kwargs={"platform": platform},
        )
        self._watch_thread.start()

        return {"ok": True, "message": "Watch started", "platform": platform}

    def stop_watch(self) -> dict[str, Any]:
        """Stop background symptom watch."""
        if not self._watch_active:
            return {"ok": True, "message": "Watch not active"}

        self._watch_active = False
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=3)

        return {
            "ok": True,
            "message": "Watch stopped",
            "alerts_count": len(self._watch_alerts),
            "lines_scanned": self._watch_lines_scanned,
        }

    def get_watch_alerts(self, n: int = 20, since_ts: float = 0) -> list[dict]:
        """Get recent watch alerts, optionally filtered by timestamp."""
        with self._watch_lock:
            alerts = list(self._watch_alerts)
        if since_ts > 0:
            alerts = [a for a in alerts if a["ts"] > since_ts]
        return alerts[-n:]

    def get_watch_status(self) -> dict[str, Any]:
        """Get watch status."""
        return {
            "active": self._watch_active,
            "alerts_count": len(self._watch_alerts),
            "lines_scanned": self._watch_lines_scanned,
            "uptime_seconds": round(time.time() - self._watch_start_ts, 1) if self._watch_active else 0,
        }

    def summarize_buffer(self, n: int = 500) -> dict[str, Any]:
        """Analyze recent buffer lines and return a summary with detected issues."""
        with self._lock:
            lines = list(self._buffer)[-n:]

        if not lines:
            return {"ok": True, "message": "Buffer empty", "total_lines": 0}

        total = len(lines)
        rx_count = sum(1 for l in lines if l["direction"] == "rx")
        tx_count = total - rx_count

        severity_counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
        symptom_hits: dict[str, dict] = {}
        boot_events = 0
        error_lines: list[dict] = []

        for entry in lines:
            if entry["direction"] != "rx":
                continue
            raw = entry.get("raw", "")

            # Classify line
            cls = classify_line(raw)
            sev = cls["severity"]
            if sev in severity_counts:
                severity_counts[sev] += 1

            # Count boot markers
            for bm in _BOOT_MARKERS:
                if bm.search(raw):
                    boot_events += 1
                    break

            # Symptom matching (only on rx lines with potential issues)
            if sev in ("critical", "error", "warning"):
                symptoms = match_symptoms_fast(raw)
                for s in symptoms:
                    sid = s["id"]
                    if sid not in symptom_hits:
                        symptom_hits[sid] = {
                            "id": sid,
                            "name": s["name"],
                            "severity": s["severity"],
                            "constraints": s["constraints"],
                            "root_cause_hints": s["root_cause_hints"],
                            "count": 0,
                            "first_line": raw[:200],
                        }
                    symptom_hits[sid]["count"] += 1

                if sev in ("critical", "error") and len(error_lines) < 10:
                    error_lines.append({
                        "ts": entry.get("ts", 0),
                        "raw": raw[:200],
                        "severity": sev,
                        "category": cls["category"],
                    })

        # Calculate time span
        first_ts = lines[0].get("ts", 0)
        last_ts = lines[-1].get("ts", 0)
        duration = round(last_ts - first_ts, 1) if last_ts > first_ts else 0

        # Top symptoms by count
        top_symptoms = sorted(symptom_hits.values(), key=lambda x: x["count"], reverse=True)[:5]

        # Overall health assessment
        if severity_counts["critical"] > 0:
            health = "CRITICAL"
        elif severity_counts["error"] > 3:
            health = "DEGRADED"
        elif severity_counts["warning"] > 5:
            health = "WARNING"
        else:
            health = "HEALTHY"

        return {
            "ok": True,
            "total_lines": total,
            "rx_lines": rx_count,
            "tx_lines": tx_count,
            "duration_sec": duration,
            "health": health,
            "severity_counts": severity_counts,
            "boot_events": boot_events,
            "top_symptoms": top_symptoms,
            "error_samples": error_lines,
        }

    def _watch_loop(self, platform: str = "esp32"):
        """Background thread: monitor new lines for symptoms."""
        scan_idx = len(self._buffer)  # Start from current end

        while self._watch_active:
            try:
                # Get new lines since last scan
                with self._lock:
                    current_len = len(self._buffer)
                    if current_len > scan_idx:
                        new_lines = list(self._buffer)[scan_idx:current_len]
                        scan_idx = current_len
                    else:
                        new_lines = []

                for entry in new_lines:
                    if not self._watch_active:
                        break
                    if entry["direction"] != "rx":
                        continue

                    raw = entry.get("raw", "")
                    self._watch_lines_scanned += 1

                    # Classify
                    cls = classify_line(raw)
                    sev = cls["severity"]

                    # Only alert on non-info lines
                    if sev in ("critical", "error", "warning"):
                        symptoms = match_symptoms_fast(raw)

                        alert = {
                            "ts": entry.get("ts", 0),
                            "line": raw[:300],
                            "severity": sev,
                            "category": cls["category"],
                            "symptoms": symptoms,
                        }

                        with self._watch_lock:
                            if len(self._watch_alerts) < self._watch_max_alerts:
                                self._watch_alerts.append(alert)

                # Sleep briefly to avoid busy-waiting
                time.sleep(0.1)

            except Exception as e:
                if self._watch_active:
                    logger.warning("Watch loop error: %s", e)
                time.sleep(0.5)

    # ── Bookmarks & Export ──

    def bookmark(self, label: str) -> dict[str, Any]:
        """Mark a moment in the log with a labeled bookmark.

        Args:
            label: Human-readable bookmark label

        Returns:
            {"ok": bool, "label": str, "timestamp": str}
        """
        if not self._connected:
            return {"ok": False, "error": "Not connected"}
        if not self._log_writer:
            return {"ok": False, "error": "No log file configured"}

        self._log_writer.bookmark(label)
        ts = datetime.now(timezone.utc).isoformat()

        # Also add to ring buffer for search
        with self._lock:
            self._buffer.append({
                "ts": time.time(),
                "raw": f"--- BOOKMARK: {label} ---",
                "direction": "bookmark",
            })

        return {"ok": True, "label": label, "timestamp": ts}

    def export_bundle(
        self,
        *,
        output_dir: Path | None = None,
        context_lines: int = 200,
        include_alerts: bool = True,
    ) -> dict[str, Any]:
        """Export a minimal reproduction bundle for debugging.

        Collects: log snippet, serial config, device identity, watch alerts, summary.

        Args:
            output_dir: Directory to write bundle (defaults to log dir)
            context_lines: Number of recent buffer lines to include
            include_alerts: Whether to include watch alerts

        Returns:
            {"ok": bool, "path": str, "contents": dict}
        """
        out_dir = output_dir or self._log_dir
        if out_dir is None:
            return {"ok": False, "error": "No log directory configured"}

        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

        # Collect data
        with self._lock:
            recent_lines = list(self._buffer)[-context_lines:]

        bundle: dict[str, Any] = {
            "export_time": datetime.now(timezone.utc).isoformat(),
            "config": {
                "port": self._port,
                "baudrate": self._baudrate,
                "max_lines": self._max_lines,
            },
            "device_identity": self._device_identity,
            "status": self.status,
            "recent_lines": [
                {
                    "ts": l.get("ts", 0),
                    "direction": l.get("direction", ""),
                    "raw": _apply_redaction(l.get("raw", "")),
                }
                for l in recent_lines
            ],
        }

        if include_alerts:
            bundle["watch_alerts"] = self.get_watch_alerts(n=50)

        # Write bundle
        bundle_path = out_dir / f"bundle_{ts}.json"
        try:
            bundle_path.write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            return {"ok": True, "path": str(bundle_path), "contents": bundle}
        except OSError as e:
            return {"ok": False, "error": str(e)}

    # ── Request/Response ──

    def request(
        self,
        command: str,
        expect: str,
        timeout: float = 5.0,
        newline: str = "\r\n",
        context_lines: int = 5,
    ) -> dict[str, Any]:
        """Send a command and wait for a matching response.

        Args:
            command: Command string to send
            expect: Regex pattern to match against RX lines
            timeout: Max seconds to wait for match (0.1–30.0)
            newline: Newline suffix appended to command
            context_lines: Number of RX lines before/after match to include

        Returns:
            On match: {"ok": True, "matched_line", "match_groups", "context", "elapsed_ms"}
            On timeout: {"ok": False, "error": "timeout", "recent_rx", "elapsed_ms"}
        """
        # Pre-compile the expect pattern (validate before sending anything)
        try:
            pattern = re.compile(expect)
        except re.error as e:
            return {"ok": False, "error": f"Invalid regex: {e}"}

        if not self._connected or not self._serial:
            return {"ok": False, "error": "Not connected"}

        timeout = max(0.1, min(30.0, timeout))

        # Record current buffer position so we only scan new entries
        with self._lock:
            start_idx = len(self._buffer)

        # Send the command
        write_result = self.write(command, newline=newline)
        if not write_result.get("ok"):
            return {"ok": False, "error": f"Write failed: {write_result.get('error')}"}

        # Poll for matching RX line
        deadline = time.time() + timeout
        matched_entry = None

        while time.time() < deadline:
            with self._lock:
                current_len = len(self._buffer)
                if current_len > start_idx:
                    new_entries = list(self._buffer)[start_idx:current_len]
                    start_idx = current_len
                else:
                    new_entries = []

            for entry in new_entries:
                if entry["direction"] == "rx":
                    if pattern.search(entry["raw"]):
                        matched_entry = entry
                        break

            if matched_entry:
                break

            # Brief sleep to avoid busy-waiting (match reader thread cadence)
            time.sleep(0.02)

        elapsed_ms = round((time.time() - (deadline - timeout)) * 1000)

        if matched_entry:
            # Gather context: RX lines before/after the match in the buffer
            with self._lock:
                all_lines = list(self._buffer)

            rx_lines = [l for l in all_lines if l["direction"] == "rx"]
            match_ts = matched_entry["ts"]

            # Find the match position in the RX-only list
            match_pos = None
            for i, line in enumerate(rx_lines):
                if line["ts"] == match_ts and line["raw"] == matched_entry["raw"]:
                    match_pos = i
                    break

            context = []
            if match_pos is not None:
                ctx_start = max(0, match_pos - context_lines)
                ctx_end = min(len(rx_lines), match_pos + context_lines + 1)
                context = [l["raw"] for l in rx_lines[ctx_start:ctx_end]]

            # Extract regex groups
            m = pattern.search(matched_entry["raw"])
            match_groups = list(m.groups()) if m and m.groups() else []

            return {
                "ok": True,
                "matched_line": matched_entry["raw"],
                "match_groups": match_groups,
                "context": context,
                "elapsed_ms": elapsed_ms,
            }
        else:
            # Timeout — return recent RX lines for diagnostics
            with self._lock:
                recent_rx = [l["raw"] for l in list(self._buffer) if l["direction"] == "rx"][-20:]

            return {
                "ok": False,
                "error": "timeout",
                "timeout_sec": timeout,
                "command_sent": command,
                "recent_rx": recent_rx,
                "elapsed_ms": elapsed_ms,
            }

    def shutdown(self):
        """Clean shutdown."""
        self._watch_active = False
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=2)
        self.disconnect()


# ── Module-level singleton for MCP server ──

_bridge: SerialBridge | None = None


def get_bridge(max_lines: int = DEFAULT_MAX_LINES) -> SerialBridge:
    """Get or create the module-level SerialBridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = SerialBridge(max_lines)
    return _bridge
