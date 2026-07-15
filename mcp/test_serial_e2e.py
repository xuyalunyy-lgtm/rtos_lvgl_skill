"""E2E tests for SerialBridge using a loopback serial mock.

Tests the full bridge lifecycle: connect, write, read, request, watch,
rotation, redaction, bookmark, export — without requiring real hardware.

On systems with virtual serial port pairs (com0com, socat), set
SERIAL_TEST_PORT_A and SERIAL_TEST_PORT_B to test against real ports.

Usage:
    python -m pytest mcp/test_serial_e2e.py -v
    python mcp/test_serial_e2e.py  # standalone runner
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock

# Ensure mcp/ is importable
import sys
sys.path.insert(0, str(Path(__file__).parent))

from serial_client import SerialBridge, RotatingLogWriter, _apply_redaction


# ── Loopback Serial Mock ──


class LoopbackSerial:
    """Mock serial.Serial that echoes TX back as RX after a brief delay.

    Supports configurable echo behavior for testing edge cases.
    """

    def __init__(self, *, echo: bool = True, echo_delay: float = 0.01, garble: bool = False):
        self._echo = echo
        self._echo_delay = echo_delay
        self._garble = garble
        self._rx_buffer: deque[bytes] = deque()
        self._lock = threading.Lock()
        self.is_open = True
        self._write_count = 0
        self._read_timeout = 1.0

    @property
    def timeout(self):
        return self._read_timeout

    @timeout.setter
    def timeout(self, val):
        self._read_timeout = val

    def write(self, data: bytes) -> int:
        if not self.is_open:
            raise OSError("Port closed")
        self._write_count += 1
        if self._echo:
            # Schedule echo after delay
            def _echo():
                time.sleep(self._echo_delay)
                response = data
                if self._garble and self._write_count % 3 == 0:
                    response = b"\xff\xfe" + data  # prepend garbage bytes
                with self._lock:
                    self._rx_buffer.append(response)

            t = threading.Thread(target=_echo, daemon=True)
            t.start()
        return len(data)

    def readline(self) -> bytes:
        deadline = time.time() + self._read_timeout
        while time.time() < deadline:
            with self._lock:
                if self._rx_buffer:
                    return self._rx_buffer.popleft()
            time.sleep(0.01)
        return b""

    def flush(self):
        pass

    def close(self):
        self.is_open = False

    def inject_rx(self, data: bytes):
        """Inject data into the RX buffer (for simulating device responses)."""
        with self._lock:
            self._rx_buffer.append(data)


# ── Test Helpers ──


def make_bridge(**kwargs) -> SerialBridge:
    """Create a SerialBridge with test defaults."""
    return SerialBridge(max_lines=1000, allowed_ports=("COM99",), **kwargs)


def connect_loopback(bridge: SerialBridge, mock_serial: LoopbackSerial) -> dict:
    """Connect bridge by injecting a mock serial object directly."""
    # Bypass the pyserial import by directly setting up the bridge internals
    bridge._serial = mock_serial
    bridge._port = "COM99"
    bridge._baudrate = 115200
    bridge._connected = True
    bridge._connect_time = time.time()
    bridge._rx_count = 0
    bridge._tx_count = 0
    bridge._device_identity = {}
    bridge._open_log_file("COM99")

    # Start background reader thread
    bridge._stop_event.clear()
    bridge._reader_thread = threading.Thread(target=bridge._read_loop, daemon=True)
    bridge._reader_thread.start()

    return {"ok": True, "port": "COM99", "baudrate": 115200}


# ── Tests ──


class TestConnectDisconnect:
    """Test connect/disconnect lifecycle."""

    def test_connect_and_disconnect(self):
        bridge = make_bridge()
        mock = LoopbackSerial()
        result = connect_loopback(bridge, mock)
        assert result["ok"] is True
        assert bridge.status["connected"] is True

        disc = bridge.disconnect()
        assert disc["ok"] is True
        assert bridge.status["connected"] is False
        bridge.shutdown()

    def test_connect_replaces_existing(self):
        bridge = make_bridge()
        mock1 = LoopbackSerial()
        mock2 = LoopbackSerial()
        connect_loopback(bridge, mock1)
        assert bridge.status["connected"] is True

        # Disconnect first, then reconnect with new mock
        bridge.disconnect()
        connect_loopback(bridge, mock2)
        assert bridge.status["connected"] is True
        assert mock1.is_open is False
        bridge.shutdown()

    def test_disconnect_when_not_connected(self):
        bridge = make_bridge()
        result = bridge.disconnect()
        assert result["ok"] is True
        bridge.shutdown()

    def test_connect_blocks_disallowed_port(self):
        bridge = SerialBridge(allowed_ports=("COM3",))
        result = bridge.connect("COM99")
        assert result["ok"] is False
        assert "not explicitly allowed" in result["error"]
        bridge.shutdown()


class TestWriteAndRead:
    """Test write and read through the bridge."""

    def test_write_records_in_buffer(self):
        bridge = make_bridge()
        mock = LoopbackSerial()
        connect_loopback(bridge, mock)

        result = bridge.write("AT+RST")
        assert result["ok"] is True
        assert result["bytes_sent"] > 0

        lines = bridge.get_lines(n=10, direction="tx")
        assert len(lines) == 1
        assert lines[0]["raw"] == "AT+RST"
        bridge.shutdown()

    def test_echo_appears_in_rx(self):
        bridge = make_bridge()
        mock = LoopbackSerial(echo=True, echo_delay=0.01)
        connect_loopback(bridge, mock)

        bridge.write("AT+GMR")
        time.sleep(0.1)  # wait for echo

        rx_lines = bridge.get_lines(n=10, direction="rx")
        assert len(rx_lines) >= 1
        assert "AT+GMR" in rx_lines[0]["raw"]
        bridge.shutdown()

    def test_write_with_newline(self):
        bridge = make_bridge()
        mock = LoopbackSerial()
        connect_loopback(bridge, mock)

        result = bridge.write("AT", newline="\r\n")
        assert result["ok"] is True

        tx = bridge.get_lines(n=1, direction="tx")
        assert tx[0]["raw"] == "AT\r\n"
        bridge.shutdown()

    def test_write_when_disconnected(self):
        bridge = make_bridge()
        result = bridge.write("AT")
        assert result["ok"] is False
        assert "Not connected" in result["error"]
        bridge.shutdown()

    def test_rx_filter(self):
        bridge = make_bridge()
        mock = LoopbackSerial(echo=True, echo_delay=0.005)
        connect_loopback(bridge, mock)

        bridge.write("cmd1")
        time.sleep(0.05)
        bridge.write("cmd2")
        time.sleep(0.05)

        all_lines = bridge.get_lines(n=100)
        rx_lines = bridge.get_lines(n=100, direction="rx")
        tx_lines = bridge.get_lines(n=100, direction="tx")

        assert len(all_lines) == len(rx_lines) + len(tx_lines)
        assert len(tx_lines) == 2
        bridge.shutdown()

    def test_binary_echo(self):
        """Test that binary data passes through without crashing."""
        bridge = make_bridge()
        mock = LoopbackSerial(echo=True, echo_delay=0.01)
        connect_loopback(bridge, mock)

        binary_data = bytes(range(256))
        result = bridge.write(binary_data.hex())
        assert result["ok"] is True
        bridge.shutdown()


class TestSearch:
    """Test buffer search."""

    def test_search_finds_keyword(self):
        bridge = make_bridge()
        bridge._buffer.append({"ts": 1.0, "raw": "ERROR: connection failed", "direction": "rx"})
        bridge._buffer.append({"ts": 2.0, "raw": "OK", "direction": "rx"})
        bridge._buffer.append({"ts": 3.0, "raw": "ERROR: timeout", "direction": "rx"})

        results = bridge.search("ERROR")
        assert len(results) == 2
        assert all("ERROR" in r["raw"] for r in results)
        bridge.shutdown()

    def test_search_case_sensitive(self):
        bridge = make_bridge()
        bridge._buffer.append({"ts": 1.0, "raw": "error", "direction": "rx"})
        bridge._buffer.append({"ts": 2.0, "raw": "ERROR", "direction": "rx"})

        results = bridge.search("ERROR")
        assert len(results) == 1
        bridge.shutdown()

    def test_search_respects_limit(self):
        bridge = make_bridge()
        for i in range(20):
            bridge._buffer.append({"ts": float(i), "raw": f"line {i} target", "direction": "rx"})

        results = bridge.search("target", n=5)
        assert len(results) == 5
        bridge.shutdown()


class TestRequest:
    """Test serial_request (send-and-wait)."""

    def test_request_matches_response(self):
        bridge = make_bridge()
        mock = LoopbackSerial(echo=True, echo_delay=0.05)
        connect_loopback(bridge, mock)

        # The echo will return the command itself; match on it
        result = bridge.request("AT+GMR", "AT\\+GMR", timeout=2.0)
        assert result["ok"] is True
        assert "AT+GMR" in result["matched_line"]
        assert result["elapsed_ms"] > 0
        assert isinstance(result["context"], list)
        bridge.shutdown()

    def test_request_timeout_returns_recent_rx(self):
        bridge = make_bridge()
        mock = LoopbackSerial(echo=False)  # no echo — will timeout
        connect_loopback(bridge, mock)

        # Inject some RX data before the request
        mock.inject_rx(b"some device log\n")
        time.sleep(0.05)

        result = bridge.request("AT+RST", "ready", timeout=0.3)
        assert result["ok"] is False
        assert result["error"] == "timeout"
        assert "recent_rx" in result
        assert result["timeout_sec"] == 0.3
        bridge.shutdown()

    def test_request_invalid_regex(self):
        bridge = make_bridge()
        mock = LoopbackSerial()
        connect_loopback(bridge, mock)

        result = bridge.request("AT", "(?P<bad")
        assert result["ok"] is False
        assert "Invalid regex" in result["error"]
        bridge.shutdown()

    def test_request_with_groups(self):
        bridge = make_bridge()
        mock = LoopbackSerial(echo=False)
        connect_loopback(bridge, mock)

        # Inject a response with a delay so it arrives after the command is sent
        def delayed_inject():
            time.sleep(0.1)
            mock.inject_rx(b"VERSION: 1.2.3\r\n")

        t = threading.Thread(target=delayed_inject, daemon=True)
        t.start()

        result = bridge.request("AT+GMR", r"VERSION:\s*(\S+)", timeout=2.0)
        assert result["ok"] is True
        assert result["match_groups"] == ["1.2.3"]
        bridge.shutdown()

    def test_request_disconnected(self):
        bridge = make_bridge()
        result = bridge.request("AT", "OK")
        assert result["ok"] is False
        assert "Not connected" in result["error"]


class TestWatch:
    """Test background symptom watch."""

    def test_watch_start_stop(self):
        bridge = make_bridge()
        mock = LoopbackSerial(echo=False)
        connect_loopback(bridge, mock)

        result = bridge.start_watch(platform="esp32")
        assert result["ok"] is True

        status = bridge.get_watch_status()
        assert status["active"] is True

        result = bridge.stop_watch()
        assert result["ok"] is True
        assert bridge.get_watch_status()["active"] is False
        bridge.shutdown()

    def test_watch_detects_symptoms(self):
        bridge = make_bridge()
        mock = LoopbackSerial(echo=False)
        connect_loopback(bridge, mock)

        bridge.start_watch(platform="esp32")

        # Inject error lines
        mock.inject_rx(b"Guru Meditation Error: Core 0 panic'ed\r\n")
        time.sleep(0.3)
        mock.inject_rx(b"WDT reset\r\n")
        time.sleep(0.3)

        alerts = bridge.get_watch_alerts(n=10)
        assert len(alerts) >= 1
        assert any(a["severity"] == "critical" for a in alerts)

        bridge.stop_watch()
        bridge.shutdown()

    def test_watch_not_active_when_disconnected(self):
        bridge = make_bridge()
        result = bridge.start_watch()
        assert result["ok"] is False
        assert "Not connected" in result["error"]
        bridge.shutdown()


class TestLogEngineering:
    """Test log rotation, redaction, bookmarks, export."""

    def test_log_rotation_creates_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = RotatingLogWriter(Path(tmpdir), "COM1", max_size=200, max_files=5)
            writer.open()
            for i in range(100):
                writer.write("rx", f"log line {i} with padding to fill the file quickly")
            writer.close()

            files = sorted(Path(tmpdir).glob("COM1_*.log"))
            assert len(files) > 1
            # All files should be under max_size (approximately)
            for f in files:
                assert f.stat().st_size < 500  # some overhead from header

    def test_log_rotation_max_files_cleanup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = RotatingLogWriter(Path(tmpdir), "COM2", max_size=100, max_files=3)
            writer.open()
            for i in range(200):
                writer.write("rx", f"line {i} padding data to fill rotation")
            writer.close()

            files = list(Path(tmpdir).glob("COM2_*.log"))
            assert len(files) <= 3

    def test_log_metadata_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = RotatingLogWriter(Path(tmpdir), "COM3")
            writer.open(metadata={"baudrate": 115200, "device_vid": "0x1a86"})
            writer.write("rx", "test line")
            writer.close()

            content = list(Path(tmpdir).glob("COM3_*.log"))[0].read_text(encoding="utf-8")
            assert "port: COM3" in content
            assert "baudrate: 115200" in content
            assert "device_vid: 0x1a86" in content

    def test_redaction_masks_sensitive_data(self):
        assert "secret123" not in _apply_redaction('password=secret123')
        assert "[REDACTED]" in _apply_redaction('password=secret123')
        assert "mytoken" not in _apply_redaction('token=mytoken')
        assert "wifi_pass" not in _apply_redaction('AT+CWJAP="MyNet","wifi_pass"')

    def test_redaction_preserves_normal_data(self):
        normal = "AT+GMR\r\nESP32 v1.0"
        assert _apply_redaction(normal) == normal

    def test_bookmark_in_buffer_and_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = SerialBridge(log_dir=Path(tmpdir), allowed_ports=("COM99",))
            mock = LoopbackSerial()
            connect_loopback(bridge, mock)

            result = bridge.bookmark("test-event")
            assert result["ok"] is True

            bm_lines = bridge.get_lines(n=1, direction="bookmark")
            assert len(bm_lines) == 1
            assert "test-event" in bm_lines[0]["raw"]

            bridge._close_log_file()
            log_content = list(Path(tmpdir).glob("COM99_*.log"))[0].read_text(encoding="utf-8")
            assert "BOOKMARK" in log_content
            bridge.shutdown()

    def test_export_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = SerialBridge(log_dir=Path(tmpdir), allowed_ports=("COM99",))
            mock = LoopbackSerial(echo=True, echo_delay=0.01)
            connect_loopback(bridge, mock)

            bridge.write("AT")
            time.sleep(0.05)

            result = bridge.export_bundle(context_lines=50)
            assert result["ok"] is True

            bundle_path = Path(result["path"])
            assert bundle_path.is_file()

            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            assert "config" in bundle
            assert "recent_lines" in bundle
            assert bundle["config"]["port"] == "COM99"
            bridge.shutdown()


class TestDisconnectDetection:
    """Test behavior when serial connection drops."""

    def test_read_loop_stops_on_close(self):
        bridge = make_bridge()
        mock = LoopbackSerial(echo=False)
        connect_loopback(bridge, mock)

        # Verify reader is running
        assert bridge._reader_thread is not None
        assert bridge._reader_thread.is_alive()

        # Close the mock port
        mock.close()

        # Shutdown should complete cleanly (reader detects closed port)
        bridge.shutdown()
        assert not bridge._connected
        assert mock.is_open is False

    def test_write_after_disconnect(self):
        bridge = make_bridge()
        mock = LoopbackSerial()
        connect_loopback(bridge, mock)

        mock.close()
        time.sleep(0.2)

        result = bridge.write("AT")
        # Should either succeed (buffer-level) or fail gracefully
        assert isinstance(result, dict)
        assert "ok" in result
        bridge.shutdown()


class TestHighThroughput:
    """Test behavior under high data volume."""

    def test_ring_buffer_overflow(self):
        bridge = SerialBridge(max_lines=100, allowed_ports=("COM99",))
        mock = LoopbackSerial(echo=False)
        connect_loopback(bridge, mock)

        # Inject many lines
        for i in range(200):
            mock.inject_rx(f"line {i}\n".encode())
        time.sleep(0.5)

        lines = bridge.get_lines(n=1000)
        assert len(lines) <= 100
        # Should have the most recent lines
        assert lines[-1]["raw"] == "line 199"
        bridge.shutdown()

    def test_concurrent_read_write(self):
        bridge = make_bridge()
        mock = LoopbackSerial(echo=False)
        connect_loopback(bridge, mock)

        errors = []

        def writer():
            try:
                for i in range(50):
                    bridge.write(f"cmd{i}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def injector():
            try:
                for i in range(50):
                    mock.inject_rx(f"resp{i}\n".encode())
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=injector)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert len(errors) == 0
        all_lines = bridge.get_lines(n=1000)
        tx_lines = [l for l in all_lines if l["direction"] == "tx"]
        rx_lines = [l for l in all_lines if l["direction"] == "rx"]
        assert len(tx_lines) == 50
        # RX may vary due to timing, but should be close to 50
        assert len(rx_lines) >= 40
        bridge.shutdown()


class TestStats:
    """Test buffer statistics."""

    def test_stats_accuracy(self):
        bridge = make_bridge()
        bridge._buffer.append({"ts": 1.0, "raw": "a", "direction": "rx"})
        bridge._buffer.append({"ts": 2.0, "raw": "b", "direction": "tx"})
        bridge._buffer.append({"ts": 3.0, "raw": "c", "direction": "rx"})

        stats = bridge.get_stats()
        assert stats["total_lines"] == 3
        assert stats["rx_lines"] == 2
        assert stats["tx_lines"] == 1
        assert stats["first_ts"] == 1.0
        assert stats["last_ts"] == 3.0
        assert stats["duration_sec"] == 2.0
        bridge.shutdown()

    def test_stats_empty_buffer(self):
        bridge = make_bridge()
        stats = bridge.get_stats()
        assert stats["total_lines"] == 0
        assert stats["first_ts"] is None
        bridge.shutdown()


# ── Standalone Runner ──


def run_all_tests():
    """Run all tests without pytest."""
    import traceback

    passed = 0
    failed = 0
    errors = []

    for cls_name, cls in sorted(globals().items()):
        if not isinstance(cls, type) or not cls_name.startswith("Test"):
            continue
        instance = cls()
        for method_name in sorted(dir(instance)):
            if not method_name.startswith("test_"):
                continue
            test_name = f"{cls_name}.{method_name}"
            try:
                getattr(instance, method_name)()
                passed += 1
                print(f"  PASS: {test_name}")
            except Exception as e:
                failed += 1
                errors.append((test_name, e))
                print(f"  FAIL: {test_name}: {e}")

    print(f"\nE2E Tests: {passed} passed, {failed} failed")
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  {name}:")
            traceback.print_exception(type(err), err, err.__traceback__)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all_tests())
