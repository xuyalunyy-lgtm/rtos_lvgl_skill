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
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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

        # Watch state
        self._watch_active = False
        self._watch_thread: threading.Thread | None = None
        self._watch_alerts: deque[dict[str, Any]] = deque(maxlen=200)
        self._watch_lock = threading.Lock()
        self._watch_max_alerts: int = 50
        self._watch_start_ts: float = 0
        self._watch_lines_scanned: int = 0

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
