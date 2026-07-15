#!/usr/bin/env python3
"""Keep a receive-only serial session alive and write incremental JSONL events.

Use this only when no MCP host is available.  The MCP equivalents are
``serial_session_start`` and ``serial_session_poll``.
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp"))

from serial_client import SerialBridge  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Persistent receive-only serial monitor")
    parser.add_argument("--port", required=True, help="Explicit serial port, for example COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--events", type=Path, required=True, help="JSONL event file")
    parser.add_argument("--logs", type=Path, help="Optional rotating raw-session log directory")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()

    running = True

    def stop(_signum, _frame) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    bridge = SerialBridge(log_dir=args.logs)
    args.events.parent.mkdir(parents=True, exist_ok=True)
    sequence = 0
    last_status: tuple[object, ...] | None = None
    with args.events.open("a", encoding="utf-8") as output:
        output.write(json.dumps({"event": "monitor_start", "port": args.port, "baudrate": args.baudrate}, ensure_ascii=False) + "\n")
        output.flush()
        while running:
            if not bridge.status["session_active"]:
                started = bridge.start_session(args.port, baudrate=args.baudrate, auto_reconnect=True)
                output.write(json.dumps({"event": "connect_attempt", "result": started}, ensure_ascii=False) + "\n")
                output.flush()
                if not started.get("ok"):
                    time.sleep(max(0.1, args.poll_seconds))
                    continue
            poll = bridge.poll_session(after_sequence=sequence, n=1000)
            sequence = poll["next_sequence"]
            status = poll["status"]
            status_key = tuple(status.get(key) for key in (
                "connected", "connection_state", "session_active", "last_disconnect_reason",
                "last_read_error", "reconnect_attempts", "reconnect_successes",
            ))
            if status_key != last_status:
                output.write(json.dumps({"event": "status", "status": status}, ensure_ascii=False) + "\n")
                last_status = status_key
            for entry in poll["entries"]:
                output.write(json.dumps({"event": "line", **entry}, ensure_ascii=False) + "\n")
            output.flush()
            time.sleep(max(0.1, args.poll_seconds))
        bridge.disconnect()
        output.write(json.dumps({"event": "monitor_stop", "status": bridge.status}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
