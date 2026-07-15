#!/usr/bin/env python3
"""Verify a device MQTT publish through an explicitly authorised serial AT session.

The caller supplies the target serial port, broker and module-specific AT command
templates.  This script never discovers devices or brokers.  ``SERIAL_ALLOWED_PORTS``
and ``MQTT_ALLOWED_HOSTS`` remain mandatory policy boundaries in the two bridges.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp"))

from mqtt_client import get_bridge as mqtt_bridge
from serial_client import get_bridge as serial_bridge


def _format_template(template: str, values: dict[str, str], label: str) -> str:
    try:
        return template.format(**values)
    except KeyError as exc:
        raise ValueError(f"{label} contains unsupported placeholder {exc}; allowed: broker, topic, payload, ssid, password") from exc


def _request(serial, command: str, stage: str, timeout: float) -> dict:
    result = serial.request(command, expect="OK", timeout=timeout)
    # Never surface the command: templates can contain Wi-Fi credentials.
    return {"ok": bool(result.get("ok")), "stage": stage, **({"error": result.get("error", "AT command failed")} if not result.get("ok") else {})}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Explicitly allowlisted serial port")
    parser.add_argument("--broker", required=True, help="Explicitly allowlisted MQTT broker host")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--ssid", required=True)
    parser.add_argument("--wifi-password-env", required=True, metavar="ENV", help="Environment variable containing the Wi-Fi password")
    parser.add_argument("--wifi-command", default='AT+CWJAP="{ssid}","{password}"')
    parser.add_argument("--mqtt-command", action="append", required=True, help="Module-specific MQTT setup AT command template; repeat as needed")
    parser.add_argument("--publish-command", required=True, help="AT command template that makes the device publish {payload} to {topic}")
    parser.add_argument("--payload", default="skill-e2e-probe")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    if not 0.1 <= args.timeout <= 30.0:
        parser.error("--timeout must be between 0.1 and 30 seconds")
    password = os.environ.get(args.wifi_password_env)
    if not password:
        parser.error(f"environment variable {args.wifi_password_env!r} is not set")

    values = {"broker": args.broker, "topic": args.topic, "payload": args.payload, "ssid": args.ssid, "password": password}
    try:
        wifi_command = _format_template(args.wifi_command, values, "--wifi-command")
        mqtt_commands = [_format_template(command, values, "--mqtt-command") for command in args.mqtt_command]
        publish_command = _format_template(args.publish_command, values, "--publish-command")
    except ValueError as exc:
        parser.error(str(exc))

    serial = serial_bridge()
    mqtt = mqtt_bridge()
    serial_connected = False
    mqtt_connected = False
    try:
        serial_result = serial.connect(port=args.port)
        if not serial_result.get("ok"):
            print(json.dumps({"ok": False, "stage": "serial_connect", "error": serial_result.get("error")}, ensure_ascii=False))
            return 1
        serial_connected = True
        for stage, command in [("wifi", wifi_command), *(("mqtt_setup", command) for command in mqtt_commands)]:
            result = _request(serial, command, stage, args.timeout)
            if not result["ok"]:
                print(json.dumps(result, ensure_ascii=False))
                return 1

        broker_result = mqtt.connect(host=args.broker)
        if not broker_result.get("ok"):
            print(json.dumps({"ok": False, "stage": "mqtt_connect", "error": broker_result.get("error")}, ensure_ascii=False))
            return 1
        mqtt_connected = True
        subscription = mqtt.subscribe(topic=args.topic)
        if not subscription.get("ok"):
            print(json.dumps({"ok": False, "stage": "mqtt_subscribe", "error": subscription.get("error")}, ensure_ascii=False))
            return 1
        received_after = time.time()
        result = _request(serial, publish_command, "device_publish", args.timeout)
        if not result["ok"]:
            print(json.dumps(result, ensure_ascii=False))
            return 1

        deadline = time.monotonic() + args.timeout
        messages: list[dict] = []
        while time.monotonic() < deadline:
            messages = mqtt.get_messages(topic=args.topic, since=received_after)
            if any(item.get("payload") == args.payload for item in messages):
                print(json.dumps({"ok": True, "stage": "verified", "topic": args.topic, "payload": args.payload, "messages": messages}, ensure_ascii=False))
                return 0
            time.sleep(0.1)
        print(json.dumps({"ok": False, "stage": "verify", "error": "expected MQTT payload was not received before timeout"}, ensure_ascii=False))
        return 1
    finally:
        if mqtt_connected:
            mqtt.disconnect()
        if serial_connected:
            serial.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
